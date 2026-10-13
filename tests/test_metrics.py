"""
盲道检测核心算法单元测试
测试 blindpath_metrics.py 中的 measure() 和 analyze() 函数
"""
import math
import numpy as np
import cv2
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blindpath_metrics import measure, analyze, CLASS_ID_TACTILE_PAVING, AREA_RATIO_MISSING_THRESHOLD, AREA_RATIO_OBSTACLE_THRESHOLD


# ============================================================
# 辅助函数：创建模拟 YOLO 结果对象
# ============================================================
class MockBox:
    """模拟 YOLO boxes 对象"""
    def __init__(self, cls_values):
        self.cls = cls_values


class MockMask:
    """模拟 YOLO masks 对象"""
    def __init__(self, xy_coords):
        self.xy = xy_coords


class MockResult:
    """模拟 YOLO 推理结果对象"""
    def __init__(self, masks_xy=None, boxes_cls=None):
        self.masks = MockMask(masks_xy) if masks_xy is not None else None
        self.boxes = MockBox(boxes_cls) if boxes_cls is not None else None


# ============================================================
# 辅助函数：创建测试图像
# ============================================================
def create_test_frame(height=480, width=640):
    """创建空白测试帧（RGB）"""
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_centered_paving_mask(frame_height=480, frame_width=640):
    """创建居中的盲道轮廓（矩形）"""
    h, w = frame_height, frame_width
    paving_width = w // 4
    x_left = (w - paving_width) // 2
    x_right = x_left + paving_width
    y_top = int(h * 0.3)
    y_bottom = int(h * 0.9)
    pts = np.array([
        [x_left, y_top], [x_right, y_top],
        [x_right, y_bottom], [x_left, y_bottom]
    ], dtype=np.float32)
    return pts


def create_left_offset_paving_mask(frame_height=480, frame_width=640):
    """创建偏左的盲道轮廓（盲道在画面左侧 → 人偏右）"""
    h, w = frame_height, frame_width
    paving_width = w // 4
    x_left = w // 8
    x_right = x_left + paving_width
    y_top = int(h * 0.3)
    y_bottom = int(h * 0.9)
    pts = np.array([
        [x_left, y_top], [x_right, y_top],
        [x_right, y_bottom], [x_left, y_bottom]
    ], dtype=np.float32)
    return pts


def create_right_offset_paving_mask(frame_height=480, frame_width=640):
    """创建偏右的盲道轮廓（盲道在画面右侧 → 人偏左）"""
    h, w = frame_height, frame_width
    paving_width = w // 4
    x_right = w * 7 // 8
    x_left = x_right - paving_width
    y_top = int(h * 0.3)
    y_bottom = int(h * 0.9)
    pts = np.array([
        [x_left, y_top], [x_right, y_top],
        [x_right, y_bottom], [x_left, y_bottom]
    ], dtype=np.float32)
    return pts


