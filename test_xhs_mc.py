#!/usr/bin/env python3
"""
测试小红书图文提取 - 使用 MediaCrawler
"""

import os
import sys
import asyncio
import re
import json
from pathlib import Path

# 添加 MediaCrawler 到路径
sys.path.insert(0, str(Path(__file__).parent / "MediaCrawler"))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


async def get_user_notes_media_crawler(user_id: str, cookie: str = ""):
    """
    使用 MediaCrawler 获取用户笔记

    需要先在 MediaCrawler 中配置好 cookie
    """
    try:
        from media_platform.xiaohongshu.client import XiaoHongShuClient
        from media_platform.xiaohongshu.exception import DataFetchError

        client = XiaoHongShuClient()

        # 获取用户信息
        print(f"📡 获取用户信息...")
        user_info = await client.get_creator_info(user_id, "", "")

        if user_info:
            print(f"✅ 用户名: {user_info.get('nickname', '未知')}")
            print(f"   笔记数: {user_info.get('notes_count', 0)}")

        return None

    except ImportError as e:
        print(f"❌ MediaCrawler 导入失败: {e}")
        print(f"   请确保 MediaCrawler 子模块已初始化")
        return None
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return None


def test_extract_from_url(note_url: str):
    """
    直接从笔记链接提取图片
    """
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    print(f"📡 请求笔记: {note_url[:80]}...")

    response = requests.get(note_url, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")

    if '你访问的页面不见了' in response.text:
        print("❌ 页面无法访问 - 需要完整的 xsec_token")
        return None

    html = response.text

    # 查找笔记ID
    note_id_match = re.search(r'/explore/([a-f0-9]+)', note_url)
    if note_id_match:
        note_id = note_id_match.group(1)
        print(f"🆔 笔记ID: {note_id}")

    # 提取标题
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
        print(f"📝 标题: {title}")

    # 搜索图片URL
    print(f"\n🔍 搜索图片...")

    # 方法1: urlDefault
    urls1 = re.findall(r'"urlDefault":"([^"]+)"', html)
    # 方法2: sns-webpic
    urls2 = re.findall(r'(https://sns-webpic[^"\s]+)', html)

    all_urls = []
    for url in urls1 + urls2:
        url = url.split('?')[0]
        try:
            url = url.encode('utf-8').decode('unicode_escape')
        except:
            pass
        url = url.replace(r'\/', '/')
        if 'xhscdn' in url and url not in all_urls:
            all_urls.append(url)

    print(f"✅ 找到 {len(all_urls)} 张图片")

    if all_urls:
        print(f"\n🖼️  图片列表:")
        for i, url in enumerate(all_urls[:10], 1):
            print(f"   [{i}] {url}")

    return {
        'title': title if title_match else "未知",
        'images': all_urls
    }


def main():
    print("\n" + "=" * 80)
    print("🔍 小红书图文提取测试")
    print("=" * 80)
    print()

    # 测试笔记链接 - 请替换为有效的链接
    test_url = "https://www.xiaohongshu.com/explore/64e6403e0000000012004563?xsec_source=pc_feed"

    print("📝 测试链接（默认）")
    print(f"   {test_url}")
    print()

    # 你可以输入自己的链接
    import sys
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        print(f"📝 使用自定义链接")
        print(f"   {test_url}")
        print()

    result = test_extract_from_url(test_url)

    if result and result['images']:
        print(f"\n✅ 提取成功!")
        print(f"   标题: {result['title']}")
        print(f"   图片数: {len(result['images'])}")

        # 保存结果
        output_dir = Path("output/test_xhs")
        output_dir.mkdir(parents=True, exist_ok=True)

        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = output_dir / f"result_{timestamp}.txt"

        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"标题: {result['title']}\n\n")
            f.write(f"图片列表 ({len(result['images'])}张):\n\n")
            for i, url in enumerate(result['images'], 1):
                f.write(f"[{i}] {url}\n")

        print(f"💾 结果已保存: {result_file}")
    else:
        print("\n❌ 提取失败")
        print("\n💡 提示:")
        print("   1. 确保链接包含完整的 xsec_token 参数")
        print("   2. 从小红书APP分享获取链接")
        print("   3. 笔记必须是图文类型，不能是视频")


if __name__ == "__main__":
    main()
