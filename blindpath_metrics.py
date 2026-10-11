import math
import numpy as np
import cv2

# ============================================================
# 常量定义
# ============================================================
CLASS_ID_TACTILE_PAVING = 80  # YOLO 模型中盲道类别的 ID

# 盲道面积占比阈值（用于判断盲道是否缺失或被遮挡）
# - 面积占比 = 盲道轮廓像素数 / 画面总像素数
# - 低于 MISSING_THRESHOLD 认为盲道缺失或严重不足
# - 在 MISSING_THRESHOLD 和 OBSTACLE_THRESHOLD 之间认为可能有障碍物遮挡
AREA_RATIO_MISSING_THRESHOLD = 0.02      # 2% 以下判定为盲道缺失
AREA_RATIO_OBSTACLE_THRESHOLD = 0.05     # 5% 以下判定为可能有障碍物

# ============================================================
# 偏移检测和跑偏判定说明
# ============================================================
# 1. 偏移量 (offset / d_user)
#    - 在画面下半部分（50%~95%高度）逐行扫描盲道轮廓
#    - 每行找到盲道的左右边界，计算中点 x_mid
#    - 归一化偏移：d = (x_mid - w/2) / (w_path/2)
#      其中 w_path = 盲道宽度，w = 画面宽度
#      含义：偏移量以"半个盲道宽度"为单位
#      d = 0   → 盲道中线与画面中线重合（居中）
#      d = 0.5 → 盲道中线偏离画面中线半个盲道宽度
#      d = 1.0 → 盲道中线偏离画面中线一个盲道宽度
#    - 取所有扫描行中偏移绝对值最大的作为最终 offset
#    - 符号：d > 0 → 盲道在画面中线右侧（人偏左）
#           d < 0 → 盲道在画面中线左侧（人偏右）
#
# 2. 方向角 (angle)
#    - 取最近处和最远处的两个中线点
#    - angle = atan2(x_near - x_far, y_near - y_far) 转角度
#    - 正值 → 盲道向右倾斜，负值 → 向左倾斜
#
# 3. 三态判定
#    - |d| < 0.3   → "居中"（偏移小于 0.3 个盲道半宽）
#    - 0.3 ≤ |d| < 1.0 → "偏移"（偏移在 0.3~1.0 个盲道半宽之间）
#    - |d| ≥ 1.0   → "严重偏移"（偏移超过 1 个盲道半宽）
#
# 4. 面积占比判定（新增：用于检测盲道缺失/障碍物）
#    - area_ratio < 2%  → "盲道缺失"（画面中盲道面积过小）
#    - 2% ≤ area_ratio < 5% → "疑似障碍"（盲道面积偏小，可能被遮挡）
#    - area_ratio ≥ 5% → 正常，继续偏移判定
#
# 5. 语音告警触发（blindpath_voice.py）
#    - 偏移阈值：offset >= alert_offset_thresh%（默认 30%，即 d >= 0.3）
#    - 角度阈值：|angle| >= alert_angle_thresh°（默认 20°）
#    - 面积阈值：area_ratio < 2% 触发"盲道缺失"告警
#    - 持续时间：异常状态持续 >= min_abnormal_duration 秒（默认 2.0s）
#    - 触发后必须恢复正常状态，才能再次累积
# ============================================================

