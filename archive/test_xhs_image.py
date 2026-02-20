#!/usr/bin/env python3
"""
测试小红书图片获取功能
用法: python test_xhs_image.py "小红书链接"
"""

import sys
import re
import json
import requests
from bs4 import BeautifulSoup

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def test_xhs_images(url):
    """测试获取小红书图片"""

    print(f"{'='*60}")
    print(f"测试链接: {url}")
    print(f"{'='*60}\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    image_urls = []

    # 方法1: 请求页面
    print("📡 步骤1: 请求页面...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   状态码: {response.status_code}")
        print(f"   页面长度: {len(response.text)} 字符")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        return

    html = response.text

    # 方法2: 从 __INITIAL_STATE__ 提取
    print("\n📡 步骤2: 解析 __INITIAL_STATE__...")
    initial_state_pattern = r'window\.__INITIAL_STATE__\s*=\s*({.+?});'
    match = re.search(initial_state_pattern, html)

    if match:
        try:
            initial_state = json.loads(match.group(1))
            print(f"   ✅ 找到 __INITIAL_STATE__")

            # 尝试多种路径
            paths = [
                initial_state.get('note', {}).get('noteDetail', {}).get('imageList', []),
                initial_state.get('note', {}).get('noteDetail', {}).get('images', []),
            ]

            for i, path in enumerate(paths, 1):
                if isinstance(path, list) and len(path) > 0:
                    print(f"   ✅ 路径{i}: 找到 {len(path)} 张图片")
                    for img_obj in path:
                        if isinstance(img_obj, dict):
                            img_url = (img_obj.get('urlDefault') or
                                      img_obj.get('url_default') or
                                      img_obj.get('url'))
                            if img_url:
                                image_urls.append(img_url)
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON解析失败: {e}")
    else:
        print(f"   ⚠️  未找到 __INITIAL_STATE__")

    # 方法3: 从 __INITIAL_SSR_STATE__ 提取
    print("\n📡 步骤3: 解析 __INITIAL_SSR_STATE__...")
    ssr_state_pattern = r'window\.__INITIAL_SSR_STATE__\s*=\s*({.+?});'
    match = re.search(ssr_state_pattern, html)

    if match:
        try:
            ssr_state = json.loads(match.group(1))
            print(f"   ✅ 找到 __INITIAL_SSR_STATE__")

            paths = [
                ssr_state.get('note', {}).get('noteDetailMap', {}),
                ssr_state.get('note', {}).get('detailMap', {}),
            ]

            for path_obj in paths:
                if isinstance(path_obj, dict):
                    for note_id, note_data in path_obj.items():
                        if isinstance(note_data, dict):
                            image_list = note_data.get('imageList') or note_data.get('images') or []
                            if isinstance(image_list, list) and len(image_list) > 0:
                                print(f"   ✅ 找到 {len(image_list)} 张图片 (SSR)")
                                for img_obj in image_list:
                                    if isinstance(img_obj, dict):
                                        img_url = (img_obj.get('urlDefault') or
                                                  img_obj.get('url_default') or
                                                  img_obj.get('url'))
                                        if img_url:
                                            image_urls.append(img_url)
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"   ⚠️  解析失败: {e}")

    # 方法4: 正则匹配图片URL
    print("\n📡 步骤4: 正则匹配 xhscdn 图片...")
    xhs_img_pattern = r'https?://[a-z0-9\-]*\.xhscdn\.com/[a-z0-9/\-]+\.(?:jpg|jpeg|png|webp)'
    found_urls = re.findall(xhs_img_pattern, html)

    if found_urls:
        # 去重
        unique_urls = list(set(found_urls))
        print(f"   ✅ 正则找到 {len(unique_urls)} 张图片")
        image_urls.extend(unique_urls)

    # 方法5: meta og:image
    print("\n📡 步骤5: meta 标签...")
    soup = BeautifulSoup(html, 'html.parser')
    meta_og_image = soup.find('meta', property='og:image')
    if meta_og_image:
        img_url = meta_og_image.get('content')
        print(f"   ✅ og:image: {img_url[:60]}...")
        if img_url:
            image_urls.append(img_url)

    # 汇总结果
    print(f"\n{'='*60}")
    print(f"📊 结果汇总")
    print(f"{'='*60}")

    # 去重
    seen = set()
    unique_images = []
    for img in image_urls:
        if img and isinstance(img, str) and img.startswith('http') and img not in seen:
            # 移除尺寸参数
            clean_url = img.split('?')[0]
            unique_images.append(clean_url)
            seen.add(clean_url)

    print(f"共找到 {len(unique_images)} 张唯一图片\n")

    if unique_images:
        for i, img_url in enumerate(unique_images, 1):
            print(f"{i}. {img_url}")

        # 测试下载第一张
        print(f"\n{'='*60}")
        print(f"📥 测试下载第一张图片...")
        print(f"{'='*60}")

        test_url = unique_images[0]
        try:
            img_response = requests.get(test_url, headers=headers, timeout=30)
            print(f"状态码: {img_response.status_code}")
            print(f"大小: {len(img_response.content)} bytes")
            print(f"Content-Type: {img_response.headers.get('Content-Type')}")

            if img_response.status_code == 200 and len(img_response.content) > 1000:
                print(f"✅ 下载成功！图片获取功能正常")
            else:
                print(f"⚠️  下载的文件可能是无效图片")
        except Exception as e:
            print(f"❌ 下载失败: {e}")
    else:
        print("❌ 未找到任何图片")
        print("\n可能原因:")
        print("1. 链接是视频类型（不是图文）")
        print("2. 小红书更改了页面结构")
        print("3. 需要登录才能访问")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_xhs_image.py \"小红书链接\"")
        print("示例: python test_xhs_image.py \"https://www.xiaohongshu.com/explore/xxxxx\"")
        sys.exit(1)

    test_xhs_images(sys.argv[1])
