#!/usr/bin/env python3
"""
简化的 B站首页推荐采集测试脚本
直接使用 playwright 和 httpx，避免 MediaCrawler 的复杂依赖
"""

import sys
import asyncio
import json
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

from playwright.async_api import async_playwright
import httpx

# 读取Cookie
def read_bilibili_cookie():
    """从 config/cookies.txt 读取 Bilibili Cookie"""
    cookie_file = Path(__file__).parent / "config" / "cookies.txt"
    if not cookie_file.exists():
        print("Cookie文件不存在")
        return ""

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 [bilibili] 部分
    in_bilibili_section = False
    cookies = {}
    for line in content.split('\n'):
        line = line.strip()
        if line == '[bilibili]':
            in_bilibili_section = True
            continue
        elif line.startswith('['):
            in_bilibili_section = False
            continue
        elif in_bilibili_section and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            cookies[key.strip()] = value.strip()

    # 优先使用 bilibili_full
    if 'bilibili_full' in cookies:
        return cookies['bilibili_full']

    # 否则构建Cookie字符串
    return '; '.join([f"{k}={v}" for k, v in cookies.items() if not k.endswith('_full')])

# 测试登录状态
async def test_login(cookie_str):
    """测试 Cookie 是否有效"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
        "Cookie": cookie_str
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.bilibili.com/x/web-interface/nav",
                headers=headers
            )
            data = response.json()

            if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                print("登录成功！")
                user_data = data.get("data", {})
                if user_data.get("uname"):
                    print(f"  用户名: {user_data.get('uname')}")
                if user_data.get("mid"):
                    print(f"  用户ID: {user_data.get('mid')}")
                return True
            else:
                print("登录失败：Cookie无效或已过期")
                return False
    except Exception as e:
        print(f"登录测试失败: {e}")
        return False

# 解析视频卡片
def parse_video_cards(page_content):
    """从页面内容解析视频卡片"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_content, 'html.parser')

    videos = []
    # 查找视频卡片
    video_cards = soup.select('.bili-video-card')

    for card in video_cards:
        # 获取BV号
        video_link = card.select_one('a[href*="/video/BV"]')
        if not video_link:
            continue

        href = video_link.get('href', '')
        if 'BV' in href:
            bvid = href.split('BV')[1].split('?')[0].split('/')[0]
            bvid = 'BV' + bvid
        else:
            continue

        # 获取标题
        title_elem = card.select_one('.bili-video-card__info--tit')
        if not title_elem:
            title_elem = card.select_one('a[href*="/video/BV"]')

        if title_elem:
            title = title_elem.get('title', '') or title_elem.get_text(strip=True)
        else:
            title = ""

        # 获取UP主信息
        uploader_elem = card.select_one('.bili-video-card__info--author')
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""

        # 获取UP主链接
        uploader_link = card.select_one('a[href*="space.bilibili.com"]')
        uploader_url = ""
        uploader_uid = ""
        if uploader_link:
            uploader_url = uploader_link.get('href', '')
            if uploader_url.startswith('//'):
                uploader_url = 'https:' + uploader_url

            # 提取UID
            if "space.bilibili.com/" in uploader_url:
                uid_part = uploader_url.split("space.bilibili.com/")[-1].split("?")[0].split("/")[0]
                uploader_uid = uid_part

        video_info = {
            "bvid": bvid,
            "title": title,
            "uploader": uploader,
            "uploader_url": uploader_url,
            "uploader_uid": uploader_uid,
            "video_url": f"https://www.bilibili.com/video/{bvid}",
        }
        videos.append(video_info)

    return videos

# 主函数
async def main():
    print("=" * 60)
    print("B站首页推荐采集测试（简化版）")
    print("=" * 60)
    print()

    # 读取Cookie
    print("读取 Cookie...")
    cookie_str = read_bilibili_cookie()
    print(f"Cookie 长度: {len(cookie_str)} 字符")
    print()

    # 测试登录
    print("测试登录状态...")
    is_logged_in = await test_login(cookie_str)
    print()

    if not is_logged_in:
        print("警告: 登录失败，继续尝试采集...")
        print()

    # 配置参数
    REFRESH_COUNT = 2
    MAX_VIDEOS = 50

    print(f"配置: 刷新 {REFRESH_COUNT} 次，最多采集 {MAX_VIDEOS} 个视频")
    print()

    # 启动浏览器
    print("启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # 设置 Cookie
        # 将 Cookie 字符串转换为 Playwright 格式
        cookies_list = []
        for cookie_pair in cookie_str.split(';'):
            if '=' in cookie_pair:
                name, value = cookie_pair.strip().split('=', 1)
                cookies_list.append({
                    'name': name,
                    'value': value,
                    'domain': '.bilibili.com',
                    'path': '/'
                })

        await context.add_cookies(cookies_list)

        page = await context.new_page()

        # 采集首页推荐
        all_videos = []
        for i in range(REFRESH_COUNT):
            print(f"第 {i+1}/{REFRESH_COUNT} 次刷新...")
            await page.goto("https://www.bilibili.com")
            await page.wait_for_timeout(3000)  # 等待页面加载

            # 获取页面内容
            content = await page.content()

            # 保存 HTML 用于调试
            debug_file = Path(__file__).parent / "debug_homepage.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  已保存页面 HTML 到: {debug_file}")

            # 解析视频
            videos = parse_video_cards(content)
            print(f"  找到 {len(videos)} 个视频")

            # 去重（按BV号）
            seen_bvids = {v['bvid'] for v in all_videos}
            for video in videos:
                if video['bvid'] not in seen_bvids:
                    all_videos.append(video)
                    seen_bvids.add(video['bvid'])

            if len(all_videos) >= MAX_VIDEOS:
                break

            # 滚动页面触发加载
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        await browser.close()

    print()
    print("=" * 60)
    print("采集结果")
    print("=" * 60)
    print(f"共采集到 {len(all_videos)} 个视频")
    print()

    if all_videos:
        print("数据结构预览:")
        print(json.dumps(all_videos[0], ensure_ascii=False, indent=2))
        print()

        print("-" * 60)
        print(f"{'序号':<4} {'BV号':<14} {'标题':<25} {'UP主':<12} {'UID':<10}")
        print("-" * 60)
        for i, video in enumerate(all_videos[:20], 1):
            bvid = video.get('bvid', '')[:14]
            title = video.get('title', '')[:22] + '...' if len(video.get('title', '')) > 22 else video.get('title', '')
            uploader = video.get('uploader', '')[:10] + '...' if len(video.get('uploader', '')) > 10 else video.get('uploader', '')
            uid = video.get('uploader_uid', '')[:10]
            print(f"{i:<4} {bvid:<14} {title:<25} {uploader:<12} {uid:<10}")

            if video.get('uploader_url'):
                print(f"     └─ UP主主页: {video.get('uploader_url')}")

        # 保存到 JSON
        output_file = Path(__file__).parent / "homepage_recommend_videos.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_videos, f, ensure_ascii=False, indent=2)
        print()
        print(f"已保存到: {output_file}")

    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