def measure(frame, pts):
    """
    逐行扫描盲道轮廓，计算偏移量和方向角。
    
    算法原理：
    1. 将盲道轮廓填充为二值掩膜图像
    2. 在画面下半部分（50%~95%高度）逐行扫描
    3. 对每一行，找到盲道的左右边界，计算中点位置
    4. 计算该行的归一化偏移量：(中点 - 画面中心) / (半个盲道宽度)
    5. 取所有扫描行中偏移绝对值最大的作为最终偏移量
    6. 用最远处和最近处的中点计算方向角
    
    参数:
        frame: 当前视频帧（numpy 数组，H×W×3）
        pts: 盲道轮廓点集（多边形顶点列表）
    
    返回:
        (d_user, angle, ok)
        - d_user: 归一化偏移量（负号表示人的偏移方向）
        - angle: 方向角（度），正值表示盲道向右倾斜
        - ok: 是否成功计算（False 表示有效扫描行不足）
    """
    h, w = frame.shape[:2]

    # ① 把轮廓填成二值图，方便按行扫描
    # 创建一个与画面同样大小的空白图像
    mask_img = np.zeros((h, w), np.uint8)
    # 将盲道轮廓填充为白色（值为1），其余为黑色（值为0）
    cv2.fillPoly(mask_img, [np.asarray(pts, dtype=np.int32)], 1)

    # ② 在画面下半部分逐行扫描（50%~95%高度）
    # 选择下半部分是因为透视关系中，画面下方离人更近，盲道更宽，测量更准确
    y_start, y_end = int(h * 0.50), int(h * 0.95)
    mids = []  # 存储每行中点坐标 (y, x_mid)
    d_max = 0.0  # 记录最大偏移量

    for y in range(y_start, y_end):
        # 找到当前行中所有属于盲道的像素的 x 坐标
        xs = np.where(mask_img[y] > 0)[0]
        if len(xs) < 2:
            # 当前行盲道像素不足2个，无法确定左右边界，跳过
            continue
        
        # 取最左和最右的盲道像素作为边界
        x_left, x_right = xs[0], xs[-1]
        w_path = x_right - x_left  # 当前行盲道宽度
        
        if w_path < 5:
            # 盲道太窄（通常在远处），测量误差大，跳过
            continue

        # 计算当前行盲道中点的 x 坐标
        x_mid = (x_left + x_right) / 2.0
        # 归一化偏移量：以"半个盲道宽度"为单位
        # d = 0 表示盲道中线与画面中线重合
        # d = 1 表示盲道中线偏离画面中线一个盲道宽度
        d = (x_mid - w / 2.0) / (w_path / 2.0)
        
        # 记录最大偏移量（取绝对值最大的）
        if abs(d) > abs(d_max):
            d_max = d
        mids.append((y, x_mid))

    if len(mids) < 2:
        # 有效扫描行不足2行，无法计算方向角
        return None, None, False

    # ③ 计算方向角：从最远处的中线点指向最近处的中线点
    # mids[0] 是最远处（y 值小），mids[-1] 是最近处（y 值大）
    y_far, x_far = mids[0]
    y_near, x_near = mids[-1]
    # atan2 返回的是弧度，转换为角度
    angle = math.degrees(math.atan2(x_near - x_far, y_near - y_far))

    # 返回时取反：盲道在画面右侧 → 人偏左（需要向左调整）
    return -d_max, angle, True


