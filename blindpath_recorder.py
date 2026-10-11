import cv2

# 视频录制（VideoRecorder 类）
class VideoRecorder:
    """视频录制器：懒创建 writer，按需写帧"""

    def __init__(self):
        self.recording = False
        self.out_path = None
        self.writer = None
        self.fps = 25.0

    def startRecord(self, out_path):
        """开始录制：只挂开关，writer 留给子线程下一帧创建"""
        self.out_path = out_path
        self.recording = True

    def stopRecord(self):
        """停止录制：只关开关，release 留给子线程做"""
        self.recording = False

    def closeWriter(self):
        """释放 writer —— ★ 只能在子线程里调用"""
        if self.writer is not None:
            self.writer.release()
            self.writer = None

    def writeFrame(self, frame):
        """按需把这一帧写进输出视频"""
        if self.recording:
            if self.writer is None:                    # 懒创建：用当前帧尺寸
                h, w = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                fps = self.fps if self.fps and self.fps > 0 else 25.0
                self.writer = cv2.VideoWriter(self.out_path, fourcc, fps, (w, h))
                if not self.writer.isOpened():
                    print(f"❌ 打开 VideoWriter 失败：{self.out_path}")
            self.writer.write(frame)
        elif self.writer is not None:
            self.closeWriter()                         # 刚停止录制 → 收尾