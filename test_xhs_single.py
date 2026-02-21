#!/usr/bin/env python3
"""
测试小红书单笔记图文提取功能

直接测试笔记链接的图片提取
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


def extract_xhs_images_from_note(note_url: str) -> dict:
    """
    从小红书笔记链接提取图片和文字

    Returns:
        {
            'title': '标题',
            'text': '文字内容',
            'images': [
                {'index': 1, 'url': '图片URL', 'size': '文件大小'},
                ...
            ],
            'note_id': '笔记ID'
        }
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    print(f"📡 请求笔记页面...")
    print(f"   URL: {note_url[:80]}...")

    try:
        response = requests.get(note_url, headers=headers, timeout=30, allow_redirects=True)
        print(f"   状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            return None

        html = response.text
        print(f"✅ 页面获取成功 (长度: {len(html)})")

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

    # 提取笔记ID
    note_id = ""
    note_id_match = re.search(r'/explore/([a-f0-9]+)', note_url)
    if note_id_match:
        note_id = note_id_match.group(1)
    print(f"🆔 笔记ID: {note_id}")

    # 提取标题
    title = "小红书笔记"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
    print(f"📝 标题: {title}")

    # 提取文字内容
    text_content = ""

    # 方法1: 从 desc 字段提取
    desc_patterns = [
        r'"desc":"([^"]+)"',
        r'"desc":\s*"([^"]+)"',
    ]

    for pattern in desc_patterns:
        desc_match = re.search(pattern, html)
        if desc_match:
            try:
                text_content = desc_match.group(1).encode('utf-8').decode('unicode_escape')
                break
            except:
                text_content = desc_match.group(1)

    print(f"📄 文字内容: {text_content[:100] if text_content else '(无)'}...")

    # 提取图片
    print(f"\n🔍 正在提取图片...")

    image_list = []

    # 方法1: 从 __INITIAL_STATE__ 提取
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx >= 0:
        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        # 尝试解析
        try:
            # 清理 JSON
            json_str_clean = json_str.replace('\n', '\\n').replace('\r', '\\r')
            data = json.loads(json_str_clean)

            # 提取图片
            try:
                note = data.get('note', {})
                note_detail = note.get('noteDetail', {})
                images = note_detail.get('imageList', [])

                if images:
                    print(f"✅ 从 imageList 找到 {len(images)} 张图片")
                    for i, img in enumerate(images):
                        url = (img.get('urlDefault') or
                               img.get('url_default') or
                               img.get('url') or
                               img.get('infoList', [{}])[0].get('url')
                               if isinstance(img.get('infoList'), list) else None)
                        if url:
                            image_list.append({'index': i+1, 'url': url})
            except Exception as e:
                print(f"⚠️  从 imageList 提取失败: {e}")

        except json.JSONDecodeError:
            print(f"⚠️  JSON 解析失败")

    # 方法2: 直接搜索图片 URL
    if not image_list:
        print(f"🔍 尝试直接搜索图片 URL...")
        # 小红书图片 URL 格式
        patterns = [
            r'"urlDefault":"(https://[^"]+xhscdn[^"]*)"',
            r'"url":"(https://sns-webpic[^"]+)"',
            r'(https://sns-webpic[^"\s\'<>]+)',
        ]

        for pattern in patterns:
            urls = re.findall(pattern, html)
            if urls:
                print(f"✅ 找到 {len(urls)} 个图片 URL")
                for i, url in enumerate(urls[:10]):  # 最多10张
                    # 清理 URL
                    url = url.split('?')[0]
                    try:
                        url = url.encode('utf-8').decode('unicode_escape')
                    except:
                        pass
                    url = url.replace(r'\/', '/')
                    if url.startswith('http://'):
                        url = 'https://' + url[7:]

                    if 'xhscdn' in url or 'sns-webpic' in url:
                        image_list.append({'index': len(image_list)+1, 'url': url})
                break

    # 获取图片大小
    print(f"\n📊 获取图片信息...")
    for img in image_list:
        try:
            img_response = requests.head(img['url'], headers=headers, timeout=10)
            if img_response.status_code == 200:
                size = int(img_response.headers.get('Content-Length', 0))
                size_kb = size / 1024
                img['size'] = f"{size_kb:.1f}KB"
            else:
                img['size'] = "Unknown"
        except:
            img['size'] = "Unknown"

    return {
        'note_id': note_id,
        'title': title,
        'text': text_content,
        'images': image_list
    }


def format_result(result: dict) -> str:
    """格式化显示结果"""
    if not result:
        return "❌ 提取失败"

    lines = []
    lines.append("=" * 100)
    lines.append("📋 小红书图文笔记提取结果".center(100))
    lines.append("=" * 100)
    lines.append("")

    # 笔记ID
    lines.append(f"🆔 笔记ID: {result['note_id']}")
    lines.append("")

    # 标题
    lines.append(f"📝 标题:")
    lines.append(f"   {result['title']}")
    lines.append("")

    # 文字内容
    lines.append(f"📄 文字内容:")
    if result['text']:
        lines.append(f"   {result['text']}")
    else:
        lines.append(f"   (无文字内容)")
    lines.append("")

    # 图片列表
    lines.append(f"🖼️  图片列表 ({len(result['images'])} 张):")
    lines.append("")

    if result['images']:
        lines.append("┌────┬────────────────────────────────────────────────────────────────────────────────┬────────┐")
        lines.append("│ #  │ 图片URL                                                                 │ 大小   │")
        lines.append("├────┼────────────────────────────────────────────────────────────────────────────────┼────────┤")

        for img in result['images']:
            url = img['url'][:76] + '...' if len(img['url']) > 76 else img['url']
            size = img.get('size', 'Unknown')
            lines.append(f"│ {img['index']:2} │ {url:<76} │ {size:>6} │")

        lines.append("└────┴────────────────────────────────────────────────────────────────────────────────┴────────┘")
    else:
        lines.append("   (未找到图片)")

    lines.append("")
    lines.append("=" * 100)

    return "\n".join(lines)


def download_images(result: dict, output_dir: str = "output/test_xhs_images") -> list:
    """下载图片到本地"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded = []

    print(f"\n📥 开始下载图片...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    for img in result['images']:
        url = img['url']
        index = img['index']
        print(f"   [{index}/{len(result['images'])}] ", end='', flush=True)

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                # 确定扩展名
                content_type = response.headers.get('Content-Type', '')
                if 'png' in content_type or '.png' in url:
                    ext = '.png'
                elif 'webp' in content_type or '.webp' in url:
                    ext = '.webp'
                else:
                    ext = '.jpg'

                # 安全文件名
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', result['title'])[:30]
                filename = f"{safe_title}_{index:02d}{ext}"
                filepath = output_path / filename

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                size = len(response.content) / 1024
                print(f"✅ {size:.1f}KB -> {filename}")
                downloaded.append(str(filepath))
            else:
                print(f"❌ HTTP {response.status_code}")

        except Exception as e:
            print(f"❌ {str(e)[:30]}")

    return downloaded


def main():
    # 测试笔记链接（你可以替换成其他链接）
    test_url = input("请输入小红书笔记链接（直接回车使用默认测试链接）: ").strip()

    if not test_url:
        # 默认测试链接（你可以替换成有效的）
        test_url = "https://www.xiaohongshu.com/explore/65003b71000000001300085c?xsec_source=pc_feed"

    print("\n" + "=" * 100)
    print("🔍 小红书图文笔记提取测试")
    print("=" * 100)
    print()

    # 提取图片
    result = extract_xhs_images_from_note(test_url)

    if result and result['images']:
        # 显示结果
        print("\n")
        print(format_result(result))

        # 询问是否下载
        print()
        choice = input("是否下载图片到本地？(y/n): ").strip().lower()

        if choice == 'y':
            downloaded = download_images(result)
            print(f"\n💾 已下载 {len(downloaded)} 张图片到 output/test_xhs_images/")

        # 保存结果
        output_dir = Path("output/test_xhs")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', result['title'])[:30]
        result_file = output_dir / f"{safe_title}_{timestamp}.txt"

        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(format_result(result))
            f.write(f"\n\n")
            f.write(f"原始链接: {test_url}\n")
            f.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"💾 结果已保存到: {result_file}")

    else:
        print("\n❌ 未找到图片，可能原因:")
        print("   1. 链接需要 xsec_token 参数")
        print("   2. 笔记是视频类型（不是图文）")
        print("   3. 反爬虫保护（需要登录）")
        print("\n💡 建议:")
        print("   - 从小红书APP分享获取完整链接")
        print("   - 确保笔记是图文类型而非视频")


if __name__ == "__main__":
    main()
