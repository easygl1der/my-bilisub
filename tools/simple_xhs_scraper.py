#!/usr/bin/env python3
"""
小红书简单爬虫 - 直接从HTML提取链接

只做一件事：用Cookie访问小红书，提取页面中带有xsec_token的笔记链接
"""

import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_DIR = Path(__file__).parent.parent


def read_xhs_cookie():
    """从 config/cookies.txt 读取小红书Cookie"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        return {}

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    import re
    cookies_dict = {}

    # 查找 [xiaohongshu] 部分
    xhs_section = re.search(r'\[xiaohongshu\](.*?)\[', content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        for line in section.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                cookies_dict[key.strip()] = value.strip()

    return cookies_dict


async def extract_xhs_links_from_html():
    """从小红书HTML页面提取链接"""

    cookies_dict = read_xhs_cookie()
    if not cookies_dict:
        print("❌ 未找到Cookie，请在 config/cookies.txt 中配置")
        return

    print("✅ Cookie已读取")
    print(f"   a1: {cookies_dict.get('a1', '')[:20]}...")
    print()

    async with async_playwright() as p:
        print("🌐 启动浏览器...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 添加Cookie
        cookies_list = []
        for key, value in cookies_dict.items():
            if not key or not value:
                continue
            cookies_list.append({
                'name': key,
                'value': value,
                'domain': '.xiaohongshu.com',
                'path': '/',
            })

        try:
            await context.add_cookies(cookies_list)
            print(f"✅ 已添加 {len(cookies_list)} 个 Cookie")
        except Exception as e:
            print(f"⚠️  添加Cookie时出错: {e}")

        page = await context.new_page()
        print("✅ 浏览器已启动")

        # 访问小红书首页
        print()
        print("📄 访问小红书首页...")
        try:
            await page.goto('https://www.xiaohongshu.com/', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)  # 等待5秒让内容加载
            print("✅ 页面加载完成")
        except Exception as e:
            print(f"❌ 页面加载失败: {e}")
            await browser.close()
            return

        # 检查登录状态
        page_content = await page.content()
        if '登录' in page_content and '注册' in page_content:
            print("⚠️  检测到未登录状态")
            print("💡 请更新 Cookie")
            await browser.close()
            return

        # 提取所有笔记链接
        print()
        print("=" * 70)
        print("  开始提取链接")
        print("=" * 70)

        # 方法1: 提取所有带 xsec_token 的链接
        links = await page.evaluate('''
            () => {
                const result = [];

                // 提取所有带 xsec_token 的 explore 链接
                const allLinks = document.querySelectorAll('a[href*="xsec_token"]');
                const seen = new Set();

                allLinks.forEach(a => {
                    const href = a.href;

                    // 只保留 /explore/ 开头的链接
                    if (href.includes('/explore/')) {
                        // 提取笔记ID
                        const idMatch = href.match(/\\/explore\\/([a-f0-9]{32})/);
                        if (!idMatch) return;

                        const noteId = idMatch[1];

                        // 提取 xsec_token
                        let xsecToken = '';
                        try {
                            const urlParams = new URLSearchParams(href.split('?')[1]);
                            xsecToken = urlParams.get('xsec_token') || '';
                        } catch (e) {}

                        // 去重
                        if (seen.has(noteId)) return;
                        seen.add(noteId);

                        result.push({
                            note_id: noteId,
                            full_url: href,
                            xsec_token: xsecToken
                        });
                    }
                });

                return result;
            }
        ''')

        print(f"\n✅ 找到 {len(links)} 个笔记链接\n")

        # 输出完整链接
        for i, link in enumerate(links, 1):
            print(link['full_url'])

        # 保存到文件
        output_file = PROJECT_DIR / "output" / "xhs_links.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for link in links:
                f.write(link['full_url'] + '\n')

        print("\n" + "=" * 70)
        print(f"📁 已保存到: {output_file}")
        print("=" * 70)

        await browser.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(extract_xhs_links_from_html())
