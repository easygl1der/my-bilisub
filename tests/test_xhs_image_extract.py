#!/usr/bin/env python3
"""
测试小红书图文提取功能

功能：
1. 爬取用户主页的笔记列表
2. 选择一个图文笔记
3. 提取图片并以格式化形式展示
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


def get_user_notes(user_url: str) -> list:
    """
    获取用户的笔记列表

    Args:
        user_url: 用户主页链接（带xsec_token）

    Returns:
        笔记列表
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    print(f"📡 请求用户主页...")
    print(f"   URL: {user_url[:80]}...")

    response = requests.get(user_url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"❌ 请求失败: {response.status_code}")
        return []

    html = response.text
    print(f"✅ 页面获取成功 (长度: {len(html)})")

    # 提取用户名
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    user_name = "未知用户"
    if title_match:
        user_name = title_match.group(1).split('-')[0].strip()
    print(f"👤 用户名: {user_name}")

    # 查找 __INITIAL_STATE__ JSON 数据
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx == -1:
        print(f"❌ 未找到 __INITIAL_STATE__")
        return []

    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    # 尝试解析 JSON（可能不完整）
    data = None
    try:
        # 小红书的 JSON 可能包含换行，需要清理
        json_str_clean = json_str.replace('\n', '\\n').replace('\r', '\\r')
        data = json.loads(json_str_clean)
    except json.JSONDecodeError:
        # 如果还是失败，尝试找到完整的部分
        print(f"⚠️  JSON解析失败，尝试其他方法...")

    # 提取笔记列表
    notes = []

    # 方法1: 从 JSON 中提取
    if data:
        try:
            # 路径1: noteData.byNoteId
            if 'noteData' in data and 'byNoteId' in data['noteData']:
                note_dict = data['noteData']['byNoteId']
                for note_id, note_info in note_dict.items():
                    if isinstance(note_info, dict) and 'title' in note_info:
                        notes.append({
                            'note_id': note_id,
                            'title': note_info.get('title', ''),
                            'type': note_info.get('type', 'normal'),
                            'desc': note_info.get('desc', '')[:100],
                            'liked_count': note_info.get('liked_count', 0),
                        })
            # 路径2: user.noteStore.notes
            elif 'user' in data and 'noteStore' in data['user']:
                note_store = data['user']['noteStore']
                if 'notes' in note_store:
                    for note_item in note_store['notes']:
                        notes.append({
                            'note_id': note_item.get('id', ''),
                            'title': note_item.get('title', ''),
                            'type': note_item.get('type', 'normal'),
                            'desc': note_item.get('desc', '')[:100],
                            'liked_count': note_item.get('liked_count', 0),
                        })
        except Exception as e:
            print(f"⚠️  从 JSON 提取失败: {e}")

    # 方法2: 使用正则表达式从原始 HTML 中提取笔记 ID 和标题
    if not notes:
        print(f"🔍 使用正则表达式提取笔记...")
        # 查找所有 explore/ 链接
        explore_pattern = r'href="/explore/([a-f0-9]+)\?'
        note_ids = re.findall(explore_pattern, html)
        note_ids = list(set(note_ids))  # 去重

        # 查找标题
        title_pattern = r'"title":"([^"]+)"'
        titles = re.findall(title_pattern, html)

        print(f"   找到 {len(note_ids)} 个笔记ID, {len(titles)} 个标题")

        # 匹配 ID 和标题（简单配对）
        for i, note_id in enumerate(note_ids[:20]):  # 限制20个
            title = titles[i] if i < len(titles) else f"笔记{i+1}"
            try:
                title = title.encode('utf-8').decode('unicode_escape')
            except:
                pass
            notes.append({
                'note_id': note_id,
                'title': title,
                'type': 'normal',
                'desc': '',
                'liked_count': 0,
            })

    print(f"📝 找到 {len(notes)} 条笔记")

    return notes, user_name


