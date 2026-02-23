# -*- coding: utf-8 -*-
"""
评论适配器基类

定义统一的评论爬取接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class CommentAdapter(ABC):
    """评论适配器基类"""

    @abstractmethod
    async def fetch(self, url: str, max_comments: int = 50) -> List[Dict]:
        """
        获取评论

        Args:
            url: 内容URL
            max_comments: 最大评论数

        Returns:
            评论列表，每条评论包含统一格式
        """
        pass

    @abstractmethod
    def normalize_comment(self, raw_comment: Dict) -> Dict:
        """
        标准化评论格式

        Args:
            raw_comment: 原始评论数据

        Returns:
            标准化后的评论数据
        """
        pass

    @staticmethod
    def get_standard_fields() -> list:
        """
        获取标准评论字段

        Returns:
            字段名列表
        """
        return [
            'comment_id',
            'content',
            'author',
            'likes',
            'create_time',
            'ip_location',
            'parent_id',
            'reply_count',
            'platform'
        ]
