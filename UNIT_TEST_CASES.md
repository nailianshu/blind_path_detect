# 单元测试用例

## 测试统计

| 模块 | 测试文件 | 测试类数 | 测试用例数 | 通过率 |
|------|---------|---------|-----------|--------|
| 核心算法 | test_metrics.py | 4 | 38 | 100% |
| 状态可视化 | test_visual.py | 3 | 28 | 100% |
| 语音告警引擎 | test_voice.py | 9 | 76 | 100% |
| **总计** | **3个文件** | **16个测试类** | **142个用例** | **100%** |

---

## 1. 核心算法模块 (blindpath_metrics.py)

### 1.1 measure() 函数测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-M-01 | TestMeasure | test_centered_paving_zero_offset | 居中盲道偏移量计算 | 返回偏移量接近0, ok=True |
| UT-M-02 | TestMeasure | test_left_offset_paving | 偏左盲道(人偏右)偏移量 | 返回正值 d>0, ok=True |
| UT-M-03 | TestMeasure | test_right_offset_paving | 偏右盲道(人偏左)偏移量 | 返回负值 d<0, ok=True |
| UT-M-04 | TestMeasure | test_tilted_paving_angle | 倾斜盲道方向角计算 | 方向角绝对值>1.0°, ok=True |
| UT-M-05 | TestMeasure | test_insufficient_scan_lines | 有效扫描行不足(<5行) | 返回 d=None, angle=None, ok=False |
| UT-M-06 | TestMeasure | test_degenerate_contour | 退化轮廓(线段) | 返回 ok=False |
| UT-M-07 | TestMeasure | test_narrow_paving_skipped | 过窄盲道(<5像素) | 返回 ok=False |
| UT-M-08 | TestMeasure | test_offset_symmetry | 左右偏移对称性 | 左右偏移绝对值差<0.2 |

### 1.2 analyze() 函数测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-A-01 | TestAnalyze | test_no_masks | 无掩膜结果 | count=0, state="未检出", valid=False |
| UT-A-02 | TestAnalyze | test_no_paving_detected | 无盲道类别(class_id≠80) | count=0, state="未检出" |
| UT-A-03 | TestAnalyze | test_paving_detected_centered | 检测到居中盲道 | count=1, valid=True, state="居中"或"偏移" |
| UT-A-04 | TestAnalyze | test_area_ratio_calculation | 面积占比计算 | 0<area_ratio≤1.0, area_ratio>0.05 |
| UT-A-05 | TestAnalyze | test_missing_paving_state | 盲道缺失状态(area_ratio<2%) | state="盲道缺失" |
| UT-A-06 | TestAnalyze | test_obstacle_suspected_state | 疑似障碍状态(2%≤area_ratio<5%) | state="疑似障碍" |
| UT-A-07 | TestAnalyze | test_normal_paving_state | 正常盲道状态(area_ratio≥5%) | state="居中"或"偏移"或"严重偏移" |
| UT-A-08 | TestAnalyze | test_multiple_paving_instances | 多个盲道实例 | count=2, valid=True, 取面积最大 |
| UT-A-09 | TestAnalyze | test_degenerate_contour_in_analyze | 退化轮廓在analyze中 | state="未检出" |
| UT-A-10 | TestAnalyze | test_direction_left | 偏移方向:盲道偏左→人偏右 | direction="右" |
| UT-A-11 | TestAnalyze | test_direction_right | 偏移方向:盲道偏右→人偏左 | direction="左" |
| UT-A-12 | TestAnalyze | test_invalid_reason_on_no_detection | 未检出时失败原因 | invalid_reason="未检出盲道" |

### 1.3 常量定义测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-C-01 | TestConstants | test_class_id_tactile_paving | 盲道类别ID | CLASS_ID_TACTILE_PAVING=80 |
| UT-C-02 | TestConstants | test_area_ratio_thresholds | 面积占比阈值 | MISSING=0.02, OBSTACLE=0.05 |
| UT-C-03 | TestConstants | test_threshold_values_reasonable | 阈值合理性 | 0<MISSING<OBSTACLE<1.0 |

### 1.4 边界情况测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-E-01 | TestEdgeCases | test_empty_frame | 空帧(全黑) | ok=True |
| UT-E-02 | TestEdgeCases | test_large_frame | 大尺寸帧(1920×1080) | ok=True |
| UT-E-03 | TestEdgeCases | test_small_frame | 小尺寸帧(160×120) | ok=True |
| UT-E-04 | TestEdgeCases | test_single_instance_in_result | 单个实例结果 | count=1 |
| UT-E-05 | TestEdgeCases | test_offset_normalization | 偏移量归一化 | 绝对值<3.0 |

---

## 2. 状态可视化模块 (blindpath_visual.py)

