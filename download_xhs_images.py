#!/usr/bin/env python3
"""
小红书图片下载器 - 只下载笔记的实际内容图片
需要提供完整的小红书链接（带xsec_token）
用法: python download_xhs_images.py "小红书完整链接"
"""

import os
import sys
import re
import json
import time
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_xhs_images(url):
    """从小红书链接提取笔记的实际图片URL"""

    # 重要的：必须使用完整的 URL（包含 xsec_token）
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
    }

    print(f"📡 请求页面...")
    print(f"   URL: {url[:80]}...")

    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

    print(f"   状态码: {response.status_code}")
    print(f"   最终URL: {response.url[:80]}...")

    if response.status_code != 200:
        print(f"❌ 请求失败: {response.status_code}")
        return None, []

    # 检查是否被重定向到404
    if '/404?' in response.url or '你访问的页面不见了' in response.text:
        print(f"❌ 页面无法访问（反爬虫保护）")
        print(f"   原因：")
        print(f"   1. 链接缺少 xsec_token 参数")
        print(f"   2. 链接已过期或失效")
        print(f"   3. 需要登录才能查看")
        return None, []

    html = response.text
    print(f"✅ 页面获取成功 (长度: {len(html)})")

    # 提取标题
    title = "小红书图片"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
    print(f"📝 标题: {title[:50]}...")

    print(f"\n🔍 正在提取笔记图片...")

    # 查找 __INITIAL_STATE__ JSON 数据
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx == -1:
        print(f"❌ 未找到 __INITIAL_STATE__")
        return title, []

    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    # 尝试解析 JSON
    data = None
    try:
        data = json.loads(json_str)
        print(f"✅ JSON解析成功")
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON解析失败，使用正则搜索...")

    image_urls = []

    # 方法1: 从解析好的 JSON 中提取
    if data:
        try:
            # 路径: note.noteDetail.imageList
            note = data.get('note', {})
            note_detail = note.get('noteDetail', {})
            image_list = note_detail.get('imageList', [])

            if image_list:
                print(f"✅ 从 note.noteDetail.imageList 找到 {len(image_list)} 张图片")
                for img_obj in image_list:
                    if isinstance(img_obj, dict):
                        # 尝试多个字段
                        url = (img_obj.get('urlDefault') or
                               img_obj.get('url_default') or
                               img_obj.get('url') or
                               img_obj.get('infoList', [{}])[0].get('url') if isinstance(img_obj.get('infoList'), list) else None)
                        if url:
                            image_urls.append(url)
        except Exception as e:
            print(f"⚠️  方法1失败: {e}")

    # 方法2: 直接在 JSON 字符串中搜索 imageList
    if not image_urls:
        print(f"🔍 尝试直接搜索 imageList...")

        # 找到 imageList: [...] 部分 - 使用计数器匹配完整的数组
        start = json_str.find('"imageList"')
        if start >= 0:
            # 找到 [
            bracket_start = json_str.find('[', start)
            if bracket_start >= 0:
                # 手动匹配对应的 ]
                depth = 0
                i = bracket_start
                while i < len(json_str):
                    if json_str[i] == '[':
                        depth += 1
                    elif json_str[i] == ']':
                        depth -= 1
                        if depth == 0:
                            bracket_end = i
                            break
                    i += 1

                list_content = json_str[bracket_start+1:bracket_end]
                print(f"✅ 找到 imageList，内容长度: {len(list_content)}")

                # 只提取 urlDefault（默认/原图），跳过 urlPre 和 infoList
                # 每个 image 对象只取一个 urlDefault
                url_pattern = r'"urlDefault":"([^"]+)"'
                for match in re.finditer(url_pattern, list_content):
                    url = match.group(1)
                    if url:
                        image_urls.append(url)

                if image_urls:
                    print(f"✅ 提取到 {len(image_urls)} 张图片")

    # 方法3: 从整个 HTML 中搜索 sns-webpic 图片URL（备用）
    if not image_urls:
        print(f"🔍 尝试从HTML直接提取...")
        # 查找所有 sns-webpic 链接
        all_urls = re.findall(r'(https://sns-webpic[^\"\s\'<>]+)', html)
        # 去重
        unique_urls = list(set(all_urls))
        if unique_urls:
            print(f"✅ 找到 {len(unique_urls)} 个 sns-webpic URL")
            image_urls = unique_urls[:10]  # 限制数量

    # 去重并清理
    seen = set()
    unique_urls = []
    for url in image_urls:
        # 清理 URL
        url = url.split('?')[0]
        # 解码 Unicode 转义 (如 \u002F -> /)
        try:
            url = url.encode('utf-8').decode('unicode_escape')
        except:
            pass
        # 再次清理可能引入的问题
        url = url.replace(r'\/', '/')
        # 确保 https 协议
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        elif not url.startswith('https://'):
            continue
        if url not in seen and 'xhscdn' in url:
            seen.add(url)
            unique_urls.append(url)

    # 显示找到的URL用于调试
    print(f"📋 图片URL列表:")
    for i, u in enumerate(unique_urls, 1):
        print(f"   {i}. {u[:80]}...")

    return title, unique_urls


def download_images(url, output_dir="xhs_images"):
    """下载所有图片到指定目录"""

    result = extract_xhs_images(url)

    if not result:
        print(f"\n❌ 提取失败")
        return False

    title, image_urls = result

    if not image_urls:
        print(f"\n❌ 未找到图片")
        return False

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 清理标题作为文件夹名
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]

    print(f"\n📥 开始下载 {len(image_urls)} 张图片...")
    print(f"{'='*60}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    success_count = 0
    failed_count = 0

    for i, img_url in enumerate(image_urls, 1):
        try:
            print(f"[{i}/{len(image_urls)}] ", end='', flush=True)

            img_response = requests.get(img_url, headers=headers, timeout=30)

            if img_response.status_code == 200:
                # 确定文件扩展名
                content_type = img_response.headers.get('Content-Type', '')
                if 'png' in content_type or img_url.endswith('.png'):
                    ext = '.png'
                elif 'webp' in content_type or img_url.endswith('.webp'):
                    ext = '.webp'
                else:
                    ext = '.jpg'

                filename = f"{safe_title}_{i:02d}{ext}"
                filepath = output_path / filename

                with open(filepath, 'wb') as f:
                    f.write(img_response.content)

                size = len(img_response.content) / 1024
                print(f"✅ {size:.1f}KB")
                success_count += 1
            else:
                print(f"❌ HTTP {img_response.status_code}")
                failed_count += 1

        except Exception as e:
            print(f"❌ {str(e)[:30]}")
            failed_count += 1

        time.sleep(0.3)

    print(f"{'='*60}")
    print(f"\n🎉 下载完成!")
    print(f"   成功: {success_count} | 失败: {failed_count}")
    print(f"   保存位置: {output_path.absolute()}")

    return success_count > 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python download_xhs_images.py \"小红书完整链接\"")
        print("\n注意：必须使用完整的链接（包含 xsec_token 参数）")
        print("从小红书分享或复制链接获取完整URL")
        sys.exit(1)

    url = sys.argv[1]
    download_images(url)
