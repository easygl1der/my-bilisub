#!/usr/bin/env python3
"""
小红书图文提取测试 - 非交互版本

使用方法:
1. 从小红书APP或网页复制笔记链接（必须带xsec_token）
2. 修改下面的 test_url 变量
3. 运行脚本: python test_xhs_final.py
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


# ==================== 配置区 ====================
# TODO: 在这里粘贴你的小红书笔记链接（必须带 xsec_token）
test_url = ""
# ================================================


def extract_xhs_images(note_url: str) -> dict:
    """提取小红书笔记的图片和文字"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    print(f"📡 请求: {note_url[:80]}...")
    print()

    try:
        response = requests.get(note_url, headers=headers, timeout=30)
        print(f"状态码: {response.status_code}")
        print(f"页面长度: {len(response.text)}")

        if response.status_code != 200:
            return None

        # 检查是否是404页面
        if '你访问的页面不见了' in response.text or '404' in response.url:
            print("\n❌ 页面无法访问")
            print("   原因: 链接缺少 xsec_token 或已过期")
            print("   解决: 请从小红书APP复制完整链接")
            return None

        html = response.text

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

    # 提取标题
    title = "小红书笔记"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()

    # 提取笔记ID
    note_id = ""
    note_id_match = re.search(r'/explore/([a-f0-9]+)', note_url)
    if note_id_match:
        note_id = note_id_match.group(1)

    # 提取文字
    text_content = ""
    desc_match = re.search(r'"desc":"([^"]+)"', html)
    if desc_match:
        try:
            text_content = desc_match.group(1).encode('utf-8').decode('unicode_escape')
        except:
            text_content = desc_match.group(1)

    # 提取图片
    images = []

    # 从 JSON 提取
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx >= 0:
        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        try:
            data = json.loads(json_str)
            note = data.get('note', {})
            note_detail = note.get('noteDetail', {})
            image_list = note_detail.get('imageList', [])

            for i, img in enumerate(image_list):
                url = (img.get('urlDefault') or img.get('url'))
                if url:
                    images.append(url)

        except:
            pass

    # 备用：直接搜索
    if not images:
        urls = re.findall(r'"urlDefault":"(https://[^"]+)"', html)
        images = urls

    return {
        'note_id': note_id,
        'title': title,
        'text': text_content,
        'images': images
    }


def format_and_save(result: dict, url: str):
    """格式化显示并保存结果"""

    # 输出目录
    output_dir = Path("output/test_xhs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建输出
    lines = []
    lines.append("=" * 100)
    lines.append("📋 小红书图文笔记提取结果".center(100))
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"🆔 笔记ID: {result['note_id']}")
    lines.append("")
    lines.append(f"📝 标题:")
    lines.append(f"   {result['title']}")
    lines.append("")
    lines.append(f"📄 文字内容:")
    lines.append(f"   {result['text'] if result['text'] else '(无)'}")
    lines.append("")
    lines.append(f"🖼️  图片列表 ({len(result['images'])} 张):")
    lines.append("")

    for i, img_url in enumerate(result['images'], 1):
        lines.append(f"   [{i}] {img_url}")

    lines.append("")
    lines.append("=" * 100)

    output = "\n".join(lines)
    print(output)

    # 保存到文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', result['title'])[:30]
    result_file = output_dir / f"{safe_title}_{timestamp}.txt"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(output)
        f.write(f"\n\n原始链接: {url}\n")
        f.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"\n💾 结果已保存: {result_file}")

    # 下载图片
    if result['images']:
        print(f"\n📥 开始下载图片...")
        img_dir = output_dir / f"{safe_title}_{timestamp}_images"
        img_dir.mkdir(exist_ok=True)

        headers = {'Referer': 'https://www.xiaohongshu.com/'}

        for i, img_url in enumerate(result['images'], 1):
            print(f"   [{i}/{len(result['images'])}] ", end='', flush=True)
            try:
                resp = requests.get(img_url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    ext = '.png' if 'png' in resp.headers.get('Content-Type', '') else '.jpg'
                    filepath = img_dir / f"image_{i:02d}{ext}"
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    size = len(resp.content) / 1024
                    print(f"✅ {size:.1f}KB")
                else:
                    print(f"❌ HTTP {resp.status_code}")
            except Exception as e:
                print(f"❌ {e}")

        print(f"💾 图片已保存: {img_dir}")


def main():
    print("\n" + "=" * 100)
    print("🔍 小红书图文笔记提取测试")
    print("=" * 100)
    print()

    if not test_url:
        print("❌ 请先在脚本中设置 test_url 变量")
        print()
        print("📝 使用方法:")
        print("   1. 打开小红书APP或网页")
        print("   2. 找到一个图文笔记（非视频）")
        print("   3. 点击分享 -> 复制链接")
        print("   4. 将链接粘贴到脚本的 test_url 变量中")
        print()
        print("💡 链接示例:")
        print("   https://www.xiaohongshu.com/explore/xxxxxx?xsec_token=xxxxx")
        return

    result = extract_xhs_images(test_url)

    if result and result['images']:
        format_and_save(result, test_url)
    else:
        print("\n❌ 提取失败或未找到图片")
        print()
        print("可能原因:")
        print("   1. 链接缺少 xsec_token 参数")
        print("   2. 笔记是视频类型")
        print("   3. 链接已过期")
        print()
        print("请检查链接是否完整且包含 xsec_token 参数")


if __name__ == "__main__":
    main()
