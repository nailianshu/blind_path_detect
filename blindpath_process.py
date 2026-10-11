import os
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from ultralytics import YOLO

from blindpath_metrics import analyze
from blindpath_recorder import VideoRecorder


# 图片扩展名（用来和视频分流）
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

# 推理线程（组合 metrics + recorder）
class MyBlindPathProcess(QThread):
    """视频/图片读取 + YOLO分割推理子线程"""
    done_signal = pyqtSignal(np.ndarray, object)   # (帧, 指标字典)

    def __init__(self, model, source):
        super().__init__()
        self.runFlag = True
        self.model = model            # 模型由外面传入，只加载一次
        self.source = source          # 要处理的素材路径
        self.recorder = VideoRecorder()

    def stop(self):
        """设置标志，退出线程循环"""
        self.runFlag = False

    def startRecord(self, out_path):
        self.recorder.startRecord(out_path)

    def stopRecord(self):
        self.recorder.stopRecord()

    def draw_tactile_paving(self, frame, masks, cls):
        """对盲道实例填色 + 画中线"""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        for i in range(len(masks.xy)):
            if int(cls[i].item()) != 80:
                continue

            pts = np.asarray(masks.xy[i], dtype=np.int32)

            # ① 半透明填色（绿色）
            cv2.fillPoly(overlay, [pts], (0, 255, 0))

            # ② 画中线：逐行取中点连线
            mask_img = np.zeros((h, w), np.uint8)
            cv2.fillPoly(mask_img, [pts], 1)

            mid_points = []
            for y in range(h):
                xs = np.where(mask_img[y] > 0)[0]
                if len(xs) >= 2:
                    x_mid = int((xs[0] + xs[-1]) / 2)
                    mid_points.append((x_mid, y))

            if len(mid_points) >= 2:
                # 用折线连接所有中点 - 加粗
                pts_line = np.array(mid_points, dtype=np.int32)
                cv2.polylines(frame, [pts_line], False, (255, 255, 0), thickness=4)

        # 半透明叠加
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    def process_frame(self, frame):
        """推理 → 画轮廓 + 填色 + 画中线 → 算指标，返回 (画好的帧, 指标dict)"""
        results = self.model.predict(frame, device="mps", verbose=False)
        result = results[0]

        masks = result.masks
        if masks is not None:
            cls = result.boxes.cls
            self.draw_tactile_paving(frame, masks, cls)

        # 画参考中线（画面垂直中线）- 加粗
        h, w = frame.shape[:2]
        center_x = w // 2
        cv2.line(frame, (center_x, 0), (center_x, h), (0, 165, 255), thickness=4, lineType=cv2.LINE_AA)

        return frame, analyze(frame, result)

    def run(self):
        """线程主循环，start() 后自动运行"""
        ext = os.path.splitext(self.source)[1].lower()

        # ===== 图片：读一次、推一次、发一次，结束 =====
        if ext in IMAGE_EXTS:
            frame = cv2.imread(self.source)
            if frame is not None:
                frame, metrics = self.process_frame(frame)
                metrics["is_single_frame"] = True
                self.done_signal.emit(frame, metrics)
            return

        # ===== 视频：逐帧循环 =====
        cap = cv2.VideoCapture(self.source)
        self.recorder.fps = cap.get(cv2.CAP_PROP_FPS)           # ★ 读源视频帧率
        while self.runFlag:
            success, frame = cap.read()
            if not success:
                break

            frame, metrics = self.process_frame(frame)
            metrics["is_single_frame"] = False
            self.recorder.writeFrame(frame)                     # ★ 画完就写
            self.done_signal.emit(frame, metrics)

        cap.release()
        self.recorder.closeWriter()                             # ★ 收尾：不 release 文件打不开