#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书笔记类型检查工具
检查笔记是视频还是图文
"""

import os
import sys
import re
import requests
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_note_type(url):
    """检查笔记类型"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    print("="*80)
    print("小红书笔记类型检查")
    print("="*80)
    print(f"链接: {url[:80]}...")
    print()

    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"状态码: {response.status_code}")
        print(f"页面长度: {len(response.text)} 字符")
        print()

        # 提取标题
        title_match = re.search(r'<title[^>]*>(.+?)</title>', response.text)
        if title_match:
            title = title_match.group(1).replace(' - 小红书', '').strip()
            try:
                title = title.encode('raw_unicode_escape').decode('unicode_escape')
            except:
                try:
                    title = title.encode('latin1').decode('utf-8')
                except:
                    pass
            print(f"标题: {title[:50]}...")

        # 检查笔记类型
        print()
        print("笔记类型分析:")
        print("-"*80)

        # 方法1: 检查视频流
        has_video_stream = 'video' in response.text.lower() and 'stream' in response.text.lower()
        has_video_object = '"video":' in response.text
        has_media = '"media":' in response.text

        # 方法2: 检查图片
        has_image_list = 'imageList' in response.text and '"urlDefault"' in response.text

        # 计算图片数量
        if has_image_list:
            img_count = response.text.count('"urlDefault"')
            print(f"图片数量: {img_count}")
        else:
            print("图片数量: 0")

        # 方法3: 检查 type 字段
        type_matches = re.findall(r'"type":\s*"(\w+)"', response.text)
        if type_matches:
            print(f"笔记类型字段: {type_matches[0] if type_matches else 'N/A'}")

        print()

        # 判断笔记类型
        if has_video_stream or (has_video_object and has_media):
            print("[视频笔记]")
            print()
            print("推荐下载方式:")
            print("  方法1: 使用 MediaCrawler 爬虫")
            print("    cd MediaCrawler")
            print(f"    python main.py --platform xhs --lt q \"笔记ID\"")
            print()
            print("  方法2: 如果 yt-dlp 支持更新，稍后重试")
            print("    pip install --upgrade yt-dlp")

        elif has_image_list:
            print("[图文笔记]")
            print()
            print("推荐下载方式:")
            print("  使用小红书图文下载工具:")
            print(f"    python platforms/xiaohongshu/download_xhs_images.py \"{url}\"")
            print()
            print("  或使用工作流:")
            print(f"    python workflows/auto_xhs_image_workflow.py \"{url}\"")
        else:
            print("[无法确定笔记类型]")
            print()
            print("可能原因:")
            print("  1. 链接已过期或失效")
            print("  2. 需要登录才能查看")
            print("  3. 笔记已被删除")
            print()
            print("建议:")
            print("  请在小红书App中打开链接确认是否可访问")

        print()
        print("="*80)

    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_xhs_note.py \"小红书链接\"")
        sys.exit(1)

    url = sys.argv[1]
    check_note_type(url)