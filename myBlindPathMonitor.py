import os
import sys
import time
import datetime

import numpy as np
import cv2
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QApplication, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QMessageBox

from ultralytics import YOLO

from ui_blindpath_monitor import Ui_BlindPathMonitorForm
from blindpath_process import MyBlindPathProcess
from blindpath_statemachine import StateMachine
from blindpath_visual import apply_state_style, get_status_text
from blindpath_voice import VoiceAlertEngine
from flask_server import frame_buffer, start_flask_in_background


OUTPUT_DIR = './output'


class CameraSelectDialog(QDialog):
    """摄像头选择对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择摄像头")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        
        # 摄像头列表
        self.combo = QComboBox()
        # 默认添加 0-3 号摄像头
        for i in range(4):
            self.combo.addItem(f"摄像头 {i}")
        layout.addWidget(QLabel("请选择摄像头设备："))
        layout.addWidget(self.combo)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def getCameraIndex(self):
        """返回选中的摄像头索引"""
        return self.combo.currentIndex()


class MyBlindPathMonitorForm(QWidget, Ui_BlindPathMonitorForm):
    """检测窗口"""

    voice_alert_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 加载 YOLO 模型，带错误处理
        try:
            self.model = YOLO("./model/best0217.pt")
            print("✅ 模型加载成功")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            # 显示错误提示
            QMessageBox.critical(
                self,
                "模型加载失败",
                f"无法加载模型文件:\n./model/best0217.pt\n\n错误信息: {str(e)}\n\n程序将无法进行推理。"
            )
            self.model = None  # 设置为 None，后续操作会检查

        self.current_frame = None
        self.current_metrics = None
        self.recording = False

        # FPS 和性能监控
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.fps_display = 0.0
        self.inference_times = []  # 最近10帧的推理耗时

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
        try:
            start_flask_in_background(host='0.0.0.0', port=5000)
        except Exception as e:
            print(f"⚠️ Flask 服务器启动失败: {e}")

        self.processThread = None
        self.imageAnalysisWindow = None  # 图片分析窗口实例

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
        # 检查模型是否加载成功
        if self.model is None:
            QMessageBox.warning(
                self,
                "模型未加载",
                "模型加载失败，无法进行推理。\n请检查模型文件是否存在。"
            )
            return
        
        # 停止旧线程
        if self.processThread is not None:
            self.processThread.stop()
            # 等待线程退出，带降级处理
            if not self.processThread.wait(2000):
                print("⚠️ 旧线程 2 秒内未退出，尝试再次等待")
                if not self.processThread.wait(1000):
                    print("❌ 旧线程未能正常退出")

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

        # 计算 FPS（每秒帧数）
        self.fps_counter += 1
        now = time.time()
        elapsed = now - self.fps_last_time
        if elapsed >= 1.0:  # 每秒更新一次 FPS
            self.fps_display = self.fps_counter / elapsed
            self.fps_counter = 0
            self.fps_last_time = now

        # 记录推理耗时（保留最近10帧）
        inf_time = metrics.get("inference_time", 0.0)
        if inf_time > 0:
            self.inference_times.append(inf_time)
            if len(self.inference_times) > 10:
                self.inference_times.pop(0)

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

        # 更新 FPS 和推理耗时显示
        avg_inf_time = sum(self.inference_times) / len(self.inference_times) if self.inference_times else 0
        fps_text = f"FPS: {self.fps_display:.1f} | 推理: {avg_inf_time:.1f}ms"
        self.label_fps.setText(fps_text)

        if hasattr(self, 'voice_engine'):
            self.voice_engine.checkAndAlert(metrics)
        
        # 更新 Flask 帧缓冲（用于远程监视）
        frame_buffer.update(frame, metrics)

    def closeEvent(self, event):
        """窗口关闭时安全退出线程和释放语音资源"""
        # 停止语音引擎
        if hasattr(self, 'voice_engine'):
            try:
                self.voice_engine.stop()
            except Exception as e:
                print(f"⚠️ 语音引擎停止时出错: {e}")
        
        # 安全退出处理线程
        if self.processThread is not None:
            self.processThread.stop()
            # 等待线程退出，最多等待 2 秒
            if not self.processThread.wait(2000):
                print("⚠️ 处理线程 2 秒内未退出，尝试强制终止")
                # 降级处理：再次尝试等待 1 秒
                if not self.processThread.wait(1000):
                    print("❌ 处理线程未能正常退出，可能存在资源泄漏")
        
        # 关闭图片分析窗口（如果存在）
        if self.imageAnalysisWindow is not None:
            try:
                self.imageAnalysisWindow.close()
            except Exception as e:
                print(f"⚠️ 关闭图片分析窗口时出错: {e}")
        
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

    def openCamera(self):
        """打开摄像头选择对话框，选择后启动摄像头"""
        dialog = CameraSelectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            camera_index = dialog.getCameraIndex()
            self.label_operation.setText(f"正在打开摄像头 {camera_index}...")
            self.startThread(camera_index)

    def openImageAnalysis(self):
        """打开图片分析窗口"""
        if self.imageAnalysisWindow is None or not self.imageAnalysisWindow.isVisible():
            self.imageAnalysisWindow = ImageAnalysisForm(self.model)
            self.imageAnalysisWindow.show()
        else:
            self.imageAnalysisWindow.raise_()
            self.imageAnalysisWindow.activateWindow()

    def startWriteVideo(self):
        """保存视频：第一次点 = 开始录制，再点 = 停止"""
        if self.recording:
            try:
                self.processThread.stopRecord()
                self.recording = False
                self.pushButton_savevideo.setText("保存视频")
                self.label_operation.setText("已停止录制")
            except Exception as e:
                print(f"❌ 停止录制失败: {e}")
                self.label_operation.setText(f"停止录制失败: {e}")
            return

        if self.processThread is None or not self.processThread.isRunning():
            self.label_operation.setText("当前没有正在播放的视频，无法录制")
            return

        try:
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
        except Exception as e:
            print(f"❌ 启动录制失败: {e}")
            self.label_operation.setText(f"启动录制失败: {e}")

    def writeSnapshot(self):
        """保存快照：把当前这一帧存成图片"""
        if self.current_frame is None:
            self.label_operation.setText("还没有画面，无法保存快照")
            return

        try:
            name = datetime.datetime.now().strftime("snapshot_%Y%m%d_%H%M%S.jpg")
            path, _ = QFileDialog.getSaveFileName(
                self, "保存快照", os.path.join(OUTPUT_DIR, name), "图片 (*.jpg *.png)"
            )
            if not path:
                return

            ok = cv2.imwrite(path, self.current_frame)
            self.label_operation.setText("已保存快照" if ok else "快照保存失败")
        except Exception as e:
            print(f"❌ 保存快照失败: {e}")
            self.label_operation.setText(f"保存快照失败: {e}")


class ImageAnalysisForm(QWidget):
    """
    图片分析专用窗口
    
    功能：
    - 只能导入图片进行分析
    - 左边显示原图，右边显示结果图（对比查看）
    - 显示盲道在画面中的占比（面积百分比）
    - 显示是否偏离参考线
    - 显示检测状态和详细信息
    """
    
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.original_frame = None  # 原始图片
        self.result_frame = None    # 结果图片
        self.current_metrics = None
        
        # 检查模型是否可用
        if self.model is None:
            QMessageBox.warning(
                self,
                "模型未加载",
                "模型加载失败，图片分析功能不可用。"
            )
        
        self.setWindowTitle("盲道图片分析")
        self.resize(1200, 700)
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 图片对比显示区域（左右布局）
        image_layout = QHBoxLayout()
        
        # 左侧：原图
        left_layout = QVBoxLayout()
        left_label = QLabel("原图")
        left_label.setStyleSheet("font-size: 14px; font-weight: bold; color: black;")
        left_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(left_label)
        
        self.label_original = QLabel("点击'选择图片'开始分析")
        self.label_original.setMinimumSize(500, 400)
        self.label_original.setAlignment(Qt.AlignCenter)
        self.label_original.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        left_layout.addWidget(self.label_original)
        
        image_layout.addLayout(left_layout)
        
        # 右侧：结果图
        right_layout = QVBoxLayout()
        right_label = QLabel("结果图")
        right_label.setStyleSheet("font-size: 14px; font-weight: bold; color: black;")
        right_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(right_label)
        
        self.label_result = QLabel("等待分析...")
        self.label_result.setMinimumSize(500, 400)
        self.label_result.setAlignment(Qt.AlignCenter)
        self.label_result.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        right_layout.addWidget(self.label_result)
        
        image_layout.addLayout(right_layout)
        
        main_layout.addLayout(image_layout)
        
        # 指标显示区域
        metrics_layout = QVBoxLayout()
        
        # 面积占比
        area_layout = QHBoxLayout()
        area_layout.addWidget(QLabel("盲道面积占比:"))
        self.label_area = QLabel("0.00%")
        self.label_area.setStyleSheet("font-size: 16px; font-weight: bold; color: black;")
        area_layout.addWidget(self.label_area)
        area_layout.addStretch()
        metrics_layout.addLayout(area_layout)
        
        # 偏移量
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("偏移量:"))
        self.label_offset = QLabel("无")
        self.label_offset.setStyleSheet("font-size: 16px; font-weight: bold; color: black;")
        offset_layout.addWidget(self.label_offset)
        offset_layout.addStretch()
        metrics_layout.addLayout(offset_layout)
        
        # 方向角
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("方向角:"))
        self.label_angle = QLabel("无")
        self.label_angle.setStyleSheet("font-size: 16px; font-weight: bold; color: black;")
        angle_layout.addWidget(self.label_angle)
        angle_layout.addStretch()
        metrics_layout.addLayout(angle_layout)
        
        # 状态
        state_layout = QHBoxLayout()
        state_layout.addWidget(QLabel("检测状态:"))
        self.label_state = QLabel("未检测")
        self.label_state.setStyleSheet("font-size: 16px; font-weight: bold; color: black;")
        self.label_state.setAlignment(Qt.AlignCenter)
        state_layout.addWidget(self.label_state)
        state_layout.addStretch()
        metrics_layout.addLayout(state_layout)
        
        # 详细信息
        detail_layout = QHBoxLayout()
        detail_layout.addWidget(QLabel("详细信息:"))
        self.label_detail = QLabel("")
        self.label_detail.setStyleSheet("font-size: 14px; color: #333;")
        self.label_detail.setWordWrap(True)
        detail_layout.addWidget(self.label_detail)
        metrics_layout.addLayout(detail_layout)
        
        main_layout.addLayout(metrics_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_select = QPushButton("选择图片")
        self.btn_select.clicked.connect(self.selectImage)
        self.btn_select.setStyleSheet("padding: 8px 20px; font-size: 14px;")
        btn_layout.addWidget(self.btn_select)
        
        self.btn_save = QPushButton("保存结果")
        self.btn_save.clicked.connect(self.saveResult)
        self.btn_save.setStyleSheet("padding: 8px 20px; font-size: 14px;")
        btn_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
    
    def selectImage(self):
        """选择并分析图片"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if not path:
            return
        
        self.analyzeImage(path)
    
    def analyzeImage(self, image_path):
        """
        分析单张图片
        
        流程：
        1. 读取图片并保存原图
        2. YOLO 推理
        3. 绘制盲道轮廓和中线（结果图）
        4. 计算指标（面积占比、偏移量、方向角）
        5. 左右对比显示原图和结果图
        """
        # 检查模型是否可用
        if self.model is None:
            QMessageBox.warning(self, "错误", "模型未加载，无法进行分析")
            return
        
        try:
            # 读取图片
            frame = cv2.imread(image_path)
            if frame is None:
                QMessageBox.warning(self, "错误", f"无法读取图片: {image_path}")
                return
            
            # 保存原图
            self.original_frame = frame.copy()
            
            # YOLO 推理
            results = self.model.predict(frame, device="mps", verbose=False)
            result = results[0]
            
            # 绘制盲道轮廓和中线（结果图）
            masks = result.masks
            if masks is not None:
                cls = result.boxes.cls
                self.draw_tactile_paving(frame, masks, cls)
            
            # 画参考中线
            h, w = frame.shape[:2]
            center_x = w // 2
            cv2.line(frame, (center_x, 0), (center_x, h), (0, 165, 255), thickness=4, lineType=cv2.LINE_AA)
            
            # 保存结果图
            self.result_frame = frame
            
            # 计算指标
            from blindpath_metrics import analyze
            metrics = analyze(frame, result)
            
            self.current_metrics = metrics
            
            # 显示原图和结果图
            self.displayOriginalFrame(self.original_frame)
            self.displayResultFrame(self.result_frame)
            
            # 更新指标显示
            self.updateMetrics(metrics)
            
        except Exception as e:
            QMessageBox.critical(self, "分析失败", f"图片分析过程中发生错误:\n{str(e)}")
            print(f"❌ 图片分析失败: {e}")
    
    def draw_tactile_paving(self, frame, masks, cls):
        """绘制盲道轮廓和中线"""
        from blindpath_metrics import CLASS_ID_TACTILE_PAVING
        
        overlay = frame.copy()
        h, w = frame.shape[:2]

        for i in range(len(masks.xy)):
            if int(cls[i].item()) != CLASS_ID_TACTILE_PAVING:
                continue

            pts = np.asarray(masks.xy[i], dtype=np.int32)

            # 半透明填色（绿色）
            cv2.fillPoly(overlay, [pts], (0, 255, 0))

            # 画中线
            mask_img = np.zeros((h, w), np.uint8)
            cv2.fillPoly(mask_img, [pts], 1)

            mid_points = []
            for y in range(h):
                xs = np.where(mask_img[y] > 0)[0]
                if len(xs) >= 2:
                    x_mid = int((xs[0] + xs[-1]) / 2)
                    mid_points.append((x_mid, y))

            if len(mid_points) >= 2:
                pts_line = np.array(mid_points, dtype=np.int32)
                cv2.polylines(frame, [pts_line], False, (255, 255, 0), thickness=4)

        # 半透明叠加
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
    
    def displayOriginalFrame(self, frame):
        """在 label_original 上显示原图"""
        height, width = frame.shape[:2]
        q_image = QImage(frame.data, width, height, frame.strides[0], QImage.Format_RGB888)
        q_image = q_image.rgbSwapped()
        
        pixmap = QPixmap.fromImage(q_image)
        scaled_pix = pixmap.scaled(self.label_original.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.label_original.setPixmap(scaled_pix)
    
    def displayResultFrame(self, frame):
        """在 label_result 上显示结果图"""
        height, width = frame.shape[:2]
        q_image = QImage(frame.data, width, height, frame.strides[0], QImage.Format_RGB888)
        q_image = q_image.rgbSwapped()
        
        pixmap = QPixmap.fromImage(q_image)
        scaled_pix = pixmap.scaled(self.label_result.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.label_result.setPixmap(scaled_pix)
    
    def displayFrame(self, frame):
        """在 label_img 上显示图片（兼容旧方法）"""
        height, width = frame.shape[:2]
        q_image = QImage(frame.data, width, height, frame.strides[0], QImage.Format_RGB888)
        q_image = q_image.rgbSwapped()
        
        pixmap = QPixmap.fromImage(q_image)
        scaled_pix = pixmap.scaled(self.label_result.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.label_result.setPixmap(scaled_pix)
    
    def updateMetrics(self, metrics):
        """更新指标显示"""
        # 面积占比
        area_ratio = metrics.get("area_ratio", 0.0)
        self.label_area.setText(f"{area_ratio * 100:.2f}%")
        
        # 根据面积占比设置颜色
        if area_ratio < 0.02:
            self.label_area.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        elif area_ratio < 0.05:
            self.label_area.setStyleSheet("font-size: 16px; font-weight: bold; color: orange;")
        else:
            self.label_area.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        
        # 偏移量
        offset = metrics.get("offset")
        if offset is not None:
            self.label_offset.setText(f"{offset * 100:.1f}%")
        else:
            self.label_offset.setText("无法计算")
        
        # 方向角
        angle = metrics.get("angle")
        if angle is not None:
            self.label_angle.setText(f"{angle:.1f}°")
        else:
            self.label_angle.setText("无法计算")
        
        # 状态
        state = metrics.get("state", "未知")
        self.label_state.setText(state)
        apply_state_style(self.label_state, state)
        
        # 详细信息
        direction = metrics.get("direction", "无")
        count = metrics.get("count", 0)
        invalid_reason = metrics.get("invalid_reason")
        
        detail_text = f"检测到 {count} 个盲道实例"
        if metrics.get("valid"):
            detail_text += f" | 方向: {direction}"
        if invalid_reason:
            detail_text += f"\n原因: {invalid_reason}"
        
        self.label_detail.setText(detail_text)
    
    def saveResult(self):
        """保存分析结果图片"""
        if self.result_frame is None:
            QMessageBox.warning(self, "提示", "请先选择图片进行分析")
            return
        
        name = datetime.datetime.now().strftime("analysis_%Y%m%d_%H%M%S.jpg")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存分析结果", os.path.join(OUTPUT_DIR, name), "图片 (*.jpg *.png)"
        )
        if not path:
            return
        
        ok = cv2.imwrite(path, self.result_frame)
        if ok:
            QMessageBox.information(self, "成功", f"已保存分析结果到:\n{path}")
        else:
            QMessageBox.warning(self, "错误", "保存失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MyBlindPathMonitorForm()
    w.show()
    sys.exit(app.exec_())