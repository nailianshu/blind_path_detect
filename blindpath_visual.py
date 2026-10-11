from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel


# 颜色与文字映射（浅色界面）
STATE_STYLES = {
    "初始": {
        "bg": QColor(240, 240, 240),      # 浅灰底
        "text": QColor(128, 128, 128),    # 深灰字
    },
    "居中": {
        "bg": QColor(220, 255, 220),      # 浅绿底
        "text": QColor(0, 100, 0),        # 深绿字
    },
    "偏移": {
        "bg": QColor(255, 255, 200),      # 浅黄底
        "text": QColor(128, 64, 0),       # 深棕字
    },
    "严重偏移": {
        "bg": QColor(255, 220, 220),      # 浅红底
        "text": QColor(180, 0, 0),        # 深红字
    },
    "未检出": {
        "bg": QColor(240, 240, 240),      # 浅灰底
        "text": QColor(128, 128, 128),    # 深灰字
    },
    "无法测量": {
        "bg": QColor(240, 240, 240),      # 浅灰底
        "text": QColor(128, 128, 128),    # 深灰字
    },
    "确认中": {
        "bg": QColor(240, 240, 240),      # 浅灰底
        "text": QColor(128, 128, 128),    # 深灰字
    },
    "分析结束": {
        "bg": QColor(240, 240, 240),      # 浅灰底
        "text": QColor(128, 128, 128),    # 深灰字
    },
}


def apply_state_style(label: QLabel, state: str):
    """给 label_info 应用状态颜色（背景 + 文字）"""
    style = STATE_STYLES.get(state, STATE_STYLES["初始"])
    bg = style["bg"]
    text = style["text"]

    label.setStyleSheet(
        f"background-color: rgb({bg.red()}, {bg.green()}, {bg.blue()}); "
        f"color: rgb({text.red()}, {text.green()}, {text.blue()}); "
        f"padding: 4px;"
    )
    label.setAlignment(label.alignment() | Qt.AlignCenter)


def get_status_text(state: str, direction: str, offset_pct: int, is_single_frame: bool = False):
    """根据状态和方向生成提示文字"""
    prefix = "【单帧】" if is_single_frame else ""

    if state == "初始":
        return f"{prefix}等待有效测量"
    elif state == "居中":
        return f"{prefix}盲道与参考线近似对齐"
    elif state == "偏移":
        side = "右侧" if direction == "右" else "左侧"
        return f"{prefix}盲道位于参考线{side}（{offset_pct}%）"
    elif state == "严重偏移":
        return f"{prefix}图像偏移较大：参考线超出检测区间"
    elif state == "未检出":
        return f"{prefix}未检出盲道，无法判断偏移"
    elif state == "无法测量":
        return f"{prefix}已检出盲道，但当前无法测量"
    elif state == "确认中":
        side = "右侧" if direction == "右" else "左侧" if direction else ""
        return f"{prefix}确认中：盲道位于参考线{side}" if direction else f"{prefix}确认中"
    elif state == "分析结束":
        return f"{prefix}分析结束：末帧结果仅供参考"
    return f"{prefix}未知状态"