def extract_xhs_images(url: str) -> dict:
    """
    从小红书链接提取笔记的图片

    Returns:
        {
            'title': '标题',
            'images': [
                {'url': '图片URL', 'index': 1},
                ...
            ],
            'text': '笔记文字内容'
        }
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    print(f"\n📡 请求笔记页面...")

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            return None

        html = response.text
        print(f"✅ 页面获取成功")

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

    # 提取标题
    title = "小红书笔记"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
    print(f"📝 标题: {title}")

    # 提取文字内容
    text_content = ""
    desc_match = re.search(r'"desc":"([^"]+)"', html)
    if desc_match:
        # 解码 Unicode 转义
        text_content = desc_match.group(1).encode('utf-8').decode('unicode_escape')
    print(f"📄 文字内容: {text_content[:100]}...")

    # 提取图片
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx == -1:
        print(f"❌ 未找到 __INITIAL_STATE__")
        return None

    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    data = None
    try:
        data = json.loads(json_str)
    except:
        pass

    image_urls = []

    if data:
        try:
            note = data.get('note', {})
            note_detail = note.get('noteDetail', {})
            image_list = note_detail.get('imageList', [])

            if image_list:
                for i, img_obj in enumerate(image_list):
                    if isinstance(img_obj, dict):
                        url = (img_obj.get('urlDefault') or
                               img_obj.get('url_default') or
                               img_obj.get('url'))
                        if url:
                            # 清理 URL
                            url = url.split('?')[0]
                            try:
                                url = url.encode('utf-8').decode('unicode_escape')
                            except:
                                pass
                            url = url.replace(r'\/', '/')
                            if url.startswith('http://'):
                                url = 'https://' + url[7:]

                            image_urls.append({
                                'index': i + 1,
                                'url': url
                            })
        except Exception as e:
            print(f"⚠️  提取图片失败: {e}")

    print(f"🖼️  找到 {len(image_urls)} 张图片")

    return {
        'title': title,
        'images': image_urls,
        'text': text_content
    }


def format_display_result(result: dict) -> str:
    """
    格式化显示提取结果
    """
    if not result:
        return "❌ 提取失败"

    output = []
    output.append("=" * 80)
    output.append("📋 小红书图文笔记提取结果")
    output.append("=" * 80)
    output.append("")
    output.append(f"📝 标题: {result['title']}")
    output.append("")
    output.append(f"📄 文字内容:")
    output.append(f"   {result['text']}")
    output.append("")
    output.append(f"🖼️  图片列表 ({len(result['images'])} 张):")
    output.append("")

    for img in result['images']:
        output.append(f"   [{img['index']}] {img['url']}")

    output.append("")
    output.append("=" * 80)

    return "\n".join(output)


def main():
    # 用户主页链接
    user_url = "https://www.xiaohongshu.com/user/profile/5b3ac81e11be107c7a5b7505?xsec_token=ABPLGMaYH1NMtjc6IEYUR-YLFSXtRx5IjPIM7yj019c0w=&xsec_source=pc_feed"

    print("\n" + "=" * 80)
    print("🔍 小红书图文提取测试")
    print("=" * 80)
    print()

    # 步骤1: 获取用户笔记列表
    notes_result = get_user_notes(user_url)

    if isinstance(notes_result, tuple):
        notes, user_name = notes_result
    else:
        notes = notes_result
        user_name = "未知用户"

    print(f"👤 用户: {user_name}")

    if not notes:
        print("❌ 未找到笔记")
        return

    # 显示笔记列表
    print("\n" + "-" * 80)
    print("📋 笔记列表:")
    print("-" * 80)

    for i, note in enumerate(notes[:10], 1):  # 只显示前10条
        note_type = note.get('type', 'normal')
        type_emoji = "🖼️" if note_type == 'normal' else "🎬"
        print(f"{i:2}. {type_emoji} {note['title'][:50]}")

    # 选择第一个图文笔记
    print("\n" + "-" * 80)
    print("🔍 选择第一个图文笔记进行测试...")
    print("-" * 80)

    image_note = None
    for note in notes:
        if note.get('type') == 'normal':
            image_note = note
            break

    if not image_note and notes:
        # 如果没有找到normal类型，就用第一个
        image_note = notes[0]

    if not image_note:
        print("❌ 没有找到可测试的笔记")
        return

    note_id = image_note.get('note_id', '')
    print(f"📝 选择笔记: {image_note['title'][:50]}")
    print(f"🆔 笔记ID: {note_id}")

    # 构建笔记链接
    note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_source=pc_feed"

    # 步骤2: 提取图片
    result = extract_xhs_images(note_url)

    # 步骤3: 格式化显示
    print("\n")
    print(format_display_result(result))

    # 步骤4: 保存结果到文件
    output_dir = Path("output/test_xhs")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = output_dir / f"extract_result_{timestamp}.txt"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(format_display_result(result))
        f.write("\n\n")
        f.write(f"原始笔记链接: {note_url}\n")
        f.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"💾 结果已保存到: {result_file}")


if __name__ == "__main__":
    main()
