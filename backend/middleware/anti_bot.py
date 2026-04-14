import random
import asyncio

class AntiBotController:
    def __init__(self, mode: str = "normal"):
        """
        mode: "normal" (省心模式) 或 "special_forces" (特种战士模式)
        """
        self.mode = mode
        
        # 基础延迟配置 (单位: 秒) [min, max]
        self.delay_config = {
            "normal": {
                "search": [0.3, 1.2],
                "click_video": [0.8, 2.0],
                "scroll_comments": [1.0, 2.5]
            },
            "special_forces": {
                "search": [0.1, 0.5],
                "click_video": [0.3, 1.0],
                "scroll_comments": [0.5, 1.2]
            }
        }
        
    async def random_delay(self, action: str):
        """执行拟人化随机延迟"""
        config = self.delay_config.get(self.mode, self.delay_config["normal"])
        action_delay = config.get(action, [1.0, 2.0]) # 默认 1-2 秒
        
        # 随机取值
        delay_time = random.uniform(action_delay[0], action_delay[1])
        await asyncio.sleep(delay_time)

    def check_safety_limit(self, current_depth: int, max_depth: int) -> bool:
        """检查是否触及安全底线（防止即使是特种战士模式也把账号拉爆）"""
        # 底层硬编码安全上限（例如：单次抓取绝对不允许超过 5000 条评论）
        HARD_LIMIT = 5000
        actual_max = min(max_depth, HARD_LIMIT)
        return current_depth < actual_max