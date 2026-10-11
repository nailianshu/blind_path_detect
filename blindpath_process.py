import os
import time
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from ultralytics import YOLO

from blindpath_metrics import analyze, CLASS_ID_TACTILE_PAVING
from blindpath_recorder import VideoRecorder


# 图片扩展名（用来和视频分流）
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

# 推理线程（组合 metrics + recorder）
class MyBlindPathProcess(QThread):
    """
    视频/图片/摄像头读取 + YOLO分割推理子线程
    
    功能说明：
    - 支持三种输入源：图片文件、视频文件、摄像头设备
    - 对每一帧进行 YOLO 实例分割推理
    - 绘制盲道轮廓、中线、参考线
    - 计算偏移量、方向角、面积占比等指标
    - 支持视频录制功能
    
    使用方式：
    1. 创建实例：process = MyBlindPathProcess(model, source)
       - source 可以是图片/视频路径，也可以是整数（摄像头索引）
    2. 启动线程：process.start()
    3. 接收信号：process.done_signal.connect(callback)
    4. 停止线程：process.stop()
    """
    done_signal = pyqtSignal(np.ndarray, object)   # (帧, 指标字典)

    def __init__(self, model, source):
        """
        初始化推理线程
        
        参数:
            model: YOLO 模型实例（已加载）
            source: 输入源
                   - 字符串：图片/视频文件路径
                   - 整数：摄像头设备索引（如 0 表示默认摄像头）
        """
        super().__init__()
        self.runFlag = True
        self.model = model            # 模型由外面传入，只加载一次
        self.source = source          # 要处理的素材路径或摄像头索引
        self.recorder = VideoRecorder()
        self.is_camera = isinstance(source, int)  # 判断是否为摄像头输入

    def stop(self):
        """设置标志，退出线程循环"""
        self.runFlag = False

    def startRecord(self, out_path):
        """开始录制视频"""
        self.recorder.startRecord(out_path)

    def stopRecord(self):
        """停止录制视频"""
        self.recorder.stopRecord()

    def draw_tactile_paving(self, frame, masks, cls):
        """
        对盲道实例进行可视化绘制
        
        绘制内容：
        1. 半透明绿色填充盲道区域
        2. 黄色加粗中线（逐行取中点连线）
        
        参数:
            frame: 当前帧（会被直接修改）
            masks: YOLO 分割掩膜对象
            cls: 每个实例的类别 ID 数组
        """
        overlay = frame.copy()  # 创建副本用于半透明叠加
        h, w = frame.shape[:2]

        for i in range(len(masks.xy)):
            # 只绘制盲道类别的实例
            if int(cls[i].item()) != CLASS_ID_TACTILE_PAVING:
                continue

            pts = np.asarray(masks.xy[i], dtype=np.int32)

            # ① 半透明填色（绿色）
            cv2.fillPoly(overlay, [pts], (0, 255, 0))

            # ② 画中线：逐行取中点连线
            # 创建二值掩膜图像
            mask_img = np.zeros((h, w), np.uint8)
            cv2.fillPoly(mask_img, [pts], 1)

            mid_points = []
            for y in range(h):
                xs = np.where(mask_img[y] > 0)[0]
                if len(xs) >= 2:
                    x_mid = int((xs[0] + xs[-1]) / 2)
                    mid_points.append((x_mid, y))

            if len(mid_points) >= 2:
                # 用折线连接所有中点 - 加粗显示
                pts_line = np.array(mid_points, dtype=np.int32)
                cv2.polylines(frame, [pts_line], False, (255, 255, 0), thickness=4)

        # 半透明叠加：overlay 占 30%，frame 占 70%
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    def process_frame(self, frame):
        """
        处理单帧图像：推理 → 绘制 → 计算指标
        
        处理流程：
        1. 使用 YOLO 模型进行实例分割推理
        2. 绘制盲道轮廓和中线
        3. 绘制画面垂直参考中线（橙色）
        4. 计算偏移量、方向角、面积占比等指标
        
        参数:
            frame: 当前帧（会被直接修改）
        
        返回:
            (frame, metrics)
            - frame: 绘制后的帧
            - metrics: 指标字典（新增 inference_time 字段）
        """
        try:
            # YOLO 推理（使用 MPS 加速，适用于 Apple Silicon）
            t_start = time.time()
            results = self.model.predict(frame, device="mps", verbose=False)
            inference_time = (time.time() - t_start) * 1000  # 毫秒
            result = results[0]

            # 绘制盲道轮廓和中线
            masks = result.masks
            if masks is not None:
                cls = result.boxes.cls
                self.draw_tactile_paving(frame, masks, cls)

            # 画参考中线（画面垂直中线）- 橙色加粗
            h, w = frame.shape[:2]
            center_x = w // 2
            cv2.line(frame, (center_x, 0), (center_x, h), (0, 165, 255), thickness=4, lineType=cv2.LINE_AA)

            # 计算指标
            metrics = analyze(frame, result)
            metrics["inference_time"] = inference_time  # 添加推理耗时
            return frame, metrics
            
        except Exception as e:
            # 推理失败时返回原始帧和错误指标
            print(f"❌ 帧推理失败: {e}")
            h, w = frame.shape[:2]
            error_metrics = {
                "count": 0,
                "offset": None,
                "angle": None,
                "area": 0.0,
                "area_ratio": 0.0,
                "state": "推理错误",
                "direction": "无",
                "valid": False,
                "invalid_reason": f"推理异常: {str(e)}",
                "is_single_frame": False,
                "inference_time": 0.0,
            }
            # 在帧上绘制错误提示
            cv2.putText(frame, f"Error: {str(e)[:50]}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return frame, error_metrics

    def run(self):
        """
        线程主循环，start() 后自动运行
        
        根据输入源类型执行不同逻辑：
        - 图片：读一次、推理一次、发送一次，结束
        - 视频：逐帧读取、推理、发送，直到视频结束或收到停止信号
        - 摄像头：持续读取、推理、发送，直到收到停止信号
        """
        # 判断输入源类型
        if self.is_camera:
            # ===== 摄像头实时输入 =====
            try:
                cap = cv2.VideoCapture(self.source)
                if not cap.isOpened():
                    print(f"❌ 无法打开摄像头（设备索引: {self.source}）")
                    return
                
                self.recorder.fps = 30.0  # 摄像头默认帧率
                while self.runFlag:
                    try:
                        success, frame = cap.read()
                        if not success:
                            print("⚠️ 摄像头读取失败")
                            break

                        frame, metrics = self.process_frame(frame)
                        metrics["is_single_frame"] = False
                        self.recorder.writeFrame(frame)
                        self.done_signal.emit(frame, metrics)
                    except Exception as e:
                        print(f"❌ 摄像头帧处理异常: {e}")
                        continue

                cap.release()
                self.recorder.closeWriter()
            except Exception as e:
                print(f"❌ 摄像头初始化失败: {e}")
            
        else:
            # ===== 文件输入（图片或视频） =====
            try:
                ext = os.path.splitext(self.source)[1].lower()

                # 图片：读一次、推一次、发一次，结束
                if ext in IMAGE_EXTS:
                    try:
                        frame = cv2.imread(self.source)
                        if frame is not None:
                            frame, metrics = self.process_frame(frame)
                            metrics["is_single_frame"] = True
                            self.done_signal.emit(frame, metrics)
                        else:
                            print(f"❌ 无法读取图片文件: {self.source}")
                    except Exception as e:
                        print(f"❌ 图片处理失败: {e}")
                    return

                # 视频：逐帧循环
                try:
                    cap = cv2.VideoCapture(self.source)
                    if not cap.isOpened():
                        print(f"❌ 无法打开视频文件: {self.source}")
                        return
                        
                    self.recorder.fps = cap.get(cv2.CAP_PROP_FPS)  # 读取源视频帧率
                    while self.runFlag:
                        try:
                            success, frame = cap.read()
                            if not success:
                                break

                            frame, metrics = self.process_frame(frame)
                            metrics["is_single_frame"] = False
                            self.recorder.writeFrame(frame)  # 画完就写
                            self.done_signal.emit(frame, metrics)
                        except Exception as e:
                            print(f"❌ 视频帧处理异常: {e}")
                            continue

                    cap.release()
                    self.recorder.closeWriter()  # 收尾：不 release 文件打不开
                except Exception as e:
                    print(f"❌ 视频处理失败: {e}")
            except Exception as e:
                print(f"❌ 文件处理异常: {e}")