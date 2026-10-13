"""
状态可视化模块单元测试
测试 blindpath_visual.py 中的 apply_state_style() 和 get_status_text() 函数
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blindpath_visual import get_status_text, STATE_STYLES


# ============================================================
# 测试 STATE_STYLES 常量
# ============================================================
class TestStateStyles:
    """测试状态样式定义"""

    def test_all_states_defined(self):
        """测试所有状态都有样式定义"""
        expected_states = [
            "初始", "居中", "偏移", "严重偏移", "未检出",
            "无法测量", "确认中", "分析结束", "盲道缺失", "疑似障碍"
        ]
        for state in expected_states:
            assert state in STATE_STYLES, f"状态 '{state}' 缺少样式定义"

    def test_style_has_required_keys(self):
        """测试每个样式都有 bg 和 text 键"""
        for state, style in STATE_STYLES.items():
            assert "bg" in style, f"状态 '{state}' 缺少 'bg' 键"
            assert "text" in style, f"状态 '{state}' 缺少 'text' 键"

    def test_bg_color_is_qcolor(self):
        """测试背景色是 QColor 对象"""
        from PyQt5.QtGui import QColor
        for state, style in STATE_STYLES.items():
            assert isinstance(style["bg"], QColor), \
                f"状态 '{state}' 的 bg 不是 QColor 类型"

    def test_text_color_is_qcolor(self):
        """测试文字色是 QColor 对象"""
        from PyQt5.QtGui import QColor
        for state, style in STATE_STYLES.items():
            assert isinstance(style["text"], QColor), \
                f"状态 '{state}' 的 text 不是 QColor 类型"

    def test_warning_states_use_red_orange(self):
        """测试警告状态使用红色或橙色"""
        missing = STATE_STYLES["盲道缺失"]
        severe = STATE_STYLES["严重偏移"]
        assert missing["text"].red() > 150, "盲道缺失文字色应偏红"
        assert severe["text"].red() > 150, "严重偏移文字色应偏红"

    def test_normal_state_uses_green(self):
        """测试正常状态使用绿色"""
        centered = STATE_STYLES["居中"]
        assert centered["bg"].green() > 200, "居中背景色应偏绿"
        assert centered["text"].green() > 50, "居中文字色应有绿色分量"

    def test_obstacle_state_uses_orange(self):
        """测试疑似障碍状态使用橙色"""
        obstacle = STATE_STYLES["疑似障碍"]
        assert obstacle["bg"].red() > 200, "疑似障碍背景色红色分量应高"
        assert obstacle["bg"].green() > 150, "疑似障碍背景色绿色分量应中"


# ============================================================
# 测试 get_status_text() 函数
# ============================================================
class TestGetStatusText:
    """测试状态文字生成函数"""

    def test_initial_state(self):
        """测试初始状态文字"""
        text = get_status_text("初始", "无", 0)
        assert "等待" in text

    def test_centered_state(self):
        """测试居中状态文字"""
        text = get_status_text("居中", "无", 0)
        assert "对齐" in text or "居中" in text

    def test_offset_right_state(self):
        """测试右偏状态文字"""
        text = get_status_text("偏移", "右", 35)
        assert "右侧" in text
        assert "35" in text

    def test_offset_left_state(self):
        """测试左偏状态文字"""
        text = get_status_text("偏移", "左", 40)
        assert "左侧" in text
        assert "40" in text

    def test_severe_offset_state(self):
        """测试严重偏移状态文字"""
        text = get_status_text("严重偏移", "无", 100)
        assert "严重" in text or "偏转" in text

    def test_not_detected_state(self):
        """测试未检出状态文字"""
        text = get_status_text("未检出", "无", 0)
        assert "未检出" in text

    def test_unmeasurable_state(self):
        """测试无法测量状态文字"""
        text = get_status_text("无法测量", "无", 0)
        assert "无法测量" in text or "无法" in text

    def test_confirming_state_with_direction(self):
        """测试确认中状态（有方向）"""
        text = get_status_text("确认中", "右", 30)
        assert "确认中" in text
        assert "右侧" in text

    def test_confirming_state_without_direction(self):
        """测试确认中状态（无方向）"""
        text = get_status_text("确认中", "", 0)
        assert "确认中" in text

    def test_analysis_end_state(self):
        """测试分析结束状态文字"""
        text = get_status_text("分析结束", "无", 0)
        assert "分析结束" in text

    def test_missing_paving_state(self):
        """测试盲道缺失状态文字"""
        text = get_status_text("盲道缺失", "无", 0)
        assert "缺失" in text or "过低" in text

    def test_obstacle_suspected_state(self):
        """测试疑似障碍状态文字"""
        text = get_status_text("疑似障碍", "无", 0)
        assert "障碍" in text or "遮挡" in text

    def test_single_frame_prefix(self):
        """测试单帧模式前缀"""
        text = get_status_text("居中", "无", 0, is_single_frame=True)
        assert "【单帧】" in text

    def test_multi_frame_no_prefix(self):
        """测试多帧模式无前缀"""
        text = get_status_text("居中", "无", 0, is_single_frame=False)
        assert "【单帧】" not in text

    def test_unknown_state_returns_state_name(self):
        """测试未知状态返回状态名称本身"""
        text = get_status_text("未知状态", "无", 0)
        assert text == "未知状态"


# ============================================================
# 测试 apply_state_style() 函数（使用 QApplication fixture）
# ============================================================
class TestApplyStateStyle:
    """测试状态样式应用函数"""

    @pytest.fixture(autouse=True)
    def setup_qapp(self):
        """每个测试前创建 QApplication"""
        from PyQt5.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        yield
        # 测试后不销毁 QApplication（避免多次创建问题）

    def test_apply_style_sets_stylesheet(self):
        """测试应用样式会设置 stylesheet"""
        from PyQt5.QtWidgets import QLabel
        from blindpath_visual import apply_state_style
        label = QLabel()
        apply_state_style(label, "居中")
        style = label.styleSheet()
        assert "background-color" in style
        assert "color" in style

    def test_apply_style_unknown_state_uses_default(self):
        """测试未知状态使用默认样式"""
        from PyQt5.QtWidgets import QLabel
        from blindpath_visual import apply_state_style
        label = QLabel()
        apply_state_style(label, "未知状态")
        style = label.styleSheet()
        assert "background-color" in style

    def test_apply_style_warning_state_has_red(self):
        """测试警告状态样式包含红色"""
        from PyQt5.QtWidgets import QLabel
        from blindpath_visual import apply_state_style
        label = QLabel()
        apply_state_style(label, "盲道缺失")
        style = label.styleSheet()
        assert "rgb(255" in style or "rgb(180" in style

    def test_apply_style_normal_state_has_green(self):
        """测试正常状态样式包含绿色"""
        from PyQt5.QtWidgets import QLabel
        from blindpath_visual import apply_state_style
        label = QLabel()
        apply_state_style(label, "居中")
        style = label.styleSheet()
        assert "rgb(220, 255, 220)" in style

    def test_apply_style_all_states(self):
        """测试所有状态都能正常应用"""
        from PyQt5.QtWidgets import QLabel
        from blindpath_visual import apply_state_style
        for state in STATE_STYLES.keys():
            label = QLabel()
            apply_state_style(label, state)
            style = label.styleSheet()
            assert len(style) > 0, f"状态 '{state}' 样式为空"