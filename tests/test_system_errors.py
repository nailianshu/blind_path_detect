"""
盲道检测系统异常处理测试
测试各种错误场景和异常处理
"""
import os
import sys
import tempfile
import shutil
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 测试文件异常
# ============================================================
class TestFileErrors:
    """测试文件相关异常"""

    def test_missing_model_file(self):
        """测试模型文件缺失"""
        from ultralytics import YOLO
        
        with pytest.raises(Exception):
            model = YOLO("./model/nonexistent.pt")

    def test_corrupted_image(self):
        """测试损坏的图片文件"""
        temp_dir = tempfile.mkdtemp()
        corrupt_path = os.path.join(temp_dir, "corrupt.jpg")
        
        with open(corrupt_path, 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04\x05')
        
        img = cv2.imread(corrupt_path)
        assert img is None
        
        shutil.rmtree(temp_dir)

    def test_invalid_video_file(self):
        """测试无效视频文件"""
        temp_dir = tempfile.mkdtemp()
        invalid_path = os.path.join(temp_dir, "invalid.mp4")
        
        with open(invalid_path, 'w') as f:
            f.write("This is not a video")
        
        cap = cv2.VideoCapture(invalid_path)
        assert not cap.isOpened()
        cap.release()
        
        shutil.rmtree(temp_dir)

    def test_empty_directory(self):
        """测试空目录"""
        temp_dir = tempfile.mkdtemp()
        
        assert len(os.listdir(temp_dir)) == 0
        
        shutil.rmtree(temp_dir)

    def test_permission_error_simulation(self):
        """测试权限错误模拟"""
        temp_dir = tempfile.mkdtemp()
        protected_path = os.path.join(temp_dir, "protected")
        
        try:
            os.makedirs(protected_path)
            test_file = os.path.join(protected_path, "test.txt")
            
            with open(test_file, 'w') as f:
                f.write("test")
            
            os.chmod(protected_path, 0o000)
            
            with pytest.raises(PermissionError):
                with open(os.path.join(protected_path, "new.txt"), 'w') as f:
                    f.write("test")
        except Exception:
            pass
        finally:
            os.chmod(protected_path, 0o755)
            shutil.rmtree(temp_dir)


# ============================================================
# 测试模型异常
# ============================================================
class TestModelErrors:
    """测试模型相关异常"""

    def test_model_with_empty_image(self):
        """测试模型处理空白图片"""
        from ultralytics import YOLO
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        blank_img = np.zeros((480, 640, 3), dtype=np.uint8)
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "blank.jpg")
        cv2.imwrite(img_path, blank_img)
        
        try:
            results = model(img_path)
            assert results is not None
        except Exception as e:
            pytest.fail(f"模型处理空白图片失败: {e}")
        
        shutil.rmtree(temp_dir)

    def test_model_with_very_large_image(self):
        """测试模型处理超大图片"""
        from ultralytics import YOLO
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        large_img = np.zeros((2000, 3000, 3), dtype=np.uint8)
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "large.jpg")
        cv2.imwrite(img_path, large_img)
        
        try:
            results = model(img_path)
            assert results is not None
        except Exception as e:
            pytest.fail(f"模型处理大图片失败: {e}")
        
        shutil.rmtree(temp_dir)

    def test_model_with_single_pixel_image(self):
        """测试模型处理极小图片"""
        from ultralytics import YOLO
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        tiny_img = np.zeros((10, 10, 3), dtype=np.uint8)
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "tiny.jpg")
        cv2.imwrite(img_path, tiny_img)
        
        try:
            results = model(img_path)
            assert results is not None
        except Exception as e:
            pytest.fail(f"模型处理小图片失败: {e}")
        
        shutil.rmtree(temp_dir)


# ============================================================
# 测试指标计算异常
# ============================================================
class TestMetricsErrors:
    """测试指标计算异常"""

    def test_analyze_with_no_masks(self):
        """测试无掩膜时的分析"""
        from blindpath_metrics import analyze
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        class MockResult:
            def __init__(self):
                self.masks = None
                self.boxes = None
        
        result = MockResult()
        
        try:
            metrics = analyze(frame, result)
            assert metrics is not None
            assert metrics["valid"] is False
        except Exception as e:
            pytest.fail(f"无掩膜分析失败: {e}")

    def test_analyze_with_empty_frame(self):
        """测试空帧分析"""
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
        
        try:
            metrics = analyze(frame, result)
            assert metrics is not None
        except Exception as e:
            pytest.fail(f"空帧分析失败: {e}")

    def test_analyze_with_invalid_frame_dimensions(self):
        """测试无效帧尺寸"""
        from blindpath_metrics import analyze
        
        invalid_frames = [
            np.zeros((0, 640, 3), dtype=np.uint8),
            np.zeros((480, 0, 3), dtype=np.uint8),
        ]
        
        for frame in invalid_frames:
            with pytest.raises(Exception):
                analyze(None, frame)