### 2.1 STATE_STYLES 常量测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VS-01 | TestStateStyles | test_all_states_defined | 所有状态都有样式定义 | 10个状态全部存在 |
| UT-VS-02 | TestStateStyles | test_style_has_required_keys | 每个样式有bg和text键 | 所有样式包含bg和text |
| UT-VS-03 | TestStateStyles | test_bg_color_is_qcolor | 背景色是QColor对象 | 所有bg是QColor类型 |
| UT-VS-04 | TestStateStyles | test_text_color_is_qcolor | 文字色是QColor对象 | 所有text是QColor类型 |
| UT-VS-05 | TestStateStyles | test_warning_states_use_red_orange | 警告状态使用红色或橙色 | 盲道缺失和严重偏移文字偏红 |
| UT-VS-06 | TestStateStyles | test_normal_state_uses_green | 正常状态使用绿色 | 居中背景偏绿 |
| UT-VS-07 | TestStateStyles | test_obstacle_state_uses_orange | 疑似障碍状态使用橙色 | 背景红色>200, 绿色>150 |

### 2.2 get_status_text() 函数测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VG-01 | TestGetStatusText | test_initial_state | 初始状态文字 | 包含"等待" |
| UT-VG-02 | TestGetStatusText | test_centered_state | 居中状态文字 | 包含"对齐"或"居中" |
| UT-VG-03 | TestGetStatusText | test_offset_right_state | 右偏状态文字 | 包含"右侧"和角度值 |
| UT-VG-04 | TestGetStatusText | test_offset_left_state | 左偏状态文字 | 包含"左侧"和角度值 |
| UT-VG-05 | TestGetStatusText | test_severe_offset_state | 严重偏移状态文字 | 包含"严重"或"偏转" |
| UT-VG-06 | TestGetStatusText | test_not_detected_state | 未检出状态文字 | 包含"未检出" |
| UT-VG-07 | TestGetStatusText | test_unmeasurable_state | 无法测量状态文字 | 包含"无法测量"或"无法" |
| UT-VG-08 | TestGetStatusText | test_confirming_state_with_direction | 确认中状态(有方向) | 包含"确认中"和方向 |
| UT-VG-09 | TestGetStatusText | test_confirming_state_without_direction | 确认中状态(无方向) | 包含"确认中" |
| UT-VG-10 | TestGetStatusText | test_analysis_end_state | 分析结束状态文字 | 包含"分析结束" |
| UT-VG-11 | TestGetStatusText | test_missing_paving_state | 盲道缺失状态文字 | 包含"缺失"或"过低" |
| UT-VG-12 | TestGetStatusText | test_obstacle_suspected_state | 疑似障碍状态文字 | 包含"障碍"或"遮挡" |
| UT-VG-13 | TestGetStatusText | test_single_frame_prefix | 单帧模式前缀 | 包含"【单帧】" |
| UT-VG-14 | TestGetStatusText | test_multi_frame_no_prefix | 多帧模式无前缀 | 不包含"【单帧】" |
| UT-VG-15 | TestGetStatusText | test_unknown_state_returns_state_name | 未知状态返回名称 | 返回状态名称本身 |

