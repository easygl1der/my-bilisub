# -*- coding: utf-8 -*-
"""
输出格式化器

统一CSV和JSON输出格式
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class CSVOutputFormatter:
    """CSV输出格式化器"""

    def save(self, comments: List[Dict], url: str, output_dir: Path = None) -> str:
        """
        保存评论到CSV

        Args:
            comments: 评论列表
            url: 原始URL
            output_dir: 输出目录

        Returns:
            输出文件路径，如果没有评论则返回 None
        """
        if not comments:
            return None

        if output_dir is None:
            output_dir = Path("comments_output")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 提取平台标识
        platform = comments[0].get('platform', 'unknown')
        content_id = url.split('/')[-1].split('?')[0][:20]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{platform}_comments_{content_id}_{timestamp}.csv"
        output_path = output_dir / filename

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = [
                'comment_id', 'author', 'content', 'likes',
                'create_time', 'ip_location', 'parent_id',
                'reply_count', 'platform'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(comments)

        return str(output_path)


class JSONOutputFormatter:
    """JSON输出格式化器"""

    def save(self, comments: List[Dict], url: str, output_dir: Path = None) -> str:
        """
        保存评论到JSON

        Args:
            comments: 评论列表
            url: 原始URL
            output_dir: 输出目录

        Returns:
            输出文件路径，如果没有评论则返回 None
        """
        if not comments:
            return None

        if output_dir is None:
            output_dir = Path("comments_output")

        output_dir.mkdir(parents=True, exist_ok=True)

        platform = comments[0].get('platform', 'unknown') if comments else 'unknown'
        content_id = url.split('/')[-1].split('?')[0][:20]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{platform}_comments_{content_id}_{timestamp}.json"
        output_path = output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url,
                'platform': platform,
                'timestamp': timestamp,
                'total': len(comments),
                'comments': comments
            }, f, ensure_ascii=False, indent=2)

        return str(output_path)