def analyze(frame, result):
    """
    从 YOLO 分割结果中计算盲道检测指标。
    
    算法流程：
    1. 从分割结果中提取所有盲道实例（类别 ID = 80）
    2. 计算盲道面积占比，判断是否存在盲道缺失或障碍物遮挡
    3. 取面积最大的盲道实例作为"主盲道"
    4. 对主盲道进行逐行扫描，计算偏移量和方向角
    5. 根据偏移量进行三态判定（居中/偏移/严重偏移）
    
    参数:
        frame: 当前视频帧（numpy 数组，H×W×3）
        result: YOLO 推理结果对象（包含 masks、boxes 等）
    
    返回:
        指标字典，包含以下字段：
        - count: 检测到的盲道实例数量
        - offset: 归一化偏移量（None 表示无法计算）
        - angle: 方向角（度，None 表示无法计算）
        - area: 主盲道面积占比（0.0~1.0）
        - area_ratio: 同 area，盲道占画面比例（用于判断缺失/障碍）
        - state: 状态字符串（"未检出"/"盲道缺失"/"疑似障碍"/"居中"/"偏移"/"严重偏移"/"无法测量"）
        - direction: 偏移方向（"无"/"左"/"右"）
        - valid: 是否成功计算出有效指标
        - invalid_reason: 失败原因（None 表示成功）
    """
    h, w = frame.shape[:2]
    frame_area = w * h  # 画面总像素数
    
    # 定义返回空指标的模板字典
    empty = {
        "count": 0,
        "offset": None,
        "angle": None,
        "area": 0.0,
        "area_ratio": 0.0,
        "state": "未检出",
        "direction": "无",
        "valid": False,
        "invalid_reason": "未检出盲道",
    }

    # 检查是否有分割掩膜结果
    masks = result.masks
    if masks is None:
        return empty

    pixel_coords = masks.xy  # 每个实例的像素级轮廓坐标
    cls = result.boxes.cls   # 每个实例的类别 ID

    # ① 筛选出所有盲道实例（类别 ID = 80）
    paving = [pixel_coords[i] for i in range(len(pixel_coords))
              if int(cls[i].item()) == CLASS_ID_TACTILE_PAVING]
    if not paving:
        return empty

    # ② 取面积最大的作为"主盲道"（假设画面中最大的盲道是用户正在行走的那条）
    main = max(paving, key=cv2.contourArea)
    pts = np.asarray(main, dtype=np.float32)
    
    if len(pts) < 3:
        # 轮廓点数不足3个，说明轮廓退化（可能是线段或点），无法计算
        empty["invalid_reason"] = "轮廓退化"
        return empty

    # 计算盲道面积占比（用于判断盲道缺失或障碍物遮挡）
    main_area = cv2.contourArea(main)
    area_ratio = main_area / frame_area

    # ③ 基于面积占比判断盲道状态
    if area_ratio < AREA_RATIO_MISSING_THRESHOLD:
        # 盲道面积占比过小（< 2%），可能是盲道缺失或距离过远
        return {
            "count": len(paving),
            "offset": None,
            "angle": None,
            "area": area_ratio,
            "area_ratio": area_ratio,
            "state": "盲道缺失",
            "direction": "无",
            "valid": False,
            "invalid_reason": f"盲道面积占比过低（{area_ratio*100:.2f}%），可能缺失",
        }
    
    if area_ratio < AREA_RATIO_OBSTACLE_THRESHOLD:
        # 盲道面积占比偏小（2%~5%），可能被障碍物遮挡
        return {
            "count": len(paving),
            "offset": None,
            "angle": None,
            "area": area_ratio,
            "area_ratio": area_ratio,
            "state": "疑似障碍",
            "direction": "无",
            "valid": False,
            "invalid_reason": f"盲道面积占比较小（{area_ratio*100:.2f}%），可能有障碍",
        }

    # ④ 面积占比正常，继续计算偏移量和方向角
    d_user, angle, ok = measure(frame, pts)
    if not ok:
        # 有效扫描行不足，无法计算偏移和角度
        return {
            "count": len(paving),
            "offset": None,
            "angle": None,
            "area": area_ratio,
            "area_ratio": area_ratio,
            "state": "无法测量",
            "direction": "无",
            "valid": False,
            "invalid_reason": "有效扫描行不足",
        }

    # ⑤ 三态判定 + 方向判断
    abs_d = abs(d_user)
    if abs_d < 0.3:
        # 偏移量小于 0.3 个盲道半宽，判定为居中
        state = "居中"
        direction = "无"
    elif abs_d < 1.0:
        # 偏移量在 0.3~1.0 个盲道半宽之间，判定为偏移
        state = "偏移"
        direction = "左" if d_user < 0 else "右"
    else:
        # 偏移量超过 1 个盲道半宽，判定为严重偏移
        state = "严重偏移"
        direction = "左" if d_user < 0 else "右"

    return {
        "count": len(paving),
        "offset": d_user,
        "angle": angle,
        "area": area_ratio,
        "area_ratio": area_ratio,
        "state": state,
        "direction": direction,
        "valid": True,
        "invalid_reason": None,
    }