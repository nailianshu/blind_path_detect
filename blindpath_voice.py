import time
import threading
import subprocess
import platform
from PyQt5.QtCore import pyqtSignal, QObject

# 尝试导入 pyttsx3，失败则使用系统 TTS
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class VoiceAlertEngine(QObject):
    """离线语音告警引擎：主线程安全调用"""

    alert_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.enabled = False
        self.alert_offset_thresh = 30           # 偏移告警阈值（百分比）
        self.alert_angle_thresh = 20            # 角度告警阈值（度）
        
        # ★ 核心参数：连续异常持续时间阈值（秒）
        self.min_abnormal_duration = 2.0        # 至少持续2秒异常才触发
        
        # ★ 告警冷却时间（秒）：两次播报之间的最小间隔
        self.alert_cooldown = 5.0               # 默认5秒冷却期
        self.last_alert_time = 0.0              # 上次播报的时间戳
        
        # ★ 使用独立的状态追踪（基于时间，不是帧数）
        self.current_alert_type = None          # 当前正在累积的异常类型
        self.abnormal_start_time = None         # 当前异常开始的时间戳
        
        # ★ TTS 引擎选择
        self.engine = None
        self.use_system_tts = False            # 是否使用系统 TTS
        self.tts_process = None                # 系统TTS进程

        self._init_engine()
        self.alert_signal.connect(self._playVoice)

    def _init_engine(self):
        """初始化 TTS 引擎：优先使用系统TTS（更稳定），回退到 pyttsx3"""
        
        # ★ 方案1：macOS 系统 TTS（最可靠）
        if platform.system() == 'Darwin':  # macOS
            self.use_system_tts = True
            print("✅ 使用 macOS 系统 TTS (say 命令)")
            return
        
        # ★ 方案2：pyttsx3（跨平台备选）
        if PYTTSX3_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 180)
                self.engine.setProperty('volume', 0.9)
                print("✅ 使用 pyttsx3 引擎")
                return
            except Exception as e:
                print(f"⚠️ pyttsx3 初始化失败：{e}")
        
        # ★ 都失败
        print("❌ 无可用的 TTS 引擎")
        self.engine = None

    def setEnabled(self, enabled: bool):
        """设置语音总开关"""
        self.enabled = enabled
        if not enabled:
            self.current_alert_type = None
            self.abnormal_start_time = None

    def setThresholds(self, offset_thresh: int, angle_thresh: int):
        """设置告警阈值"""
        self.alert_offset_thresh = offset_thresh
        self.alert_angle_thresh = angle_thresh

    def setAbnormalDuration(self, duration: float):
        """设置连续异常持续时间阈值（秒）"""
        self.min_abnormal_duration = duration

    def checkAndAlert(self, metrics: dict):
        """
        检查当前帧指标，基于时间累积触发告警
        
        告警逻辑：
        1. 检查语音开关和 TTS 引擎是否可用
        2. 从指标字典中提取关键数据（盲道数量、偏移量、角度、面积占比）
        3. 判断当前帧的异常类型
        4. 基于时间的状态机：异常状态持续超过阈值才触发告警
        5. 触发后进入冷却期，冷却期内不重复播报
        6. 冷却期过后且异常仍然存在，才再次播报
        
        参数:
            metrics: 指标字典（来自 blindpath_metrics.analyze）
        """
        
        # 检查开关和引擎
        if not self.enabled:
            return
        
        if not self.use_system_tts and self.engine is None:
            return

        count = metrics.get("count", 0)
        offset = metrics.get("offset", None)
        angle = metrics.get("angle", None)
        area_ratio = metrics.get("area_ratio", 0.0)

        # 诊断：打印当前帧的关键指标（每10帧打印一次）
        if hasattr(self, '_frame_count'):
            self._frame_count += 1
        else:
            self._frame_count = 1
            
        if self._frame_count % 10 == 1:
            offset_pct = abs(offset) * 100 if offset is not None else None
            angle_val = angle if angle is not None else None
            print(f"📊 帧{self._frame_count}: count={count}, offset={offset_pct}%, angle={angle_val}°, area={area_ratio*100:.2f}%")

        # 判断当前帧的异常类型
        alert_type = self._determineAlertType(count, offset, angle, area_ratio)
        now = time.time()
        
        # 基于时间的状态机逻辑
        if alert_type is None:
            # 【正常帧】
            if self.current_alert_type is not None:
                duration = now - self.abnormal_start_time
                print(f"✅ 恢复正常（之前是 {self.current_alert_type}，持续{duration:.1f}s）")
            # 重置所有状态
            self.current_alert_type = None
            self.abnormal_start_time = None
            
        elif alert_type == self.current_alert_type:
            # 【同一异常继续】→ 检查持续时间
            duration = now - self.abnormal_start_time
            
            if duration < self.min_abnormal_duration:
                # 还没到阈值时间，继续等待（每秒打印一次）
                if int(duration) > int(duration - (now - getattr(self, '_last_print_time', now))):
                    print(f"⚠️ {alert_type} 持续中: {duration:.1f}s / {self.min_abnormal_duration}s")
                    self._last_print_time = now
            else:
                # 达到阈值时间！检查是否在冷却期内
                time_since_last_alert = now - self.last_alert_time
                
                if time_since_last_alert < self.alert_cooldown:
                    # 在冷却期内，跳过播报但不重置状态
                    remaining = self.alert_cooldown - time_since_last_alert
                    if not hasattr(self, '_cooldown_logged') or self._cooldown_logged != alert_type:
                        print(f"⏸️ {alert_type} 在冷却期内，跳过播报（剩余 {remaining:.1f}s）")
                        self._cooldown_logged = alert_type
                    # 不重置状态，继续等待冷却期结束
                else:
                    # 冷却期已过，触发告警
                    print(f"🚨 触发告警！{alert_type}, 持续{duration:.1f}s")
                    self._triggerAlert(alert_type, offset, area_ratio)
                    
                    # 记录播报时间
                    self.last_alert_time = now
                    
                    # 关键：触发后重置状态，必须先恢复正常才能再次触发
                    self.current_alert_type = None
                    self.abnormal_start_time = None
                    self._cooldown_logged = None
                
        else:
            # 【新的异常类型】→ 重新开始计时
            if self.current_alert_type is not None:
                print(f"🔄 切换异常: {self.current_alert_type} → {alert_type}")
            else:
                print(f"⚠️ 开始检测异常: {alert_type}")
            
            self.current_alert_type = alert_type
            self.abnormal_start_time = now
            self._last_print_time = now

    def _determineAlertType(self, count, offset, angle, area_ratio=0.0):
        """
        判断当前帧的异常类型
        
        异常类型包括：
        - "no_paving": 未检测到盲道
        - "area_missing": 盲道面积占比过低（< 2%），可能缺失
        - "area_obstacle": 盲道面积占比偏小（2%~5%），可能有障碍物
        - "offset_right/left": 偏移过大
        - "angle_large": 方向角过大
        
        参数:
            count: 检测到的盲道实例数量
            offset: 归一化偏移量
            angle: 方向角（度）
            area_ratio: 盲道面积占比（0.0~1.0）
        
        返回:
            异常类型字符串，或 None 表示正常
        """
        if count == 0:
            return "no_paving"
        
        # 检查面积占比（新增：基于面积判断盲道缺失/障碍物）
        if area_ratio < 0.02:  # 2% 以下
            return "area_missing"
        elif area_ratio < 0.05:  # 2%~5%
            return "area_obstacle"
        
        if offset is not None and angle is not None:
            offset_pct = abs(offset) * 100
            angle_abs = abs(angle)
            
            # 检查偏移是否超过阈值
            if offset_pct >= self.alert_offset_thresh:
                return "offset_right" if offset > 0 else "offset_left"
            
            # 检查角度是否超过阈值
            if angle_abs >= self.alert_angle_thresh:
                return "angle_large"
        
        return None

    def _triggerAlert(self, alert_type: str, offset=None, area_ratio=0.0):
        """
        根据异常类型触发对应的语音告警
        
        参数:
            alert_type: 异常类型字符串
            offset: 归一化偏移量（可选）
            area_ratio: 盲道面积占比（可选）
        """
        if alert_type == "no_paving":
            msg = "未检测到盲道，请小心前行"
        elif alert_type == "area_missing":
            msg = "盲道缺失，请小心前行"
        elif alert_type == "area_obstacle":
            msg = "盲道可能有障碍物，请注意"
        elif alert_type == "offset_right":
            msg = "向左调整"
        elif alert_type == "offset_left":
            msg = "向右调整"
        elif alert_type == "angle_large":
            msg = "方向偏转过大"
        else:
            return
        
        self.alert_signal.emit(msg)

    def _playVoice(self, msg: str):
        """实际播放语音（槽函数，在主线程执行）- 异步不阻塞"""
        
        print(f"🔊 播报：{msg}")
        
        try:
            if self.use_system_tts:
                success = self._playWithSystemTTS(msg)
            elif self.engine is not None:
                success = self._playWithPyttsx3(msg)
            else:
                success = False
                print("❌ 无可用的 TTS 引擎")
            
            if success:
                print(f"✅ 已发送: {msg}")
            else:
                print(f"❌ 失败: {msg}")
                
        except Exception as e:
            print(f"⚠️ 异常: {type(e).__name__}: {e}")

    def _playWithSystemTTS(self, msg: str) -> bool:
        """使用 macOS 系统 TTS 播放（异步，不阻塞UI）"""
        
        # ★ 关键修复：如果上一个还没播完，先杀掉
        if self.tts_process is not None:
            print("ℹ️ 终止上一条未完成的语音")
            self._killProcess()
        
        try:
            self.tts_process = subprocess.Popen(
                ['say', '-v', 'Ting-Ting', '--rate=200', msg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # ★ 后台线程等待进程结束（仅用于清理，不阻塞主线程）
            def wait_and_cleanup():
                try:
                    self.tts_process.wait(timeout=10)
                except:
                    self._killProcess()
            
            wait_thread = threading.Thread(target=wait_and_cleanup, daemon=True)
            wait_thread.start()
            
            return True
            
        except Exception as e:
            print(f"⚠️ 系统TTS失败：{e}")
            return False

    def _playWithPyttsx3(self, msg: str) -> bool:
        """使用 pyttsx3 播放"""
        try:
            self.engine.say(msg)
            self.engine.runAndWait()
            return True
        except RuntimeError as e:
            if "run loop already started" in str(e):
                print("⚠️ pyttsx3 事件循环冲突")
            else:
                print(f"⚠️ pyttsx3 RuntimeError: {e}")
            return False
        except Exception as e:
            print(f"⚠️ pyttsx3 异常: {e}")
            return False

    def _killProcess(self):
        """终止系统TTS进程"""
        if self.tts_process:
            try:
                self.tts_process.terminate()
                self.tts_process.wait(timeout=1)
            except:
                try:
                    self.tts_process.kill()
                except:
                    pass
            finally:
                self.tts_process = None

    def reset(self):
        """重置所有状态（换素材时调用）"""
        self.current_alert_type = None
        self.abnormal_start_time = None
        self.last_alert_time = 0.0  # 重置冷却时间
        self._cooldown_logged = None

    def stop(self):
        """停止并释放资源"""
        self.reset()
        
        if self.tts_process:
            self._killProcess()
        
        if self.engine is not None and not self.use_system_tts:
            try:
                self.engine.stop()
            except:
                pass