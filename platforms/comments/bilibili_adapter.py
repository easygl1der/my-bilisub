# -*- coding: utf-8 -*-
"""
B站评论适配器

调用现有的 B站评论爬取工具
"""

import asyncio
from typing import Dict, List
from pathlib import Path
import sys

from .base import CommentAdapter


class BilibiliCommentAdapter(CommentAdapter):
    """B站评论适配器"""

    def __init__(self):
        self.client = None

    async def fetch(self, url: str, max_comments: int = 50) -> List[Dict]:
        """
        获取B站评论

        Args:
            url: B站视频URL
            max_comments: 最大评论数

        Returns:
            评论列表
        """
        # 获取Cookie
        cookie_str = self._load_bili_cookie()
        if not cookie_str:
            raise Exception("B站 Cookie 未配置，请在 config/cookies.txt 中添加")

        # 获取视频ID
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"无法从URL提取视频ID: {url}")

        # 转换BV号到AV号
        aid = await self._bv_to_aid(video_id, cookie_str)
        if not aid:
            raise Exception("无法获取视频 AV 号")

        # 获取评论
        all_comments = []
        page_size = 20
        page = 1

        while len(all_comments) < max_comments:
            comments = await self._fetch_page(aid, page, page_size, cookie_str)
            if not comments:
                break

            all_comments.extend(comments)

            if len(comments) < page_size:
                break

            page += 1

        # 标准化评论
        normalized = [self.normalize_comment(c) for c in all_comments]

        return normalized[:max_comments]

    async def _fetch_page(self, oid: int, page: int, page_size: int, cookie_str: str) -> List[Dict]:
        """
        获取一页评论

        Args:
            oid: 视频AV号
            page: 页码
            page_size: 每页数量
            cookie_str: Cookie字符串

        Returns:
            评论列表
        """
        import requests
        import time

        url = "https://api.bilibili.com/x/v2/reply"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie_str,
        }

        params = {
            'type': 1,
            'oid': oid,
            'mode': 3,  # 按热门排序
            'pagination_str': '{"offset":""}',
            'ps': page_size,
            'pn': page,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            data = response.json()

            if data.get('code') == 0:
                replies = data.get('data', {}).get('replies', [])
                return self._parse_comments(replies)
            else:
                return []

        except Exception as e:
            return []

    def _parse_comments(self, replies: List[Dict]) -> List[Dict]:
        """解析评论数据"""
        parsed = []

        for reply in replies:
            try:
                member = reply.get("member", {})
                content = reply.get("content", {})
                like_count = reply.get("like", 0)

                parsed.append({
                    "comment_id": reply.get("rpid", ""),
                    "content": content.get("message", ""),
                    "likes": like_count,
                    "author": member.get("uname", ""),
                    "create_time": reply.get("ctime", 0),
                    "platform": "bilibili"
                })
            except Exception:
                continue

        return parsed

    async def _bv_to_aid(self, bvid: str, cookie_str: str) -> int:
        """
        将 BV 号转换为 AV 号

        Args:
            bvid: BV号
            cookie_str: Cookie字符串

        Returns:
            AV号
        """
        import requests

        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie_str,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if data.get('code') == 0:
                aid = data.get('data', {}).get('aid')
                return aid
        except Exception:
            pass

        return None

    def _extract_video_id(self, url: str) -> str:
        """
        从URL提取视频ID

        Args:
            url: URL字符串

        Returns:
            视频ID (BV号/AV号)
        """
        import re

        # BV号
        bv_match = re.search(r'BV([a-zA-Z0-9]{10})', url)
        if bv_match:
            return 'BV' + bv_match.group(1)

        # AV号
        av_match = re.search(r'av(\d+)', url)
        if av_match:
            return av_match.group(1)

        return None

    def _load_bili_cookie(self) -> str:
        """
        从 config/cookies.txt 加载B站 Cookie

        Returns:
            Cookie字符串
        """
        import configparser

        project_root = Path(__file__).parent.parent.parent.parent
        config_file = project_root / "config" / "cookies.txt"

        if not config_file.exists():
            print("⚠️ Cookie 配置文件不存在: config/cookies.txt")
            return ""

        try:
            config = configparser.RawConfigParser()
            config.read(config_file, encoding='utf-8')

            # 优先使用 full 格式
            if config.has_option('bilibili', 'bilibili_full'):
                return config.get('bilibili', 'bilibili_full')

            # 手动构建 cookie 字符串
            if config.has_section('bilibili'):
                cookies = config.items('bilibili')
                filtered = [(k, v) for k, v in cookies if not k.endswith('_full')]
                return '; '.join([f"{k}={v}" for k, v in filtered])

        except Exception as e:
            print(f"⚠️ 读取 Cookie 失败: {e}")

        return ""

    def normalize_comment(self, raw_comment: Dict) -> Dict:
        """
        标准化B站评论格式

        Args:
            raw_comment: 原始评论数据

        Returns:
            标准化后的评论数据
        """
        return {
            'comment_id': raw_comment.get('comment_id', ''),
            'content': raw_comment.get('content', ''),
            'author': raw_comment.get('author', ''),
            'likes': raw_comment.get('likes', 0),
            'create_time': raw_comment.get('create_time', ''),
            'ip_location': '',
            'parent_id': '',
            'reply_count': 0,
            'platform': 'bilibili'
        }
