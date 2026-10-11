import os
import sys
import datetime

import numpy as np
import cv2
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QApplication, QFileDialog

from ultralytics import YOLO

from ui_blindpath_monitor import Ui_BlindPathMonitorForm
from blindpath_process import MyBlindPathProcess
from blindpath_statemachine import StateMachine
from blindpath_visual import apply_state_style, get_status_text
from blindpath_voice import VoiceAlertEngine
from flask_server import frame_buffer, start_flask_in_background


OUTPUT_DIR = './output'


class MyBlindPathMonitorForm(QWidget, Ui_BlindPathMonitorForm):
    """检测窗口"""

    voice_alert_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self.model = YOLO("./model/best0217.pt")

        self.current_frame = None
        self.current_metrics = None
        self.recording = False

        self.state_machine = StateMachine(confirm_n=5)

        self.voice_engine = VoiceAlertEngine()
        self.voice_alert_signal.connect(self.voice_engine._playVoice)

        if not self.voice_engine.use_system_tts and self.voice_engine.engine is None:
            print("⚠️ 语音引擎初始化失败，语音告警不可用")
            self.checkBox_voice_switch.setEnabled(False)
            self.label_operation.setText("语音引擎初始化失败，语音告警不可用")

        self.checkBox_voice_switch.stateChanged.connect(self._onVoiceSwitchChanged)
        self.slider_offset.valueChanged.connect(self._onOffsetThresholdChanged)
        self.slider_angle.valueChanged.connect(self._onAngleThresholdChanged)
        self.slider_interval.valueChanged.connect(self._onIntervalChanged)

        # 设置 LCD 数字显示为黑色
        palette = self.lcdNumber_distance.palette()
        palette.setColor(palette.WindowText, Qt.black)
        self.lcdNumber_distance.setPalette(palette)
        
        palette_angle = self.lcdNumber_angle.palette()
        palette_angle.setColor(palette_angle.WindowText, Qt.black)
        self.lcdNumber_angle.setPalette(palette_angle)

        # 设置标签文字为黑色（加粗）
        self.label.setStyleSheet("color: black; font-weight: bold; font-size: 14px;")
        self.label_3.setStyleSheet("color: black; font-weight: bold; font-size: 14px;")
        self.label_2.setStyleSheet("color: black; font-weight: bold; font-size: 14px;")

        # 启动 Flask 远程监视服务器
        print(" 正在启动 Flask 远程监视服务器...")
        start_flask_in_background(host='0.0.0.0', port=5000)

        self.processThread = None

    def _onVoiceSwitchChanged(self, state):
        enabled = state == Qt.Checked
        self.voice_engine.setEnabled(enabled)
        if not enabled:
            self.voice_engine.bad_frame_counter = 0

    def _onOffsetThresholdChanged(self, value):
        self.label_offset_value.setText(f"{value}%")
        self.voice_engine.setThresholds(value, self.voice_engine.alert_angle_thresh)

    def _onAngleThresholdChanged(self, value):
        self.label_angle_value.setText(f"{value}°")
        self.voice_engine.setThresholds(self.voice_engine.alert_offset_thresh, value)

    def _onIntervalChanged(self, value):
        duration = value / 10.0
        self.label_interval_value.setText(f"{duration:.1f}s")
        self.voice_engine.setAbnormalDuration(duration)

    def startThread(self, source):
        """停掉旧线程，用新素材起一个新线程"""
        if self.processThread is not None:
            self.processThread.stop()
            if not self.processThread.wait(1000):
                print("⚠️ 旧线程 1 秒内未退出")

        self.recording = False
        self.pushButton_savevideo.setText("保存视频")
        self.label_operation.setText("")
        self.current_frame = None
        self.current_metrics = None
        self.state_machine.reset()
        
        if hasattr(self, 'voice_engine'):
            self.voice_engine.reset()

        self.processThread = MyBlindPathProcess(self.model, source)
        self.processThread.done_signal.connect(self.refreshFrame)
        self.processThread.start()

    def refreshFrame(self, frame: np.ndarray, metrics: dict):
        """主线程接收子线程信号，更新界面"""
        self.current_frame = frame
        self.current_metrics = metrics

        is_single = metrics.get("is_single_frame", False)

        if not metrics["valid"]:
            self.lcdNumber_distance.setEnabled(False)
            self.lcdNumber_angle.setEnabled(False)
            self.state_machine.reset()
            apply_state_style(self.label_info, metrics["state"])
            self.label_info.setText(get_status_text(metrics["state"], "无", 0, is_single))
        else:
            self.lcdNumber_distance.display(int(round(metrics["offset"] * 100)))
            self.lcdNumber_angle.display(int(round(metrics["angle"])))
            self.lcdNumber_distance.setEnabled(True)
            self.lcdNumber_angle.setEnabled(True)

            if is_single:
                display_state = metrics["state"]
                display_direction = metrics["direction"]
            else:
                self.state_machine.update(metrics["state"], metrics["direction"])

                confirmed_state = self.state_machine.state
                confirmed_direction = self.state_machine.direction

                if self.state_machine.candidate_state is not None:
                    display_state = "确认中"
                    display_direction = self.state_machine.candidate_direction
                else:
                    display_state = confirmed_state
                    display_direction = confirmed_direction

            offset_pct = int(round(abs(metrics["offset"]) * 100))
            apply_state_style(self.label_info, display_state)
            self.label_info.setText(get_status_text(display_state, display_direction, offset_pct, is_single))

        self.label_timestamp.setText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        height, width = frame.shape[0], frame.shape[1]
        q_image = QImage(frame.data, width, height, frame.strides[0], QImage.Format_RGB888)
        q_image = q_image.rgbSwapped()

        pixmap = QPixmap.fromImage(q_image)
        scaled_pix = pixmap.scaled(self.label_img.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.label_img.setPixmap(scaled_pix)

        if hasattr(self, 'voice_engine'):
            self.voice_engine.checkAndAlert(metrics)
        
        # 更新 Flask 帧缓冲（用于远程监视）
        frame_buffer.update(frame, metrics)

    def closeEvent(self, event):
        """窗口关闭时安全退出线程和释放语音资源"""
        if hasattr(self, 'voice_engine'):
            self.voice_engine.stop()
        
        if self.processThread is not None:
            self.processThread.stop()
            self.processThread.wait(1000)
        event.accept()

    def openVideoFile(self):
        """选择并打开视频/图片"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频或图片",
            "",
            "媒体文件 (*.mp4 *.avi *.mov *.mkv *.jpg *.jpeg *.png *.bmp);;"
            "视频 (*.mp4 *.avi *.mov *.mkv);;"
            "图片 (*.jpg *.jpeg *.png *.bmp)"
        )
        if not path:
            return
        self.startThread(path)

    def startWriteVideo(self):
        """保存视频：第一次点 = 开始录制，再点 = 停止"""
        if self.recording:
            self.processThread.stopRecord()
            self.recording = False
            self.pushButton_savevideo.setText("保存视频")
            self.label_operation.setText("已停止录制")
            return

        if self.processThread is None or not self.processThread.isRunning():
            self.label_operation.setText("当前没有正在播放的视频，无法录制")
            return

        name = datetime.datetime.now().strftime("blindpath_%Y%m%d_%H%M%S.mp4")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存标注视频", os.path.join(OUTPUT_DIR, name), "视频 (*.mp4)"
        )
        if not path:
            return
        if not path.lower().endswith('.mp4'):
            path += '.mp4'

        self.processThread.startRecord(path)
        self.recording = True
        self.pushButton_savevideo.setText("停止保存")
        self.label_operation.setText(f"录制中 → {os.path.basename(path)}")

    def writeSnapshot(self):
        """保存快照：把当前这一帧存成图片"""
        if self.current_frame is None:
            self.label_operation.setText("还没有画面，无法保存快照")
            return

        name = datetime.datetime.now().strftime("snapshot_%Y%m%d_%H%M%S.jpg")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存快照", os.path.join(OUTPUT_DIR, name), "图片 (*.jpg *.png)"
        )
        if not path:
            return

        ok = cv2.imwrite(path, self.current_frame)
        self.label_operation.setText("已保存快照" if ok else "快照保存失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MyBlindPathMonitorForm()
    w.show()
    sys.exit(app.exec_())