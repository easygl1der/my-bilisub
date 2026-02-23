# -*- coding: utf-8 -*-
"""
URL解析工具

统一解析各平台的URL，提取内容ID
"""

import re
from typing import Optional
from dataclasses import dataclass
from .platform_detector import PlatformDetector


@dataclass
class ParsedUrl:
    """解析后的URL信息"""
    platform: str          # 平台: 'bilibili', 'xiaohongshu'
    content_id: str        # 内容ID: BV号/AV号/笔记ID
    full_url: str          # 完整URL
    url_type: str          # URL类型: 'video', 'note'


class UrlParser:
    """URL解析工具"""

    @staticmethod
    def parse(url: str) -> ParsedUrl:
        """
        解析URL

        Args:
            url: URL字符串

        Returns:
            ParsedUrl 实例

        Raises:
            ValueError: 无法解析的URL
        """
        platform = PlatformDetector.detect(url)

        if platform == 'bilibili':
            return UrlParser._parse_bilibili(url)
        elif platform == 'xiaohongshu':
            return UrlParser._parse_xiaohongshu(url)
        else:
            raise ValueError(f"无法识别的URL: {url}")

    @staticmethod
    def _parse_bilibili(url: str) -> ParsedUrl:
        """
        解析B站URL

        支持格式:
        - https://www.bilibili.com/video/BV1xx411c7mD/
        - https://www.bilibili.com/video/av123456/
        - https://b23.tv/xxxxx
        - 直接的BV号/AV号
        """
        url = url.strip()

        # BV号
        bv_match = re.search(r'BV([a-zA-Z0-9]{10})', url)
        if bv_match:
            return ParsedUrl(
                platform='bilibili',
                content_id='BV' + bv_match.group(1),
                full_url=url if '://' in url else f"https://www.bilibili.com/video/BV{bv_match.group(1)}",
                url_type='video'
            )

        # AV号
        av_match = re.search(r'av(\d+)', url)
        if av_match:
            return ParsedUrl(
                platform='bilibili',
                content_id='av' + av_match.group(1),
                full_url=url if '://' in url else f"https://www.bilibili.com/video/av{av_match.group(1)}",
                url_type='video'
            )

        raise ValueError(f"无法解析B站URL: {url}")

    @staticmethod
    def _parse_xiaohongshu(url: str) -> ParsedUrl:
        """
        解析小红书URL

        支持格式:
        - https://www.xiaohongshu.com/explore/69983ebb00000000150304d8
        - https://www.xiaohongshu.com/discovery/item/69983ebb00000000150304d8
        - https://www.xiaohongshu.com/item/69983ebb00000000150304d8
        - 直接的笔记ID (24位十六进制)
        """
        url = url.strip()

        # 提取笔记ID（24位十六进制）
        patterns = [
            r'/explore/([a-f0-9]{24})',
            r'/discovery/item/([a-f0-9]{24})',
            r'/item/([a-f0-9]{24})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                note_id = match.group(1)
                return ParsedUrl(
                    platform='xiaohongshu',
                    content_id=note_id,
                    full_url=url if '://' in url else f"https://www.xiaohongshu.com/explore/{note_id}",
                    url_type='note'
                )

        # 尝试直接提取24位十六进制
        match = re.search(r'([a-f0-9]{24})', url, re.IGNORECASE)
        if match:
            note_id = match.group(1)
            return ParsedUrl(
                platform='xiaohongshu',
                content_id=note_id,
                full_url=f"https://www.xiaohongshu.com/explore/{note_id}",
                url_type='note'
            )

        raise ValueError(f"无法解析小红书URL: {url}")
