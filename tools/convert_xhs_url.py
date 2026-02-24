#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书链接转换工具
将用户主页格式的链接转换为标准笔记链接格式
"""

import re
import sys

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def convert_xhs_url(url):
    """转换小红书链接格式"""
    print("输入链接:", url[:80] + "..." if len(url) > 80 else url)

    # 检查链接格式
    if '/explore/' in url:
        print("\n[OK] 这已经是标准笔记链接格式")
        return url

    elif '/user/profile/' in url and 'xsec_token' in url:
        print("\n[转换] 转换用户主页格式的笔记链接...")
        # 提取笔记ID和token
        # 笔记ID是16进制字符串（19-20位）
        match = re.search(r'user/profile/([^/]+)/([0-9a-f]{16,20})', url, re.IGNORECASE)
        if match:
            note_id = match.group(2)
            # 提取查询参数
            query_start = url.find('?')
            query = url[query_start:] if query_start > 0 else ''
            # 转换为 explore 格式
            new_url = f'https://www.xiaohongshu.com/explore/{note_id}{query}'
            print("转换后:")
            print(new_url)
            return new_url
        else:
            print("[错误] 无法解析笔记ID")
            return None

    elif '/user/profile/' in url:
        print("\n[错误] 需要包含 xsec_token 的完整链接")
        print("   例如: https://www.xiaohongshu.com/user/profile/ID/NOTE_ID?xsec_token=xxx")
        return None

    else:
        print("\n[未知] 未知链接格式")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python convert_xhs_url.py \"小红书链接\"")
        sys.exit(1)

    url = sys.argv[1]
    result = convert_xhs_url(url)

    if result:
        print(f"\n[测试] 测试转换后的链接:")
        print(f"python tools/test_video_download.py -u \"{result}\" --info-only")