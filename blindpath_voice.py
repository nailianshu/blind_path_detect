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
        """检查当前帧指标，基于时间累积触发告警"""
        
        # ★ 检查开关和引擎
        if not self.enabled:
            return
        
        if not self.use_system_tts and self.engine is None:
            return

        count = metrics.get("count", 0)
        offset = metrics.get("offset", None)
        angle = metrics.get("angle", None)

        # ★ 诊断：打印当前帧的关键指标（每10帧打印一次）
        if hasattr(self, '_frame_count'):
            self._frame_count += 1
        else:
            self._frame_count = 1
            
        if self._frame_count % 10 == 1:
            offset_pct = abs(offset) * 100 if offset is not None else None
            angle_val = angle if angle is not None else None
            print(f"📊 帧{self._frame_count}: count={count}, offset={offset_pct}%, angle={angle_val}°")

        # ★ 判断当前帧的异常类型
        alert_type = self._determineAlertType(count, offset, angle)
        now = time.time()
        
        # ★ 基于时间的状态机逻辑
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
                # 还没到2秒，继续等待（每秒打印一次）
                if int(duration) > int(duration - (now - getattr(self, '_last_print_time', now))):
                    print(f"⚠️ {alert_type} 持续中: {duration:.1f}s / {self.min_abnormal_duration}s")
                    self._last_print_time = now
            else:
                # ★ 达到2秒！触发告警
                print(f"🚨 触发告警！{alert_type}, 持续{duration:.1f}s")
                self._triggerAlert(alert_type, offset)
                
                # ★ 关键：触发后强制重置，必须先恢复正常才能再次触发
                self.current_alert_type = None
                self.abnormal_start_time = None
                
        else:
            # 【新的异常类型】→ 重新开始计时
            if self.current_alert_type is not None:
                print(f"🔄 切换异常: {self.current_alert_type} → {alert_type}")
            else:
                print(f"⚠️ 开始检测异常: {alert_type}")
            
            self.current_alert_type = alert_type
            self.abnormal_start_time = now
            self._last_print_time = now

    def _determineAlertType(self, count, offset, angle):
        """判断当前帧的异常类型"""
        if count == 0:
            return "no_paving"
        
        if offset is not None and angle is not None:
            offset_pct = abs(offset) * 100
            angle_abs = abs(angle)
            
            if offset_pct >= self.alert_offset_thresh:
                return "offset_right" if offset > 0 else "offset_left"
            
            if angle_abs >= self.alert_angle_thresh:
                return "angle_large"
        
        return None

    def _triggerAlert(self, alert_type: str, offset=None):
        """根据异常类型触发对应的语音告警"""
        if alert_type == "no_paving":
            msg = "未检测到盲道，请小心前行"
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