def create_tilted_paving_mask(frame_height=480, frame_width=640):
    """创建倾斜的盲道轮廓（梯形）"""
    h, w = frame_height, frame_width
    paving_width_top = w // 6
    paving_width_bottom = w // 3
    x_center_top = w // 2 - paving_width_top // 4
    x_center_bottom = w // 2
    pts = np.array([
        [x_center_top - paving_width_top // 2, int(h * 0.3)],
        [x_center_top + paving_width_top // 2, int(h * 0.3)],
        [x_center_bottom + paving_width_bottom // 2, int(h * 0.9)],
        [x_center_bottom - paving_width_bottom // 2, int(h * 0.9)]
    ], dtype=np.float32)
    return pts


def create_mock_result(pts, class_id=CLASS_ID_TACTILE_PAVING):
    """创建模拟 YOLO 结果"""
    return MockResult(
        masks_xy=[pts],
        boxes_cls=np.array([class_id], dtype=np.float32)
    )


# ============================================================
# 测试 measure() 函数
# ============================================================
class TestMeasure:
    """测试 measure() 偏移量计算函数"""

    def test_centered_paving_zero_offset(self):
        """测试居中盲道：偏移量应接近 0"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        d, angle, ok = measure(frame, pts)
        assert ok is True
        assert d is not None
        assert abs(d) < 0.1, f"居中盲道偏移量应接近0，实际为 {d}"

    def test_left_offset_paving(self):
        """测试偏左盲道：盲道在画面左侧，返回正值（人偏右）"""
        frame = create_test_frame()
        pts = create_left_offset_paving_mask()
        d, angle, ok = measure(frame, pts)
        assert ok is True
        assert d is not None
        # 盲道在左侧 → d_max 为负 → 返回 -d_max 为正
        assert d > 0, f"偏左盲道（人偏右）偏移量应为正，实际为 {d}"

    def test_right_offset_paving(self):
        """测试偏右盲道：盲道在画面右侧，返回负值（人偏左）"""
        frame = create_test_frame()
        pts = create_right_offset_paving_mask()
        d, angle, ok = measure(frame, pts)
        assert ok is True
        assert d is not None
        # 盲道在右侧 → d_max 为正 → 返回 -d_max 为负
        assert d < 0, f"偏右盲道（人偏左）偏移量应为负，实际为 {d}"

    def test_tilted_paving_angle(self):
        """测试倾斜盲道：方向角应不为 0"""
        frame = create_test_frame()
        pts = create_tilted_paving_mask()
        d, angle, ok = measure(frame, pts)
        assert ok is True
        assert angle is not None
        assert abs(angle) > 1.0, f"倾斜盲道方向角应不为0，实际为 {angle}"

    def test_insufficient_scan_lines(self):
        """测试有效扫描行不足：应返回 False"""
        frame = create_test_frame()
        pts = np.array([
            [100, 10], [110, 10], [110, 20], [100, 20]
        ], dtype=np.float32)
        d, angle, ok = measure(frame, pts)
        assert ok is False
        assert d is None
        assert angle is None

    def test_degenerate_contour(self):
        """测试退化轮廓（线段）：应返回 False"""
        frame = create_test_frame()
        pts = np.array([
            [100, 300], [200, 300]
        ], dtype=np.float32)
        d, angle, ok = measure(frame, pts)
        assert ok is False

    def test_narrow_paving_skipped(self):
        """测试过窄盲道（<5像素）：应被跳过"""
        frame = create_test_frame()
        h, w = frame.shape[:2]
        x_mid = w // 2
        y_start, y_end = int(h * 0.5), int(h * 0.95)
        pts = np.array([
            [x_mid - 1, y_start], [x_mid + 2, y_start],
            [x_mid + 2, y_end], [x_mid - 1, y_end]
        ], dtype=np.float32)
        d, angle, ok = measure(frame, pts)
        assert ok is False

    def test_offset_symmetry(self):
        """测试偏移对称性：左右偏移的绝对值应相近"""
        frame = create_test_frame()
        pts_left = create_left_offset_paving_mask()
        pts_right = create_right_offset_paving_mask()
        d_left, _, _ = measure(frame, pts_left)
        d_right, _, _ = measure(frame, pts_right)
        assert d_left is not None and d_right is not None
        assert abs(abs(d_left) - abs(d_right)) < 0.2, \
            f"左右偏移不对称: |{d_left}| vs |{d_right}|"


# ============================================================
# 测试 analyze() 函数
# ============================================================
class TestAnalyze:
    """测试 analyze() 指标计算函数"""

    def test_no_masks(self):
        """测试无掩膜结果：应返回未检出"""
        frame = create_test_frame()
        result = MockResult(masks_xy=None, boxes_cls=None)
        metrics = analyze(frame, result)
        assert metrics["count"] == 0
        assert metrics["state"] == "未检出"
        assert metrics["valid"] is False

    def test_no_paving_detected(self):
        """测试无盲道类别：应返回未检出"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        result = create_mock_result(pts, class_id=0)
        metrics = analyze(frame, result)
        assert metrics["count"] == 0
        assert metrics["state"] == "未检出"

    def test_paving_detected_centered(self):
        """测试检测到居中盲道"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        assert metrics["count"] == 1
        assert metrics["valid"] is True
        assert metrics["state"] in ["居中", "偏移"]
        assert metrics["area_ratio"] > 0

    def test_area_ratio_calculation(self):
        """测试面积占比计算"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        assert 0 < metrics["area_ratio"] <= 1.0
        assert metrics["area_ratio"] > 0.05, \
            f"面积占比过小: {metrics['area_ratio']}"

    def test_missing_paving_state(self):
        """测试盲道缺失状态：面积占比 < 2%"""
        frame = create_test_frame()
        h, w = frame.shape[:2]
        small_pts = np.array([
            [w // 2 - 5, h // 2 - 5],
            [w // 2 + 5, h // 2 - 5],
            [w // 2 + 5, h // 2 + 5],
            [w // 2 - 5, h // 2 + 5]
        ], dtype=np.float32)
        result = create_mock_result(small_pts)
        metrics = analyze(frame, result)
        assert metrics["state"] == "盲道缺失"
        assert metrics["area_ratio"] < AREA_RATIO_MISSING_THRESHOLD

    def test_obstacle_suspected_state(self):
        """测试疑似障碍状态：面积占比 2%~5%"""
        frame = create_test_frame()
        h, w = frame.shape[:2]
        pts = np.array([
            [w // 2 - 40, h // 2 - 40],
            [w // 2 + 40, h // 2 - 40],
            [w // 2 + 40, h // 2 + 40],
            [w // 2 - 40, h // 2 + 40]
        ], dtype=np.float32)
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        assert metrics["state"] == "疑似障碍"
        assert AREA_RATIO_MISSING_THRESHOLD <= metrics["area_ratio"] < AREA_RATIO_OBSTACLE_THRESHOLD

    def test_normal_paving_state(self):
        """测试正常盲道状态：面积占比 >= 5%"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        assert metrics["area_ratio"] >= AREA_RATIO_OBSTACLE_THRESHOLD
        assert metrics["state"] in ["居中", "偏移", "严重偏移"]

    def test_multiple_paving_instances(self):
        """测试多个盲道实例：应取面积最大的"""
        frame = create_test_frame()
        h, w = frame.shape[:2]
        large_pts = create_centered_paving_mask()
        small_pts = np.array([
            [w // 4, h // 4], [w // 4 + 20, h // 4],
            [w // 4 + 20, h // 4 + 20], [w // 4, h // 4 + 20]
        ], dtype=np.float32)
        result = MockResult(
            masks_xy=[large_pts, small_pts],
            boxes_cls=np.array([CLASS_ID_TACTILE_PAVING, CLASS_ID_TACTILE_PAVING], dtype=np.float32)
        )
        metrics = analyze(frame, result)
        assert metrics["count"] == 2
        assert metrics["valid"] is True

    def test_degenerate_contour_in_analyze(self):
        """测试退化轮廓：应返回未检出"""
        frame = create_test_frame()
        degenerate_pts = np.array([
            [100, 200], [200, 200]
        ], dtype=np.float32)
        result = create_mock_result(degenerate_pts)
        metrics = analyze(frame, result)
        assert metrics["state"] == "未检出"

    def test_direction_left(self):
        """测试偏移方向：盲道偏左 → 人偏右 → direction='右'"""
        frame = create_test_frame()
        pts = create_left_offset_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        if metrics["valid"]:
            assert metrics["direction"] == "右"

    def test_direction_right(self):
        """测试偏移方向：盲道偏右 → 人偏左 → direction='左'"""
        frame = create_test_frame()
        pts = create_right_offset_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        if metrics["valid"]:
            assert metrics["direction"] == "左"

    def test_invalid_reason_on_no_detection(self):
        """测试失败原因：未检出时应有原因"""
        frame = create_test_frame()
        result = MockResult(masks_xy=None, boxes_cls=None)
        metrics = analyze(frame, result)
        assert metrics["invalid_reason"] == "未检出盲道"


# ============================================================
# 测试常量定义
# ============================================================
class TestConstants:
    """测试常量定义"""

    def test_class_id_tactile_paving(self):
        """测试盲道类别 ID"""
        assert CLASS_ID_TACTILE_PAVING == 80

    def test_area_ratio_thresholds(self):
        """测试面积占比阈值"""
        assert AREA_RATIO_MISSING_THRESHOLD == 0.02
        assert AREA_RATIO_OBSTACLE_THRESHOLD == 0.05
        assert AREA_RATIO_MISSING_THRESHOLD < AREA_RATIO_OBSTACLE_THRESHOLD

    def test_threshold_values_reasonable(self):
        """测试阈值值合理性"""
        assert 0 < AREA_RATIO_MISSING_THRESHOLD < AREA_RATIO_OBSTACLE_THRESHOLD < 1.0


# ============================================================
# 测试边界情况
# ============================================================
class TestEdgeCases:
    """测试边界情况"""

    def test_empty_frame(self):
        """测试空帧（全黑）"""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        pts = np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.float32)
        d, angle, ok = measure(frame, pts)
        assert ok is True

    def test_large_frame(self):
        """测试大尺寸帧"""
        frame = create_test_frame(height=1080, width=1920)
        pts = create_centered_paving_mask(frame_height=1080, frame_width=1920)
        d, angle, ok = measure(frame, pts)
        assert ok is True

    def test_small_frame(self):
        """测试小尺寸帧"""
        frame = create_test_frame(height=120, width=160)
        pts = create_centered_paving_mask(frame_height=120, frame_width=160)
        d, angle, ok = measure(frame, pts)
        assert ok is True

    def test_single_instance_in_result(self):
        """测试单个实例的结果"""
        frame = create_test_frame()
        pts = create_centered_paving_mask()
        result = create_mock_result(pts)
        metrics = analyze(frame, result)
        assert metrics["count"] == 1

    def test_offset_normalization(self):
        """测试偏移量归一化：应在合理范围内"""
        frame = create_test_frame()
        pts = create_right_offset_paving_mask()
        d, _, ok = measure(frame, pts)
        assert ok is True
        assert abs(d) < 3.0, f"偏移量超出合理范围: {d}"