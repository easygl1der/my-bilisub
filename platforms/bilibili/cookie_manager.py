#!/usr/bin/env python3
"""
B站Cookie获取助手

使用方法:
1. 运行此脚本: python get_bilibili_cookie.py
2. 在打开的浏览器中登录你的B站账号
3. 登录完成后，按回车键
4. Cookie将自动保存到 config/cookies.txt
"""

import asyncio
from playwright.async_api import async_playwright
import sys
from pathlib import Path

# 设置项目根目录
project_root = Path(__file__).parent

async def get_cookie():
    print("=" * 60)
    print("🍪 B站Cookie获取助手")
    print("=" * 60)
    print()
    print("1. 正在打开浏览器...")
    print("2. 请在打开的浏览器窗口中登录你的B站账号")
    print("3. 登录完成后，回到这里按回车键")
    print()
    print("正在启动浏览器...")
    print()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.bilibili.com")

        input("按回车键继续（请确保已经完成登录）...")

        # 获取所有cookies
        cookies = await context.cookies()

        # 转换为Cookie字符串格式
        cookie_str = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

        # 读取现有的cookies.txt文件（如果存在）
        cookie_file = project_root / "config" / "cookies.txt"
        existing_content = ""
        if cookie_file.exists():
            with open(cookie_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()

        # 更新bilibili部分的Cookie
        lines = existing_content.split('\n')
        in_bilibili_section = False
        new_lines = []
        bilibili_section_found = False

        for line in lines:
            if line.strip() == '[bilibili]':
                in_bilibili_section = True
                bilibili_section_found = True
                new_lines.append(line)
                new_lines.append(f"bilibili_full={cookie_str}")
                continue
            elif line.strip().startswith('[') and in_bilibili_section:
                in_bilibili_section = False
            elif in_bilibili_section and line.strip().startswith('bilibili_full='):
                continue  # 跳过旧的bilibili_full行

            new_lines.append(line)

        # 如果没有找到[bilibili]部分，添加它
        if not bilibili_section_found:
            new_lines.append("")
            new_lines.append("[bilibili]")
            new_lines.append(f"bilibili_full={cookie_str}")

        # 保存到文件
        with open(cookie_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

        print()
        print("=" * 60)
        print(f"✅ Cookie已保存到: {cookie_file}")
        print(f"📝 Cookie长度: {len(cookie_str)} 字符")
        print(f"💡 提示: Cookie已添加到 [bilibili] 部分")
        print("=" * 60)

        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(get_cookie())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
