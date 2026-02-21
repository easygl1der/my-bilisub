#!/usr/bin/env python3
"""
小红书用户主页笔记爬取 - 使用更强大的方法

直接从用户主页提取笔记列表和图片
"""

import os
import sys
import re
import json
import requests
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_user_notes_with_token(user_url: str):
    """
    从用户主页提取笔记（带xsec_token的请求）
    """
    # 提取 xsec_token
    token_match = re.search(r'xsec_token=([^&]+)', user_url)
    xsec_token = token_match.group(1) if token_match else ""
    xsec_source = "pc_user" if "pc_user" in user_url else "pc_feed"

    print(f"🔑 xsec_token: {xsec_token[:20]}...")
    print(f"📡 xsec_source: {xsec_source}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    print(f"\n📡 请求用户主页...")
    response = requests.get(user_url, headers=headers, timeout=30)

    print(f"状态码: {response.status_code}")
    print(f"页面长度: {len(response.text)}")

    if response.status_code != 200:
        return None

    html = response.text

    # 检查是否成功
    if '你访问的页面不见了' in html or '404' in html:
        print("❌ 页面无法访问")
        return None

    # 提取用户ID
    user_id = ""
    user_id_match = re.search(r'/user/profile/([a-f0-9]+)', user_url)
    if user_id_match:
        user_id = user_id_match.group(1)
    print(f"🆔 用户ID: {user_id}")

    # 提取用户名
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    user_name = "未知用户"
    if title_match:
        user_name = title_match.group(1).split('-')[0].strip()
    print(f"👤 用户名: {user_name}")

    # 尝试多种方法提取笔记
    notes = []

    # 方法1: 查找所有笔记ID
    print(f"\n🔍 提取笔记ID...")
    note_ids = re.findall(r'"noteId":"([a-f0-9]+)"', html)
    note_ids = list(set(note_ids))  # 去重

    print(f"   找到 {len(note_ids)} 个笔记ID")

    # 方法2: 提取笔记卡片数据
    card_data = re.findall(r'"noteCard":\s*\{[^}]+\}', html)
    print(f"   找到 {len(card_data)} 个笔记卡片")

    # 组合信息
    note_info = {}
    for card in card_data:
        try:
            # 提取noteId
            nid_match = re.search(r'"noteId":"([a-f0-9]+)"', card)
            if nid_match:
                nid = nid_match.group(1)

                # 提取标题
                title_match = re.search(r'"title":"([^"]+)"', card)
                title = title_match.group(1) if title_match else "无标题"
                try:
                    title = title.encode('utf-8').decode('unicode_escape')
                except:
                    pass

                # 提取类型
                type_match = re.search(r'"type":"(\w+)"', card)
                note_type = type_match.group(1) if type_match else "normal"

                # 提取封面图
                cover_match = re.search(r'"cover":"([^"]+)"', card)
                cover = cover_match.group(1) if cover_match else ""
                try:
                    cover = cover.encode('utf-8').decode('unicode_escape')
                except:
                    pass

                note_info[nid] = {
                    'title': title,
                    'type': note_type,
                    'cover': cover
                }
        except:
            pass

    print(f"   解析出 {len(note_info)} 个笔记信息")

    # 显示笔记列表
    print(f"\n📋 笔记列表:")
    print(f"{'='*100}")

    if note_info:
        for i, (nid, info) in enumerate(list(note_info.items())[:10], 1):
            type_emoji = "🖼️" if info['type'] == 'normal' else "🎬"
            print(f"{i:2}. {type_emoji} [{nid}] {info['title'][:60]}")
    else:
        print("   (未找到笔记)")
        return None

    return {
        'user_id': user_id,
        'user_name': user_name,
        'notes': note_info,
        'xsec_token': xsec_token,
        'xsec_source': xsec_source
    }


def extract_note_images(note_id: str, xsec_token: str, xsec_source: str = "pc_feed"):
    """
    提取单个笔记的图片
    """
    # 构建笔记链接
    note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"

    print(f"\n📡 请求笔记: {note_id}")
    print(f"   URL: {note_url[:80]}...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    response = requests.get(note_url, headers=headers, timeout=30)
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ❌ 请求失败")
        return None

    html = response.text

    if '你访问的页面不见了' in html:
        print(f"   ❌ 页面无法访问")
        return None

    # 提取标题
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    title = title_match.group(1).replace(' - 小红书', '').strip() if title_match else "未知"
    print(f"   📝 标题: {title}")

    # 提取文字
    desc_match = re.search(r'"desc":"([^"]+)"', html)
    desc = ""
    if desc_match:
        try:
            desc = desc_match.group(1).encode('utf-8').decode('unicode_escape')
        except:
            desc = desc_match.group(1)
    print(f"   📄 文字: {desc[:50]}..." if desc else "   📄 文字: (无)")

    # 提取图片
    print(f"   🔍 提取图片...")

    images = []

    # 方法1: 从 imageList 提取
    start_idx = html.find('"imageList":')
    if start_idx >= 0:
        # 找到数组开始和结束
        bracket_start = html.find('[', start_idx)
        if bracket_start >= 0:
            depth = 0
            i = bracket_start
            while i < len(html):
                if html[i] == '[':
                    depth += 1
                elif html[i] == ']':
                    depth -= 1
                    if depth == 0:
                        bracket_end = i
                        break
                i += 1

            image_list_json = html[bracket_start:bracket_end+1]

            # 提取 urlDefault
            url_matches = re.findall(r'"urlDefault":"([^"]+)"', image_list_json)
            for url in url_matches:
                try:
                    url = url.encode('utf-8').decode('unicode_escape')
                except:
                    pass
                url = url.replace(r'\/', '/')
                if 'xhscdn' in url:
                    images.append(url)

    # 方法2: 直接搜索
    if not images:
        urls = re.findall(r'"urlDefault":"(https://[^"]+xhscdn[^"]*)"', html)
        for url in urls:
            try:
                url = url.encode('utf-8').decode('unicode_escape')
            except:
                pass
            url = url.replace(r'\/', '/')
            if url not in images:
                images.append(url)

    print(f"   🖼️  找到 {len(images)} 张图片")

    return {
        'note_id': note_id,
        'title': title,
        'desc': desc,
        'images': images
    }


def format_and_save(user_info: dict, note_result: dict):
    """格式化显示并保存结果"""

    lines = []
    lines.append("=" * 100)
    lines.append("📋 小红书图文笔记提取结果".center(100))
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"👤 用户: {user_info['user_name']}")
    lines.append(f"🆔 用户ID: {user_info['user_id']}")
    lines.append("")
    lines.append(f"🆔 笔记ID: {note_result['note_id']}")
    lines.append("")
    lines.append(f"📝 标题:")
    lines.append(f"   {note_result['title']}")
    lines.append("")
    lines.append(f"📄 文字内容:")
    lines.append(f"   {note_result['desc'] if note_result['desc'] else '(无)'}")
    lines.append("")
    lines.append(f"🖼️  图片列表 ({len(note_result['images'])} 张):")
    lines.append("")

    for i, url in enumerate(note_result['images'], 1):
        lines.append(f"   [{i}] {url}")

    lines.append("")
    lines.append("=" * 100)

    output = "\n".join(lines)
    print("\n" + output)

    # 保存
    output_dir = Path("output/test_xhs")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', note_result['title'])[:30]
    result_file = output_dir / f"{safe_title}_{timestamp}.txt"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\n💾 结果已保存: {result_file}")


def main():
    # 你提供的用户主页链接
    user_url = "https://www.xiaohongshu.com/user/profile/5b3ac81e11be107c7a5b7505/?xsec_token=ABhu_Cqz8_LewlXka4tu0shSITMIZssGpjFKWiN78OfOI=&xsec_source=pc_user"

    print("\n" + "=" * 100)
    print("🔍 小红书用户主页笔记爬取")
    print("=" * 100)
    print()

    # 步骤1: 获取用户笔记列表
    user_info = extract_user_notes_with_token(user_url)

    if not user_info or not user_info['notes']:
        print("\n❌ 未找到笔记")
        return

    # 步骤2: 选择第一个图文笔记
    print(f"\n🔍 选择第一个图文笔记进行详细分析...")

    note_id = None
    for nid, info in user_info['notes'].items():
        if info['type'] == 'normal':
            note_id = nid
            print(f"   选择: {info['title'][:50]}")
            break

    if not note_id and user_info['notes']:
        # 如果没有normal类型，用第一个
        note_id = list(user_info['notes'].keys())[0]
        print(f"   选择: {user_info['notes'][note_id]['title'][:50]}")

    # 步骤3: 提取笔记详情和图片
    note_result = extract_note_images(
        note_id,
        user_info['xsec_token'],
        user_info['xsec_source']
    )

    if note_result and note_result['images']:
        # 步骤4: 格式化显示并保存
        format_and_save(user_info, note_result)
    else:
        print(f"\n❌ 未找到图片")


if __name__ == "__main__":
    main()
