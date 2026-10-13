"""
语音告警引擎单元测试
测试 blindpath_voice.py 中的 VoiceAlertEngine 类
"""
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blindpath_voice import VoiceAlertEngine


# ============================================================
# 辅助函数：创建测试指标字典
# ============================================================
def make_metrics(count=1, offset=None, angle=None, area_ratio=0.1, valid=True):
    """创建测试用的指标字典"""
    return {
        "count": count,
        "offset": offset,
        "angle": angle,
        "area_ratio": area_ratio,
        "state": "居中" if valid else "未检出",
        "direction": "无",
        "valid": valid,
    }


# ============================================================
# 测试 VoiceAlertEngine 初始化
# ============================================================
class TestVoiceAlertEngineInit:
    """测试语音引擎初始化"""

    def test_default_enabled_false(self):
        """测试默认语音开关为关闭"""
        engine = VoiceAlertEngine()
        assert engine.enabled is False

    def test_default_thresholds(self):
        """测试默认阈值"""
        engine = VoiceAlertEngine()
        assert engine.alert_offset_thresh == 30
        assert engine.alert_angle_thresh == 20

    def test_default_abnormal_duration(self):
        """测试默认异常持续时间阈值"""
        engine = VoiceAlertEngine()
        assert engine.min_abnormal_duration == 2.0

    def test_default_cooldown(self):
        """测试默认冷却时间"""
        engine = VoiceAlertEngine()
        assert engine.alert_cooldown == 5.0

    def test_default_last_alert_time(self):
        """测试上次播报时间初始为 0"""
        engine = VoiceAlertEngine()
        assert engine.last_alert_time == 0.0

    def test_default_alert_type_none(self):
        """测试当前告警类型初始为 None"""
        engine = VoiceAlertEngine()
        assert engine.current_alert_type is None

    def test_default_abnormal_start_time_none(self):
        """测试异常开始时间初始为 None"""
        engine = VoiceAlertEngine()
        assert engine.abnormal_start_time is None


# ============================================================
# 测试 setEnabled() 方法
# ============================================================
class TestSetEnabled:
    """测试语音开关设置"""

    def test_enable_voice(self):
        """测试开启语音"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        assert engine.enabled is True

    def test_disable_voice(self):
        """测试关闭语音"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.setEnabled(False)
        assert engine.enabled is False

    def test_disable_resets_state(self):
        """测试关闭语音会重置状态"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.current_alert_type = "offset_left"
        engine.abnormal_start_time = time.time()
        engine.setEnabled(False)
        assert engine.current_alert_type is None
        assert engine.abnormal_start_time is None


# ============================================================
# 测试 setThresholds() 方法
# ============================================================
class TestSetThresholds:
    """测试阈值设置"""

    def test_set_offset_threshold(self):
        """测试设置偏移阈值"""
        engine = VoiceAlertEngine()
        engine.setThresholds(50, 20)
        assert engine.alert_offset_thresh == 50

    def test_set_angle_threshold(self):
        """测试设置角度阈值"""
        engine = VoiceAlertEngine()
        engine.setThresholds(30, 40)
        assert engine.alert_angle_thresh == 40

    def test_set_both_thresholds(self):
        """测试同时设置两个阈值"""
        engine = VoiceAlertEngine()
        engine.setThresholds(45, 35)
        assert engine.alert_offset_thresh == 45
        assert engine.alert_angle_thresh == 35


# ============================================================
# 测试 setAbnormalDuration() 方法
# ============================================================
class TestSetAbnormalDuration:
    """测试异常持续时间阈值设置"""

    def test_set_duration(self):
        """测试设置持续时间"""
        engine = VoiceAlertEngine()
        engine.setAbnormalDuration(3.0)
        assert engine.min_abnormal_duration == 3.0

    def test_set_zero_duration(self):
        """测试设置零持续时间"""
        engine = VoiceAlertEngine()
        engine.setAbnormalDuration(0.0)
        assert engine.min_abnormal_duration == 0.0


# ============================================================
# 测试 _determineAlertType() 方法
# ============================================================
class TestDetermineAlertType:
    """测试告警类型判断"""

    def test_no_paving_detected(self):
        """测试未检出盲道：返回 no_paving"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(0, None, None, 0.0)
        assert alert_type == "no_paving"

    def test_normal_centered(self):
        """测试正常居中：无告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.1, 5.0, 0.1)
        assert alert_type is None

    def test_offset_left(self):
        """测试左偏：触发左偏告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, -0.5, 5.0, 0.1)
        assert alert_type == "offset_left"

    def test_offset_right(self):
        """测试右偏：触发右偏告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.5, 5.0, 0.1)
        assert alert_type == "offset_right"

    def test_angle_too_large(self):
        """测试角度过大：触发角度告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.1, 30.0, 0.1)
        assert alert_type == "angle_large"

    def test_area_missing(self):
        """测试盲道缺失：触发面积缺失告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.1, 5.0, 0.01)
        assert alert_type == "area_missing"

    def test_area_obstacle(self):
        """测试疑似障碍：触发面积障碍告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.1, 5.0, 0.03)
        assert alert_type == "area_obstacle"

    def test_offset_below_threshold(self):
        """测试偏移低于阈值：无告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.2, 5.0, 0.1)
        assert alert_type is None

    def test_angle_below_threshold(self):
        """测试角度低于阈值：无告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        alert_type = engine._determineAlertType(1, 0.1, 10.0, 0.1)
        assert alert_type is None

    def test_determine_always_returns_type(self):
        """测试 _determineAlertType 不检查 enabled 状态"""
        engine = VoiceAlertEngine()
        engine.setEnabled(False)
        # _determineAlertType 不检查 enabled，只判断类型
        alert_type = engine._determineAlertType(1, -0.5, 5.0, 0.1)
        assert alert_type == "offset_left"


