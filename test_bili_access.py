#!/usr/bin/env python3
"""
测试 Playwright 访问 B站 首页
"""
import asyncio
import sys
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


async def test():
    print("启动浏览器...")
    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )

    page = await context.new_page()

    print("访问 B站 首页...")
    await page.goto('https://www.bilibili.com', wait_until='networkidle')
    print("页面加载完成")

    # 等待一下让用户看到
    await asyncio.sleep(3)

    # 打印页面标题
    title = await page.title()
    print(f"页面标题: {title}")

    # 尝试查找视频卡片
    print("\n尝试查找视频卡片...")

    # 尝试多种选择器
    selectors = [
        "a.bvideo-card",
        ".video-card",
        ".feed-card",
        "a[href*='/video/BV']",
        ".bili-video-card",
    ]

    for selector in selectors:
        try:
            count = await page.locator(selector).count()
            print(f"  {selector}: 找到 {count} 个")
            if count > 0:
                # 获取第一个卡片的内容
                first = page.locator(selector).first
                text = await first.inner_text()
                href = await first.get_attribute("href")
                print(f"    第一个: {text[:50]}...")
                print(f"    链接: {href}")
        except Exception as e:
            print(f"  {selector}: 错误 - {e}")

    # 打印页面结构片段
    print("\n页面 HTML 片段 (前2000字符):")
    html = await page.content()
    print(html[:2000])

    print("\n按回车关闭浏览器...")
    input()

    await browser.close()
    await playwright.stop()


if __name__ == "__main__":
    asyncio.run(test())
