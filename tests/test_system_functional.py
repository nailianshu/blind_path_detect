"""
盲道检测系统功能测试
测试完整的系统功能流程,包括UI、输入源、核心功能等
"""
import os
import sys
import time
import tempfile
import shutil
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 辅助函数：创建测试媒体文件
# ============================================================
def create_test_image(width=640, height=480, color=(0, 255, 0)):
    """创建测试图片"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = color
    return img


def create_test_video(num_frames=30, width=640, height=480):
    """创建测试视频"""
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, "test_video.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 30.0, (width, height))
    
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (0, 255, 0)
        out.write(frame)
    
    out.release()
    return video_path, temp_dir


# ============================================================
# 测试系统启动
# ============================================================
class TestSystemStartup:
    """测试系统启动流程"""

    def test_model_file_exists(self):
        """测试模型文件是否存在"""
        model_path = "./model/best0217.pt"
        assert os.path.exists(model_path), f"模型文件不存在: {model_path}"

    def test_model_loadable(self):
        """测试模型能否正常加载"""
        from ultralytics import YOLO
        model_path = "./model/best0217.pt"
        try:
            model = YOLO(model_path)
            assert model is not None
        except Exception as e:
            pytest.fail(f"模型加载失败: {e}")

    def test_output_directory_created(self):
        """测试输出目录能否正常创建"""
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "test_output")
        os.makedirs(output_path, exist_ok=True)
        assert os.path.exists(output_path)
        shutil.rmtree(temp_dir)

    def test_required_modules_importable(self):
        """测试所有必需模块能否导入"""
        try:
            from blindpath_metrics import measure, analyze
            from blindpath_visual import apply_state_style, get_status_text
            from blindpath_voice import VoiceAlertEngine
            from blindpath_process import MyBlindPathProcess
            from blindpath_statemachine import StateMachine
            from blindpath_recorder import VideoRecorder
        except ImportError as e:
            pytest.fail(f"模块导入失败: {e}")


# ============================================================
# 测试输入源处理
# ============================================================
class TestMediaInput:
    """测试不同输入源的处理"""

    def test_image_file_readable(self):
        """测试图片文件能否读取"""
        test_img = create_test_image()
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "test.jpg")
        cv2.imwrite(img_path, test_img)
        
        img = cv2.imread(img_path)
        assert img is not None
        assert img.shape == (480, 640, 3)
        
        shutil.rmtree(temp_dir)

    def test_video_file_readable(self):
        """测试视频文件能否读取"""
        video_path, temp_dir = create_test_video(num_frames=10)
        
        cap = cv2.VideoCapture(video_path)
        assert cap.isOpened()
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
        
        cap.release()
        assert frame_count == 10
        
        shutil.rmtree(temp_dir)

    def test_invalid_file_handling(self):
        """测试无效文件处理"""
        cap = cv2.VideoCapture("nonexistent_file.mp4")
        assert not cap.isOpened()
        cap.release()

    def test_empty_image_handling(self):
        """测试空图片处理"""
        temp_dir = tempfile.mkdtemp()
        empty_path = os.path.join(temp_dir, "empty.txt")
        with open(empty_path, 'w') as f:
            f.write("")
        
        img = cv2.imread(empty_path)
        assert img is None
        
        shutil.rmtree(temp_dir)


# ============================================================
# 测试核心功能模块
# ============================================================
class TestCoreFeatures:
    """测试核心功能"""

    def test_state_machine_initialization(self):
        """测试状态机初始化"""
        from blindpath_statemachine import StateMachine
        sm = StateMachine(confirm_n=5)
        assert sm is not None
        assert sm.CONFIRM_N == 5
        assert sm.state == "初始"

    def test_voice_engine_initialization(self):
        """测试语音引擎初始化"""
        from blindpath_voice import VoiceAlertEngine
        engine = VoiceAlertEngine()
        assert engine is not None
        assert engine.enabled is False

    def test_video_recorder_initialization(self):
        """测试录像器初始化"""
        from blindpath_recorder import VideoRecorder
        recorder = VideoRecorder()
        assert recorder is not None
        assert recorder.recording is False

    def test_metrics_analyze_with_valid_data(self):
        """测试指标分析功能"""
        from blindpath_metrics import analyze
        from blindpath_metrics import CLASS_ID_TACTILE_PAVING
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        class MockBox:
            def __init__(self):
                self.cls = np.array([CLASS_ID_TACTILE_PAVING])
        
        class MockMask:
            def __init__(self):
                pts = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
                self.xy = [pts]
        
        class MockResult:
            def __init__(self):
                self.boxes = MockBox()
                self.masks = MockMask()
        
        result = MockResult()
        metrics = analyze(frame, result)
        
        assert metrics is not None
        assert "state" in metrics
        assert "count" in metrics

    def test_visual_status_text_generation(self):
        """测试状态文本生成"""
        from blindpath_visual import get_status_text
        
        text = get_status_text("居中", "无", 5, False)
        assert "对齐" in text
        
        text = get_status_text("偏移", "右", 50, False)
        assert "偏移" in text or "右侧" in text

    def test_visual_style_application(self):
        """测试样式应用"""
        from blindpath_visual import apply_state_style, STATE_STYLES
        
        assert "居中" in STATE_STYLES
        assert "bg" in STATE_STYLES["居中"]
        assert "text" in STATE_STYLES["居中"]


# ============================================================
# 测试端到端流程
# ============================================================
class TestEndToEnd:
    """测试端到端完整流程"""

    def test_full_detection_pipeline(self):
        """测试完整检测流程"""
        from ultralytics import YOLO
        from blindpath_metrics import analyze
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        test_img = create_test_image()
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "test.jpg")
        cv2.imwrite(img_path, test_img)
        
        results = model(img_path)
        assert results is not None
        assert len(results) > 0
        
        result = results[0]
        frame = cv2.imread(img_path)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        metrics = analyze(frame, result)
        assert metrics is not None
        
        shutil.rmtree(temp_dir)

    def test_state_machine_transitions(self):
        """测试状态机转换"""
        from blindpath_statemachine import StateMachine
        
        sm = StateMachine(confirm_n=3)
        
        initial_state = sm.state
        assert initial_state == "初始"
        
        for _ in range(3):
            sm.update("居中", "无")
        
        assert sm.state == "居中"

    def test_voice_alert_flow(self):
        """测试语音告警流程"""
        from blindpath_voice import VoiceAlertEngine
        
        engine = VoiceAlertEngine()
        engine.enabled = True
        
        metrics = {
            "count": 0,
            "offset": 50,
            "angle": 30,
            "area_ratio": 0.05,
            "state": "未检出",
            "direction": "无",
            "valid": False,
        }
        
        alert_type = engine.checkAndAlert(metrics)
        # alert_type may be None if duration threshold not reached, which is expected


# ============================================================
# 测试数据完整性
# ============================================================
class TestDataIntegrity:
    """测试数据完整性"""

    def test_model_directory_exists(self):
        """测试模型目录存在"""
        assert os.path.exists("./model")

    def test_model_file_not_empty(self):
        """测试模型文件不为空"""
        model_path = "./model/best0217.pt"
        assert os.path.getsize(model_path) > 0

    def test_icons_directory_exists(self):
        """测试图标目录存在"""
        assert os.path.exists("./icons")

    def test_templates_directory_exists(self):
        """测试模板目录存在"""
        assert os.path.exists("./templates")

    def test_flask_template_exists(self):
        """测试Flask模板文件存在"""
        assert os.path.exists("./templates/index.html")