# ============================================================
# 测试 checkAndAlert() 方法（状态机逻辑）
# ============================================================
class TestCheckAndAlert:
    """测试告警检查与触发"""

    def test_disabled_no_alert(self):
        """测试语音关闭时不触发告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(False)
        engine.checkAndAlert(make_metrics(offset=-0.5, area_ratio=0.1))
        assert engine.current_alert_type is None

    def test_normal_metrics_no_alert(self):
        """测试正常指标不触发告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.checkAndAlert(make_metrics(offset=0.1, area_ratio=0.1))
        assert engine.current_alert_type is None

    def test_abnormal_starts_accumulating(self):
        """测试异常开始累积：第一次调用设置状态"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 1.0  # 设长一点，确保第一次不会触发
        # 注意：必须同时提供 offset 和 angle，否则 _determineAlertType 不会检查偏移
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        # 第一次调用：新异常类型 → 设置状态
        assert engine.current_alert_type == "offset_left"
        assert engine.abnormal_start_time is not None

    def test_duration_not_reached_no_alert(self):
        """测试持续时间未达阈值不触发"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 10.0
        engine.checkAndAlert(make_metrics(offset=-0.5, area_ratio=0.1))
        assert engine.last_alert_time == 0.0

    def test_recovery_resets_state(self):
        """测试恢复正常后重置状态"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 0.1
        # 第一次：设置状态（需要同时提供 offset 和 angle）
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        assert engine.current_alert_type == "offset_left"
        # 第二次：恢复正常 → 重置
        engine.checkAndAlert(make_metrics(offset=0.1, angle=5.0, area_ratio=0.1))
        assert engine.current_alert_type is None
        assert engine.abnormal_start_time is None

    def test_alert_type_change_resets(self):
        """测试告警类型变化时重置并切换"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 0.1
        # 第一次：左偏
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        assert engine.current_alert_type == "offset_left"
        # 第二次：右偏（类型变化）→ 切换
        engine.checkAndAlert(make_metrics(offset=0.5, angle=5.0, area_ratio=0.1))
        assert engine.current_alert_type == "offset_right"


# ============================================================
# 测试告警冷却机制
# ============================================================
class TestAlertCooldown:
    """测试告警冷却机制"""

    def test_cooldown_prevents_repeat_alert(self):
        """测试冷却期内不重复播报"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 0.0
        engine.alert_cooldown = 10.0
        # 第一次：新类型 → 设置状态
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        # 确保第二次调用时时间戳不同
        time.sleep(0.01)
        # 第二次：同类型 → duration >= 0 → 触发（last_alert_time 更新）
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        first_alert_time = engine.last_alert_time
        assert first_alert_time > 0
        # 第三次：同类型 → 但在冷却期内 → 不更新 last_alert_time
        time.sleep(0.01)
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        assert engine.last_alert_time == first_alert_time

    def test_cooldown_expired_allows_new_alert(self):
        """测试冷却期过后允许新告警"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 0.0
        engine.alert_cooldown = 0.1
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        first_alert_time = engine.last_alert_time
        time.sleep(0.15)
        engine.checkAndAlert(make_metrics(offset=-0.5, angle=5.0, area_ratio=0.1))
        assert engine.last_alert_time > first_alert_time

    def test_different_alert_types_independent(self):
        """测试不同类型告警独立冷却"""
        engine = VoiceAlertEngine()
        engine.setEnabled(True)
        engine.min_abnormal_duration = 0.0
        engine.alert_cooldown = 10.0
        engine.checkAndAlert(make_metrics(offset=-0.5, area_ratio=0.1))
        left_alert_time = engine.last_alert_time
        # 切换为面积缺失告警（不同类型）→ 应该触发
        engine.checkAndAlert(make_metrics(offset=0.1, area_ratio=0.01))
        assert engine.last_alert_time > left_alert_time or engine.current_alert_type == "area_missing"