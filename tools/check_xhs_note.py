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

        # 计算图片数量
        has_image_list = 'imageList' in response.text and '"urlDefault"' in response.text
        img_count = 0
        if has_image_list:
            img_count = response.text.count('"urlDefault"')
            print(f"图片数量: {img_count}")
        else:
            print("图片数量: 0")

        # 检查 type 字段
        type_matches = re.findall(r'"type":\s*"(\w+)"', response.text)
        if type_matches:
            # 过滤掉无关的 type 字段
            relevant_types = [t for t in type_matches if t in ('video', 'normal', 'default', 'image')]
            if relevant_types:
                print(f"笔记类型字段: {relevant_types[0]}")

        # 检查视频特征（只使用明确特征）
        # 视频页面特有的字段
        has_play_addr = '"playAddr":' in response.text or '"play_addr":' in response.text
        has_media_video = re.search(r'"media":\s*\{[^}]*"video":\s*\{', response.text)

        # 显示检测到的特征
        print("检测特征:")
        if has_play_addr:
            print("  ✓ 检测到 playAddr 字段（视频特征）")
        if has_media_video:
            print("  ✓ 检测到 media.video 嵌套结构（视频特征）")
        if not has_play_addr and not has_media_video:
            print("  ✗ 未检测到明确的视频特征")
        print()

        # 判断笔记类型
        note_type = "未知"
        confidence = "低"

        # 逻辑（优先从明确特征判断）：
        # 1. 检测到明确的视频特征 → 视频（高置信度）
        # 2. 图片数量 >= 2 → 图文（高置信度）
        # 3. 图片数量 == 1 且无视频特征 → 图文（中置信度，可能是单图图文）
        # 4. 默认认为是图文
        if has_play_addr or has_media_video:
            note_type = "视频"
            confidence = "高"
        elif img_count >= 2:
            note_type = "图文"
            confidence = "高"
        elif img_count == 1:
            # 单图情况：如果没有任何视频特征，更可能是单图图文
            note_type = "图文"
            confidence = "中"
        elif has_image_list:
            note_type = "图文"
            confidence = "中"

        print(f"检测类型: {note_type} (置信度: {confidence})")
        print()

        # 根据判断结果给出推荐
        if note_type == "图文":
            print("[图文笔记]")
            print()
            print("推荐下载方式:")
            print("  使用小红书图文下载工具:")
            print(f"    python platforms/xiaohongshu/download_xhs_images.py \"{url}\"")
            print()
            print("  或使用工作流:")
            print(f"    python workflows/auto_xhs_image_workflow.py \"{url}\"")

        elif note_type == "视频" or note_type == "可能是视频":
            print("[视频笔记]")
            print()
            print("推荐下载方式:")
            print("  方法1: 使用 MediaCrawler 爬虫")
            print("    cd MediaCrawler")
            print(f"    python main.py --platform xhs --lt q \"笔记ID\"")
            print()
            print("  方法2: 如果 yt-dlp 支持更新，稍后重试")
            print("    pip install --upgrade yt-dlp")
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