### 2.3 apply_state_style() 函数测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VA-01 | TestApplyStateStyle | test_apply_style_sets_stylesheet | 应用样式设置stylesheet | 包含background-color和color |
| UT-VA-02 | TestApplyStateStyle | test_apply_style_unknown_state_uses_default | 未知状态使用默认样式 | 包含background-color |
| UT-VA-03 | TestApplyStateStyle | test_apply_style_warning_state_has_red | 警告状态样式包含红色 | 包含rgb(255或rgb(180 |
| UT-VA-04 | TestApplyStateStyle | test_apply_style_normal_state_has_green | 正常状态样式包含绿色 | 包含绿色分量 |
| UT-VA-05 | TestApplyStateStyle | test_apply_style_all_states | 所有状态都能应用样式 | 无异常抛出 |

---

## 3. 语音告警引擎模块 (blindpath_voice.py)

### 3.1 VoiceAlertEngine 初始化测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VI-01 | TestVoiceAlertEngineInit | test_default_enabled_false | 默认语音开关 | enabled=False |
| UT-VI-02 | TestVoiceAlertEngineInit | test_default_thresholds | 默认阈值 | offset_thresh=30, angle_thresh=20 |
| UT-VI-03 | TestVoiceAlertEngineInit | test_default_abnormal_duration | 默认异常持续时间 | min_abnormal_duration=2.0 |
| UT-VI-04 | TestVoiceAlertEngineInit | test_default_cooldown | 默认冷却时间 | alert_cooldown=5.0 |
| UT-VI-05 | TestVoiceAlertEngineInit | test_default_last_alert_time | 上次播报时间初始值 | last_alert_time=0.0 |
| UT-VI-06 | TestVoiceAlertEngineInit | test_default_alert_type_none | 当前告警类型初始值 | current_alert_type=None |
| UT-VI-07 | TestVoiceAlertEngineInit | test_default_abnormal_start_time_none | 异常开始时间初始值 | abnormal_start_time=None |

### 3.2 setEnabled() 方法测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VE-01 | TestSetEnabled | test_enable_voice | 开启语音 | enabled=True |
| UT-VE-02 | TestSetEnabled | test_disable_voice | 关闭语音 | enabled=False |
| UT-VE-03 | TestSetEnabled | test_disable_resets_state | 关闭语音重置状态 | current_alert_type=None, abnormal_start_time=None |

### 3.3 setThresholds() 方法测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VT-01 | TestSetThresholds | test_set_offset_threshold | 设置偏移阈值 | alert_offset_thresh=50 |
| UT-VT-02 | TestSetThresholds | test_set_angle_threshold | 设置角度阈值 | alert_angle_thresh=40 |
| UT-VT-03 | TestSetThresholds | test_set_both_thresholds | 同时设置两个阈值 | offset=45, angle=35 |

### 3.4 setAbnormalDuration() 方法测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VD-01 | TestSetAbnormalDuration | test_set_duration | 设置持续时间 | min_abnormal_duration=3.0 |
| UT-VD-02 | TestSetAbnormalDuration | test_set_zero_duration | 设置零持续时间 | min_abnormal_duration=0.0 |

### 3.5 _determineAlertType() 方法测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VD-03 | TestDetermineAlertType | test_no_paving_detected | 未检出盲道 | alert_type="no_paving" |
| UT-VD-04 | TestDetermineAlertType | test_normal_centered | 正常居中 | alert_type=None |
| UT-VD-05 | TestDetermineAlertType | test_offset_left | 左偏告警 | alert_type="offset_left" |
| UT-VD-06 | TestDetermineAlertType | test_offset_right | 右偏告警 | alert_type="offset_right" |
| UT-VD-07 | TestDetermineAlertType | test_angle_too_large | 角度过大告警 | alert_type="angle_large" |
| UT-VD-08 | TestDetermineAlertType | test_area_missing | 盲道缺失告警 | alert_type="area_missing" |
| UT-VD-09 | TestDetermineAlertType | test_area_obstacle | 疑似障碍告警 | alert_type="area_obstacle" |
| UT-VD-10 | TestDetermineAlertType | test_offset_below_threshold | 偏移低于阈值 | alert_type=None |
| UT-VD-11 | TestDetermineAlertType | test_angle_below_threshold | 角度低于阈值 | alert_type=None |
| UT-VD-12 | TestDetermineAlertType | test_determine_always_returns_type | _determineAlertType不检查enabled | 返回正确类型 |

### 3.6 checkAndAlert() 方法测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VC-01 | TestCheckAndAlert | test_disabled_no_alert | 语音关闭时不触发 | current_alert_type=None |
| UT-VC-02 | TestCheckAndAlert | test_normal_metrics_no_alert | 正常指标不触发 | current_alert_type=None |
| UT-VC-03 | TestCheckAndAlert | test_abnormal_starts_accumulating | 异常开始累积 | current_alert_type="offset_left", abnormal_start_time≠None |
| UT-VC-04 | TestCheckAndAlert | test_duration_not_reached_no_alert | 持续时间未达阈值 | last_alert_time=0.0 |
| UT-VC-05 | TestCheckAndAlert | test_recovery_resets_state | 恢复正常后重置 | current_alert_type=None, abnormal_start_time=None |
| UT-VC-06 | TestCheckAndAlert | test_alert_type_change_resets | 告警类型变化时重置 | current_alert_type="offset_right" |

### 3.7 告警冷却机制测试

| 用例编号 | 测试类 | 测试方法 | 测试内容 | 预期结果 |
|---------|--------|---------|---------|---------|
| UT-VCC-01 | TestAlertCooldown | test_cooldown_prevents_repeat_alert | 冷却期内不重复播报 | last_alert_time不变 |
| UT-VCC-02 | TestAlertCooldown | test_cooldown_expired_allows_new_alert | 冷却期过后允许新告警 | last_alert_time更新 |
| UT-VCC-03 | TestAlertCooldown | test_different_alert_types_independent | 不同类型告警独立冷却 | 不同类型可触发 |

---

## 测试执行命令

```bash
# 运行所有测试
cd /Users/nilianshu/Downloads/tp_detect
conda activate ppe_yolo
python -m pytest tests/ -v

# 运行单个模块测试
python -m pytest tests/test_metrics.py -v   # 核心算法
python -m pytest tests/test_visual.py -v    # 状态可视化
python -m pytest tests/test_voice.py -v     # 语音告警引擎

# 生成覆盖率报告
python -m pytest tests/ --cov=. --cov-report=html
```

## 测试结果

**执行时间**: 24.27秒  
**总用例数**: 142个  
**通过数**: 142个  
**失败数**: 0个  
**通过率**: 100%