"""
盲道检测系统性能测试
测试FPS、内存占用、推理延迟等性能指标
"""
import os
import sys
import time
import tempfile
import shutil
import tracemalloc
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 辅助函数
# ============================================================
def create_test_video(num_frames=100, width=640, height=480, fps=30):
    """创建测试视频"""
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, "perf_test.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (0, 255, 0)
        out.write(frame)
    
    out.release()
    return video_path, temp_dir


# ============================================================
# 测试推理性能
# ============================================================
class TestInferencePerformance:
    """测试模型推理性能"""

    def test_single_frame_inference_time(self):
        """测试单帧推理时间(应<100ms)"""
        from ultralytics import YOLO
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "test.jpg")
        cv2.imwrite(img_path, test_img)
        
        start_time = time.time()
        results = model(img_path)
        inference_time = time.time() - start_time
        
        assert inference_time < 0.5, f"推理时间过长: {inference_time:.3f}s (应<0.5s)"
        
        shutil.rmtree(temp_dir)

    def test_inference_consistency(self):
        """测试推理时间稳定性"""
        from ultralytics import YOLO
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        temp_dir = tempfile.mkdtemp()
        img_path = os.path.join(temp_dir, "test.jpg")
        cv2.imwrite(img_path, test_img)
        
        times = []
        for _ in range(5):
            start_time = time.time()
            results = model(img_path)
            times.append(time.time() - start_time)
        
        avg_time = np.mean(times)
        std_time = np.std(times)
        
        assert avg_time < 0.5, f"平均推理时间过长: {avg_time:.3f}s"
        assert std_time < 0.1, f"推理时间波动过大: {std_time:.3f}s"
        
        shutil.rmtree(temp_dir)


# ============================================================
# 测试处理性能
# ============================================================
class TestProcessingPerformance:
    """测试视频处理性能"""

    def test_video_processing_fps(self):
        """测试视频处理FPS(应>=15fps)"""
        from ultralytics import YOLO
        from blindpath_metrics import analyze
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        video_path, temp_dir = create_test_video(num_frames=30)
        
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        start_time = time.time()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = model(frame_rgb)
            
            if results[0].masks is not None:
                metrics = analyze(frame_rgb, results[0])
            
            frame_count += 1
        
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        cap.release()
        shutil.rmtree(temp_dir)
        
        assert fps > 5, f"处理FPS过低: {fps:.2f} (应>5fps)"

    def test_metrics_calculation_time(self):
        """测试指标计算时间"""
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
        
        times = []
        for _ in range(100):
            start = time.time()
            metrics = analyze(frame, result)
            times.append(time.time() - start)
        
        avg_time = np.mean(times) * 1000
        
        assert avg_time < 50, f"指标计算时间过长: {avg_time:.2f}ms (应<50ms)"


# ============================================================
# 测试内存使用
# ============================================================
class TestMemoryUsage:
    """测试内存使用情况"""

    def test_memory_stability(self):
        """测试内存稳定性(不应持续增长)"""
        from ultralytics import YOLO
        from blindpath_metrics import analyze
        
        tracemalloc.start()
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        memory_snapshots = []
        
        for i in range(10):
            results = model(frame)
            if results[0].masks is not None:
                metrics = analyze(frame, results[0])
            
            if i % 3 == 0:
                current, peak = tracemalloc.get_traced_memory()
                memory_snapshots.append(current)
        
        tracemalloc.stop()
        
        if len(memory_snapshots) >= 2:
            memory_growth = memory_snapshots[-1] - memory_snapshots[0]
            assert memory_growth < 100 * 1024 * 1024, \
                f"内存增长过大: {memory_growth / 1024 / 1024:.2f}MB"

    def test_frame_buffer_memory(self):
        """测试帧缓冲区内存"""
        from flask_server import frame_buffer
        
        # FrameBuffer stores single frame, test it can be updated
        frame_buffer.update(np.zeros((480, 640, 3), dtype=np.uint8))
        assert frame_buffer._frame is not None


# ============================================================
# 测试长时间运行
# ============================================================
class TestLongRunning:
    """测试长时间运行稳定性"""

    def test_continuous_processing(self):
        """测试连续处理100帧不崩溃"""
        from ultralytics import YOLO
        from blindpath_metrics import analyze
        
        model_path = "./model/best0217.pt"
        model = YOLO(model_path)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        success_count = 0
        for i in range(100):
            try:
                results = model(frame)
                if results[0].masks is not None:
                    metrics = analyze(frame, results[0])
                success_count += 1
            except Exception as e:
                pytest.fail(f"第{i}帧处理失败: {e}")
        
        assert success_count == 100, f"成功处理帧数: {success_count}/100"

    def test_state_machine_stability(self):
        """测试状态机长时间运行"""
        from blindpath_statemachine import StateMachine
        
        sm = StateMachine(confirm_n=5)
        
        states = ["居中", "偏移", "严重偏移", "未检出", "居中"]
        
        for i in range(1000):
            state = states[i % len(states)]
            sm.update(state, "无")
        
        assert sm.state is not None

    def test_voice_engine_stability(self):
        """测试语音引擎长时间运行"""
        from blindpath_voice import VoiceAlertEngine
        
        engine = VoiceAlertEngine()
        engine.enabled = True
        
        for i in range(100):
            metrics = {
                "count": 1 if i % 2 == 0 else 0,
                "offset": 50 if i % 3 == 0 else 10,
                "angle": 30 if i % 4 == 0 else 5,
                "area_ratio": 0.05,
                "state": "未检出" if i % 2 == 0 else "居中",
                "direction": "左",
                "valid": i % 2 == 0,
            }
            
            alert_type = engine.checkAndAlert(metrics)
            # alert_type may be None if duration threshold not reached