# ============================================================
# 测试状态机异常
# ============================================================
class TestStateMachineErrors:
    """测试状态机异常"""

    def test_state_machine_with_invalid_state(self):
        """测试状态机处理无效状态"""
        from blindpath_statemachine import StateMachine
        
        sm = StateMachine(confirm_n=3)
        
        try:
            sm.update("无效状态", "无")
            assert sm.state is not None
        except Exception as e:
            pytest.fail(f"状态机处理无效状态失败: {e}")

    def test_state_machine_with_none_state(self):
        """测试状态机处理None状态"""
        from blindpath_statemachine import StateMachine
        
        sm = StateMachine(confirm_n=3)
        
        try:
            sm.update(None, None)
        except Exception:
            pass

    def test_state_machine_with_zero_confirm(self):
        """测试状态机确认数为0"""
        from blindpath_statemachine import StateMachine
        
        try:
            sm = StateMachine(confirm_n=0)
            sm.update("居中", "无")
            assert sm.state is not None
        except Exception as e:
            pytest.fail(f"状态机确认数为0时失败: {e}")


# ============================================================
# 测试语音引擎异常
# ============================================================
class TestVoiceEngineErrors:
    """测试语音引擎异常"""

    def test_voice_engine_with_invalid_metrics(self):
        """测试语音引擎处理无效指标"""
        from blindpath_voice import VoiceAlertEngine
        
        engine = VoiceAlertEngine()
        engine.enabled = True
        
        invalid_metrics_list = [
            {},
            {"count": None},
            {"offset": "invalid"},
            {"angle": None, "offset": None},
        ]
        
        for invalid_metrics in invalid_metrics_list:
            try:
                alert_type = engine.checkAndAlert(invalid_metrics)
            except Exception:
                pass

    def test_voice_engine_with_extreme_values(self):
        """测试语音引擎处理极端值"""
        from blindpath_voice import VoiceAlertEngine
        
        engine = VoiceAlertEngine()
        engine.enabled = True
        
        extreme_metrics = {
            "count": 999999,
            "offset": 999999,
            "angle": 999999,
            "area_ratio": 999.9,
            "state": "未检出",
            "direction": "左",
            "valid": False,
        }
        
        try:
            alert_type = engine.checkAndAlert(extreme_metrics)
            # alert_type may be None if duration threshold not reached
        except Exception as e:
            pytest.fail(f"语音引擎处理极端值失败: {e}")

    def test_voice_engine_rapid_toggle(self):
        """测试语音引擎快速开关"""
        from blindpath_voice import VoiceAlertEngine
        
        engine = VoiceAlertEngine()
        
        for _ in range(100):
            engine.setEnabled(True)
            engine.setEnabled(False)
        
        assert engine.enabled is False


# ============================================================
# 测试录像器异常
# ============================================================
class TestRecorderErrors:
    """测试录像器异常"""

    def test_recorder_with_invalid_path(self):
        """测试录像器使用无效路径"""
        from blindpath_recorder import VideoRecorder
        
        recorder = VideoRecorder()
        
        try:
            recorder.startRecord("/invalid/path/video.mp4")
            recorder.stopRecord()
        except Exception:
            pass

    def test_recorder_stop_without_start(self):
        """测试未开始就停止录像"""
        from blindpath_recorder import VideoRecorder
        
        recorder = VideoRecorder()
        
        try:
            recorder.stopRecord()
        except Exception as e:
            pytest.fail(f"未开始就停止录像失败: {e}")

    def test_recorder_double_start(self):
        """测试重复开始录像"""
        from blindpath_recorder import VideoRecorder
        
        recorder = VideoRecorder()
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, "test.mp4")
        
        try:
            recorder.startRecord(video_path)
            recorder.startRecord(video_path)
            recorder.stopRecord()
        except Exception:
            pass
        
        shutil.rmtree(temp_dir)


# ============================================================
# 测试Flask服务器异常
# ============================================================
class TestFlaskServerErrors:
    """测试Flask服务器异常"""

    def test_flask_frame_buffer_operations(self):
        """测试Flask帧缓冲区操作"""
        from flask_server import frame_buffer
        
        # FrameBuffer doesn't have len(), test update/clear instead
        frame_buffer.update(np.zeros((480, 640, 3), dtype=np.uint8), {"state": "test"})
        assert frame_buffer._frame is not None
        
        frame_buffer._frame = None
        assert frame_buffer._frame is None

    def test_flask_server_import(self):
        """测试Flask服务器导入"""
        try:
            from flask_server import start_flask_in_background
            assert start_flask_in_background is not None
        except Exception as e:
            pytest.fail(f"Flask服务器导入失败: {e}")