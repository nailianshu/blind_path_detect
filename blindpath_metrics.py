import math
import numpy as np
import cv2

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
# 4. 语音告警触发（blindpath_voice.py）
#    - 偏移阈值：offset >= alert_offset_thresh%（默认 30%，即 d >= 0.3）
#    - 角度阈值：|angle| >= alert_angle_thresh°（默认 20°）
#    - 持续时间：异常状态持续 >= min_abnormal_duration 秒（默认 2.0s）
#    - 触发后必须恢复正常状态，才能再次累积
# ============================================================

def measure(frame, pts):
    """逐行扫描求偏移量和方向角。返回 (d_user, angle, ok)"""
    h, w = frame.shape[:2]

    # ① 把轮廓填成二值图，方便按行扫描
    mask_img = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask_img, [np.asarray(pts, dtype=np.int32)], 1)

    # ② 在画面下半部分逐行扫描
    y_start, y_end = int(h * 0.50), int(h * 0.95)
    mids = []
    d_max = 0.0

    for y in range(y_start, y_end):
        xs = np.where(mask_img[y] > 0)[0]
        if len(xs) < 2:
            continue
        x_left, x_right = xs[0], xs[-1]
        w_path = x_right - x_left
        if w_path < 5:                       # 太窄（远处），跳过
            continue

        x_mid = (x_left + x_right) / 2.0
        d = (x_mid - w / 2.0) / (w_path / 2.0)   # 归一化到"半个盲道宽"
        if abs(d) > abs(d_max):
            d_max = d
        mids.append((y, x_mid))

    if len(mids) < 2:
        return None, None, False

    # ③ 方向角：最远处中线点 → 最近处中线点
    y_far, x_far = mids[0]
    y_near, x_near = mids[-1]
    angle = math.degrees(math.atan2(x_near - x_far, y_near - y_far))

    return -d_max, angle, True               # ★ 取反：盲道在右 → 人偏左


def analyze(frame, result):
    """从分割结果里算指标。返回详细指标字典。"""
    h, w = frame.shape[:2]
    empty = {
        "count": 0,
        "offset": None,
        "angle": None,
        "area": 0.0,
        "state": "未检出",
        "direction": "无",
        "valid": False,
        "invalid_reason": "未检出盲道",
    }

    masks = result.masks
    if masks is None:
        return empty

    pixel_coords = masks.xy
    cls = result.boxes.cls

    # ① 挑出所有盲道实例
    paving = [pixel_coords[i] for i in range(len(pixel_coords))
              if int(cls[i].item()) == 80]
    if not paving:
        return empty

    # ② 取面积最大的作为"主盲道"
    main = max(paving, key=cv2.contourArea)
    pts = np.asarray(main, dtype=np.float32)
    if len(pts) < 3:                      # 退化轮廓，算不了
        empty["invalid_reason"] = "轮廓退化"
        return empty

    # ③ 逐行扫描求偏移和角度
    d_user, angle, ok = measure(frame, pts)
    if not ok:
        return {
            "count": len(paving),
            "offset": None,
            "angle": None,
            "area": cv2.contourArea(main) / (w * h),
            "state": "无法测量",
            "direction": "无",
            "valid": False,
            "invalid_reason": "有效扫描行不足",
        }

    # ④ 三态判定 + 方向
    abs_d = abs(d_user)
    if abs_d < 0.3:
        state = "居中"
        direction = "无"
    elif abs_d < 1.0:
        state = "偏移"
        direction = "左" if d_user < 0 else "右"
    else:
        state = "严重偏移"
        direction = "左" if d_user < 0 else "右"

    return {
        "count": len(paving),
        "offset": d_user,
        "angle": angle,
        "area": cv2.contourArea(main) / (w * h),
        "state": state,
        "direction": direction,
        "valid": True,
        "invalid_reason": None,
    }