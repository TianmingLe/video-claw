from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    """
    通用平台爬虫基类
    """
    @abstractmethod
    async def start_browser(self, headless: bool = True):
        pass

    @abstractmethod
    async def close_browser(self):
        pass

    @abstractmethod
    async def search_videos(self, keyword: str, max_count: int = 5) -> List[Dict[str, Any]]:
        """
        搜索视频。
        返回字典列表，例如：
        [{
            "id": "123", "platform": "douyin", "url": "https...",
            "title": "xxx", "author": "yyy", "like_count": 0
        }]
        """
        pass

    @abstractmethod
    async def fetch_comments(self, video_url: str, max_depth: int = 10) -> List[Dict[str, Any]]:
        """
        抓取视频的评论。
        返回字典列表，例如：
        [{
            "root_comment": "评论内容",
            "replies": ["回复1", "回复2"]
        }]
        """
        pass