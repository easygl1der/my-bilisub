# -*- coding: utf-8 -*-
"""
小红书评论适配器

调用现有的小红书评论爬取工具
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List

from .base import CommentAdapter


class XiaohongshuCommentAdapter(CommentAdapter):
    """小红书评论适配器"""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def fetch(self, url: str, max_comments: int = 50) -> List[Dict]:
        """
        获取小红书评论

        Args:
            url: 小红书笔记URL
            max_comments: 最大评论数

        Returns:
            评论列表

        Raises:
            Exception: 当MediaCrawler不可用或失败时
        """
        # 调用现有的MediaCrawler版本
        return await self._fetch_with_mediacrawler(url, max_comments)

    async def _fetch_with_mediacrawler(self, url: str, max_comments: int) -> List[Dict]:
        """
        使用MediaCrawler获取评论

        Args:
            url: 笔记URL
            max_comments: 最大评论数

        Returns:
            评论列表
        """
        # 导入MediaCrawler相关模块
        media_crawler_path = Path(__file__).parent.parent.parent.parent / "MediaCrawler"
        sys.path.insert(0, str(media_crawler_path))

        try:
            # 配置MediaCrawler
            import config
            config.PLATFORM = "xhs"
            config.CRAWLER_TYPE = "detail"
            config.XHS_SPECIFIED_NOTE_URL_LIST = [url]
            config.ENABLE_GET_COMMENTS = True
            config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max_comments
            config.HEADLESS = self.headless
            config.SAVE_LOGIN_STATE = True
            config.SAVE_DATA_OPTION = "json"

            # 尝试加载 cookies
            try:
                cookie_str = self._load_xhs_cookie()
                if cookie_str:
                    config.COOKIES = cookie_str
                    config.LOGIN_TYPE = "cookie"
                else:
                    config.LOGIN_TYPE = "qrcode"
                    config.HEADLESS = False
            except Exception:
                config.LOGIN_TYPE = "qrcode"
                config.HEADLESS = False

            # 运行爬虫
            from main import main as crawler_main
            await crawler_main()

            # 查找并提取评论
            data_dir = media_crawler_path / "data" / "xhs" / "json"
            if data_dir.exists():
                for json_file in sorted(data_dir.glob("*.json"), reverse=True):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        comments = self._extract_comments_from_data(data)
                        if comments:
                            # 标准化评论
                            normalized = [self.normalize_comment(c) for c in comments]
                            return normalized[:max_comments]
                    except Exception:
                        continue

            return []

        except Exception as e:
            # 如果MediaCrawler失败，尝试备用方案
            try:
                return await self._fetch_fallback(url, max_comments)
            except Exception:
                raise Exception(f"小红书评论爬取失败: {e}\n提示：请确保 MediaCrawler 依赖已安装")

    def _fetch_fallback(self, url: str, max_comments: int) -> List[Dict]:
        """
        备用方案：尝试直接调用现有的fetch_xhs_comments.py

        Args:
            url: 笔记URL
            max_comments: 最大评论数

        Returns:
            评论列表
        """
        # 这里可以尝试调用 fetch_xhs_comments.py 的函数
        # 但由于依赖问题，暂时返回空列表
        return []

    def _load_xhs_cookie(self) -> str:
        """从 config/cookies.txt 加载小红书 Cookie"""
        import configparser

        config_file = configparser.RawConfigParser()
        config_file.read('config/cookies.txt', encoding='utf-8')

        try:
            full_key = "xiaohongshu_full"
            if config_file.has_option('xiaohongshu', full_key):
                return config_file.get('xiaohongshu', full_key)
        except Exception:
            pass

        return ""

    def _extract_comments_from_data(self, data: list) -> list:
        """从数据中提取评论"""
        comments = []

        for item in data:
            # 尝试多种评论字段
            comments_list = (
                item.get('comments', []) or
                item.get('comment_list', []) or
                item.get('note_comments', [])
            )

            for comment in comments_list:
                if not isinstance(comment, dict):
                    continue

                # 解析评论字段
                parsed = {
                    'comment_id': comment.get('id', comment.get('comment_id', '')),
                    'content': (
                        comment.get('content', '') or
                        comment.get('text', '') or
                        comment.get('note_comment', '') or
                        comment.get('comment_text', '')
                    ),
                    'likes': (
                        comment.get('like_count', 0) or
                        comment.get('likes', 0) or
                        comment.get('liked_count', 0) or 0
                    ),
                    'author': (
                        comment.get('nickname', '') or
                        comment.get('user_name', '') or
                        comment.get('author', '') or '[未知]'
                    ),
                    'ip_location': comment.get('ip_location', ''),
                    'create_time': comment.get('create_time', comment.get('ctime', '')),
                    'platform': 'xiaohongshu'
                }

                if parsed['content']:
                    comments.append(parsed)

        return comments

    def normalize_comment(self, raw_comment: Dict) -> Dict:
        """
        标准化小红书评论格式

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
            'ip_location': raw_comment.get('ip_location', ''),
            'parent_id': '',
            'reply_count': 0,
            'platform': 'xiaohongshu'
        }
