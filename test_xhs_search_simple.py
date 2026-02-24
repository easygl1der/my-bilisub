#!/usr/bin/env python3
"""
小红书搜索测试 - 简化版用于调试
"""

import asyncio
import sys
import re
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

PROJECT_DIR = Path(__file__).parent


def read_xhs_cookie_string() -> str:
    """从 config/cookies.txt 读取小红书Cookie（返回字符串格式）"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        return ""

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 xiaohongshu_full= 格式
    match = re.search(r'xiaohongshu_full=([^\n]+)', content)
    if match:
        return match.group(1)

    # 查找 [xiaohongshu] 部分
    xhs_section = re.search(r'\[xiaohongshu\](.*?)\[', content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        cookies = []
        for line in section.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                cookies.append(f"{key.strip()}={value.strip()}")
        return '; '.join(cookies)

    return ""


async def search_xhs(keyword: str, headless: bool = False):
    """小红书搜索测试"""

    print(f"\n{'='*70}")
    print(f"  小红书搜索测试")
    print(f"{'='*70}")
    print(f"\n搜索关键词: {keyword}")
    print(f"无头模式: {headless}\n")

    # 读取Cookie
    cookie = read_xhs_cookie_string()
    if cookie:
        print(f"✅ Cookie已读取 ({len(cookie)} 字符)")
    else:
        print("⚠️  未找到Cookie")

    # 启动浏览器
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    # 设置Cookie
    if cookie:
        try:
            cookies = []
            for item in cookie.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies.append({
                        'name': key,
                        'value': value,
                        'domain': '.xiaohongshu.com',
                        'path': '/'
                    })
            await context.add_cookies(cookies)
            print(f"✅ Cookie已设置 ({len(cookies)} 个)\n")
        except Exception as e:
            print(f"⚠️  Cookie设置失败: {e}\n")

    page = await context.new_page()
    print("✅ 浏览器已启动\n")

    # 访问小红书主页
    print("📄 访问小红书主页...")
    try:
        await page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)

        # 检查登录状态
        page_content = await page.content()
        if '登录' in page_content and '注册' in page_content:
            print("⚠️  检测到未登录状态")
            print("💡 请手动登录或更新Cookie\n")
            if not headless:
                print("⏳ 等待30秒供手动登录...")
                await asyncio.sleep(30)
        else:
            print("✅ 已登录\n")
    except Exception as e:
        print(f"⚠️  主页加载问题: {e}\n")

    # 访问搜索页面
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&type=51"
    print(f"🔍 访问搜索页面: {search_url}")
    try:
        await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        print("✅ 搜索页面加载完成\n")
    except Exception as e:
        print(f"⚠️  搜索页面加载问题: {e}\n")

    # 获取页面标题
    title = await page.title()
    print(f"📋 页面标题: {title}\n")

    # 获取页面URL
    url = page.url
    print(f"🔗 当前URL: {url}\n")

    # 检查页面内容
    print("📊 检查页面内容...")
    page_content = await page.content()
    print(f"   页面内容长度: {len(page_content)} 字符")

    # 检查是否有错误提示
    if '出错' in page_content or '错误' in page_content or '访问受限' in page_content:
        print("   ⚠️  检测到错误提示")
    else:
        print("   ✅ 无明显错误提示")

    # 查找笔记链接
    print("\n🔍 查找笔记链接...")
    links = await page.evaluate('''
        () => {
            const result = [];

            // 查找所有带 xsec_token 的链接
            const allLinks = document.querySelectorAll('a[href*="xsec_token"]');

            console.log('找到的所有带xsec_token的链接数量:', allLinks.length);

            allLinks.forEach(a => {
                result.push({
                    href: a.href,
                    text: a.textContent?.substring(0, 50) || ''
                });
            });

            return result;
        }
    ''')

    print(f"   找到 {len(links)} 个链接\n")

    if links:
        print("📋 前5个链接:")
        for i, link in enumerate(links[:5], 1):
            print(f"   {i}. {link['href']}")
            print(f"      文本: {link['text'][:50]}...")

    # 滚动加载更多内容
    print("\n📜 滚动加载更多内容...")
    for i in range(3):
        try:
            await asyncio.sleep(2)
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            print(f"   滚动 {i+1}/3")
        except Exception as e:
            print(f"   滚动失败: {e}")
            break

    await asyncio.sleep(3)

    # 再次查找链接
    print("\n🔍 滚动后再次查找笔记链接...")
    links_after_scroll = await page.evaluate('''
        () => {
            const result = [];
            const allLinks = document.querySelectorAll('a[href*="xsec_token"]');

            allLinks.forEach(a => {
                result.push({
                    href: a.href,
                    text: a.textContent?.substring(0, 50) || ''
                });
            });

            return result;
        }
    ''')

    print(f"   找到 {len(links_after_scroll)} 个链接\n")

    if links_after_scroll:
        print("📋 前5个链接:")
        for i, link in enumerate(links_after_scroll[:5], 1):
            print(f"   {i}. {link['href']}")
            print(f"      文本: {link['text'][:50]}...")

    # 保存页面HTML用于调试
    output_dir = PROJECT_DIR / "output" / "xhs_search_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_file = output_dir / f"debug_{keyword}_{timestamp}.html"

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(page_content)

    print(f"\n📁 页面HTML已保存: {html_file}")

    # 保持浏览器打开（如果不是无头模式）
    if not headless:
        print("\n⏳ 浏览器将保持打开60秒，请查看页面内容...")
        await asyncio.sleep(60)

    # 关闭浏览器
    await browser.close()
    await playwright.stop()
    print("\n✅ 测试完成")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='小红书搜索测试')
    parser.add_argument('--keyword', type=str, default='旅行', help='搜索关键词')
    parser.add_argument('--headless', action='store_true', help='使用无头模式')

    args = parser.parse_args()

    asyncio.run(search_xhs(args.keyword, args.headless))
