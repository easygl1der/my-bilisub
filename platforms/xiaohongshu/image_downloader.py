#!/usr/bin/env python3
"""
小红书用户主页 - 只爬取图文笔记

功能：
1. 从用户主页获取所有笔记
2. 筛选出图文类型的笔记
3. 下载图片和文案

用法:
    python download_xhs_image_only.py "用户主页链接（带xsec_token）"
"""

import os
import sys
import re
import json
import time
import requests
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def get_image_notes_only(user_url: str):
    """
    从用户主页获取所有图文笔记（过滤掉视频）

    Returns:
        {
            'user_name': '用户名',
            'notes': [
                {'note_id': '', 'title': '', 'desc': '', 'image_count': 0},
                ...
            ]
        }
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    print(f"📡 请求用户主页...")

    response = requests.get(user_url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"❌ 请求失败: {response.status_code}")
        return None

    if '你访问的页面不见了' in response.text or '404' in response.url:
        print(f"❌ 页面无法访问（需要有效的 xsec_token）")
        return None

    html = response.text

    # 提取用户名 - 尝试多种方法
    user_name = "小红书用户"
    user_id = ""

    # 先提取用户ID
    user_id_match = re.search(r'/user/profile/([a-f0-9]+)', user_url)
    if user_id_match:
        user_id = user_id_match.group(1)
        print(f"🆔 用户ID: {user_id}")

    # 方法1: 从 <title> 标签
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title_name = title_match.group(1).split('-')[0].strip()
        if title_name and '小红书' not in title_name and '登录' not in title_name:
            user_name = title_name

    # 方法2: 从 JSON 中搜索 nickname - 优先级最高
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx >= 0:
        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        try:
            # 清理 JSON
            json_str_clean = json_str.replace('\n', '\\n').replace('\r', '\\r')
            data = json.loads(json_str_clean)

            # 多种路径查找 nickname
            nickname = None

            # 路径1: user.userPageData.result.nickname
            if 'user' in data and 'userPageData' in data['user']:
                nickname = data['user']['userPageData'].get('result', {}).get('nickname')

            # �path2: user.result.nickname
            if not nickname and 'user' in data:
                nickname = data['user'].get('result', {}).get('nickname')

            # 路径3: 直接搜索 nickname 字段
            if not nickname:
                all_nicknames = re.findall(r'"nickname":"([^"]+)"', json_str_clean)
                if all_nicknames:
                    # 取最长的那个作为用户名
                    nickname = max(all_nicknames, key=len, default="")

            if nickname:
                try:
                    user_name = nickname.encode('utf-8').decode('unicode_escape')
                except:
                    user_name = nickname
        except:
            pass

    # 方法3: 如果还是没找到，使用用户ID的部分作为备用
    if user_name == "小红书用户" and user_id:
        user_name = f"用户_{user_id[:8]}"

    print(f"👤 用户名: {user_name}")

    # 查找所有笔记卡片
    print(f"\n🔍 分析笔记类型...")

    # 查找 noteCard 数据
    image_notes = []

    # 方法1: 从 JSON 解析
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx >= 0:
        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        try:
            # 清理 JSON
            json_str_clean = json_str.replace('\n', '\\n').replace('\r', '\\r')
            data = json.loads(json_str_clean)

            # 提取笔记
            if 'noteData' in data and 'byNoteId' in data['noteData']:
                for note_id, note_info in data['noteData']['byNoteId'].items():
                    if isinstance(note_info, dict):
                        note_type = note_info.get('type', 'video')
                        title = note_info.get('title', '')

                        # 只保留图文类型的笔记
                        if note_type == 'normal' and title:
                            desc = note_info.get('desc', '')

                            # 获取图片数量
                            image_list = note_info.get('imageList', [])
                            image_count = len(image_list) if isinstance(image_list, list) else 0

                            image_notes.append({
                                'note_id': note_id,
                                'title': title,
                                'desc': desc[:200] if desc else '',
                                'image_count': image_count
                            })
        except:
            pass

    # 方法2: 使用正则表达式（备用）
    if not image_notes:
        print(f"   使用正则表达式...")

        # 查找类型和标题
        type_pattern = r'"type":"(normal|video)"'
        types = re.findall(type_pattern, html)

        title_pattern = r'"title":"([^"]+)"'
        titles = re.findall(title_pattern, html)

        print(f"   找到 {len(types)} 个类型, {len(titles)} 个标题")

        # 匹配
        for i, (note_type, title) in enumerate(zip(types, titles)):
            if note_type == 'normal':
                try:
                    title = title.encode('utf-8').decode('unicode_escape')
                except:
                    pass
                image_notes.append({
                    'note_id': f"note_{i}",
                    'title': title,
                    'desc': '',
                    'image_count': 0
                })

    print(f"✅ 找到 {len(image_notes)} 个图文笔记")

    return {
        'user_name': user_name,
        'notes': image_notes
    }


def download_note_images(note: dict, xsec_token: str, xsec_source: str, output_dir: Path):
    """下载单个笔记的图片和文案"""
    note_id = note['note_id']
    title = note['title']
    desc = note.get('desc', '')

    # 构建笔记链接
    note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"

    print(f"\n📖 [{note['note_id']}] {title[:50]}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    response = requests.get(note_url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"   ❌ 请求失败")
        return False

    html = response.text

    # 提取图片URL
    images = []
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx >= 0:
        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        try:
            data = json.loads(json_str.replace('\n', '\\n'))
            note = data.get('note', {})
            note_detail = note.get('noteDetail', {})
            image_list = note_detail.get('imageList', [])

            for img in image_list:
                url = img.get('urlDefault') or img.get('url')
                if url:
                    try:
                        url = url.encode('utf-8').decode('unicode_escape')
                    except:
                        pass
                    url = url.replace(r'\/', '/')
                    images.append(url)
        except:
            pass

    if not images:
        # 备用方法
        urls = re.findall(r'"urlDefault":"(https://[^"]+)"', html)
        for url in urls:
            try:
                url = url.encode('utf-8').decode('unicode_escape')
            except:
                pass
            url = url.replace(r'\/', '/')
            if 'xhscdn' in url:
                images.append(url)

    if not images:
        print(f"   ⚠️  未找到图片")
        return False

    # 创建文件夹
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
    note_path = output_dir / safe_title
    note_path.mkdir(parents=True, exist_ok=True)

    # 保存文案
    if desc:
        with open(note_path / "content.txt", 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n\n文案:\n{desc}\n")

    # 下载图片
    print(f"   📥 下载 {len(images)} 张图片...")

    success_count = 0
    for i, img_url in enumerate(images, 1):
        try:
            print(f"      [{i}/{len(images)}] ", end='', flush=True)
            img_resp = requests.get(img_url, headers=headers, timeout=30)

            if img_resp.status_code == 200:
                # 确定扩展名
                ct = img_resp.headers.get('Content-Type', '')
                if 'png' in ct:
                    ext = '.png'
                elif 'webp' in ct:
                    ext = '.webp'
                else:
                    ext = '.jpg'

                filepath = note_path / f"image_{i:02d}{ext}"
                with open(filepath, 'wb') as f:
                    f.write(img_resp.content)

                size = len(img_resp.content) / 1024
                print(f"✅ {size:.1f}KB")
                success_count += 1
            else:
                print(f"❌ HTTP {img_resp.status_code}")

        except Exception as e:
            print(f"❌ {e}")

        time.sleep(0.3)

    print(f"   ✅ 保存到: {note_path.name}")
    return success_count > 0


def main():
    if len(sys.argv) < 2:
        print("用法: python download_xhs_image_only.py \"用户主页链接（带xsec_token）\"")
        print("\n功能:")
        print("  1. 获取用户所有笔记")
        print("  2. 筛选出图文笔记（排除视频）")
        print("  3. 下载图片和文案")
        sys.exit(1)

    user_url = sys.argv[1]

    # 提取 xsec_token
    token_match = re.search(r'xsec_token=([^&]+)', user_url)
    xsec_token = token_match.group(1) if token_match else ""
    source_match = re.search(r'xsec_source=([^&]+)', user_url)
    xsec_source = source_match.group(1) if source_match else "pc_user"

    if not xsec_token:
        print("❌ 链接中未找到 xsec_token")
        return

    print("\n" + "=" * 80)
    print("🖼️  小红书图文笔记批量下载")
    print("=" * 80)
    print()

    # 获取图文笔记列表
    result = get_image_notes_only(user_url)

    if not result or not result['notes']:
        print("\n❌ 未找到图文笔记")
        return

    print(f"\n📝 找到 {len(result['notes'])} 个图文笔记:")
    for i, note in enumerate(result['notes'][:10], 1):
        print(f"   {i:2}. {note['title'][:60]}")

    if len(result['notes']) > 10:
        print(f"   ... 还有 {len(result['notes']) - 10} 个")

    # 询问是否下载
    print()
    choice = input("是否开始下载? (y/n): ").strip().lower()

    if choice != 'y':
        print("已取消")
        return

    # 创建输出目录
    output_dir = Path("xhs_images") / re.sub(r'[<>:"/\\|?*]', '_', result['user_name'])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 保存位置: {output_dir}")
    print()

    # 下载每个笔记
    success_count = 0
    for i, note in enumerate(result['notes'], 1):
        print(f"\n[{i}/{len(result['notes'])}] ", end='', flush=True)
        if download_note_images(note, xsec_token, xsec_source, output_dir):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"🎉 完成!")
    print(f"   成功: {success_count}/{len(result['notes')}")
    print(f"   位置: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
