class StateMachine:
    """状态机：连续 N 帧确认才切换状态，防止抖动"""

    def __init__(self, confirm_n=5):
        self.state = "初始"
        self.direction = "无"
        self.candidate_state = None
        self.candidate_direction = None
        self.candidate_count = 0
        self.CONFIRM_N = confirm_n

    def update(self, new_state, new_direction):
        """返回 True 表示状态真的切换了（供报警/语音用）"""
        candidate_key = (new_state, new_direction)
        current_key = (self.state, self.direction)

        if candidate_key == current_key:
            self.candidate_state = None
            self.candidate_direction = None
            self.candidate_count = 0
            return False

        if candidate_key == (self.candidate_state, self.candidate_direction):
            self.candidate_count += 1
        else:
            self.candidate_state = new_state
            self.candidate_direction = new_direction
            self.candidate_count = 1

        if self.candidate_count >= self.CONFIRM_N:
            self.state = new_state
            self.direction = new_direction
            self.candidate_state = None
            self.candidate_direction = None
            self.candidate_count = 0
            return True
        return False

    def reset(self):
        """复位状态机"""
        self.state = "初始"
        self.direction = "无"
        self.candidate_state = None
        self.candidate_direction = None
        self.candidate_count = 0