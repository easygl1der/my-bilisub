# -*- coding: utf-8 -*-
"""
评论爬取模块

提供统一的B站和小红书评论爬取接口
"""

from .platform_detector import PlatformDetector
from .url_parser import UrlParser, ParsedUrl
from .bilibili_adapter import BilibiliCommentAdapter
from .xiaohongshu_adapter import XiaohongshuCommentAdapter
from .output_formatter import CSVOutputFormatter, JSONOutputFormatter


class CommentCrawlerFactory:
    """评论爬虫工厂"""

    @staticmethod
    def create(platform: str, headless: bool = True) -> 'CommentAdapter':
        """
        创建对应平台的爬虫

        Args:
            platform: 平台名称 ('bilibili', 'xiaohongshu', 'xhs')
            headless: 是否使用无头模式（仅小红书有效）

        Returns:
            CommentAdapter 实例
        """
        platform = platform.lower()

        if platform == 'bilibili':
            return BilibiliCommentAdapter()
        elif platform in ['xhs', 'xiaohongshu']:
            return XiaohongshuCommentAdapter(headless=headless)
        else:
            raise ValueError(f"不支持的平台: {platform}")


__all__ = [
    'CommentCrawlerFactory',
    'PlatformDetector',
    'UrlParser',
    'ParsedUrl',
    'BilibiliCommentAdapter',
    'XiaohongshuCommentAdapter',
    'CSVOutputFormatter',
    'JSONOutputFormatter',
]
