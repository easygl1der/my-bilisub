#!/usr/bin/env python3
"""
小红书响应数据查看工具

用Cookie访问小红书，提取HTML中的笔记链接（带xsec_token）
"""

import sys
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_DIR = Path(__file__).parent.parent


def read_xhs_cookie():
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


async def main():
    """主函数"""

    cookie = read_xhs_cookie()
    if not cookie:
        print("⚠️  未找到Cookie，将使用无Cookie模式（需要手动登录）")

    async with async_playwright() as p:
        print("🌐 启动浏览器...")
        browser = await p.chromium.launch(headless=False)
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
                print(f"✅ Cookie已设置 ({len(cookies)} 个)")
            except Exception as e:
                print(f"⚠️  Cookie设置失败: {e}")

        page = await context.new_page()
        print("✅ 浏览器已启动")

        # 访问小红书首页
        print()
        print("📄 访问小红书首页...")
        try:
            await page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)  # 等待3秒
        except Exception as e:
            print(f"❌ 页面加载失败: {e}")
            await browser.close()
            return

        # 检查登录状态
        page_content = await page.content()
        if '登录' in page_content and '注册' in page_content:
            print()
            print("⚠️  检测到未登录状态")
            print("💡 请在浏览器中手动登录")
            print("⏳ 等待90秒...登录完成后会自动继续")
            await asyncio.sleep(90)
            print("✅ 继续执行...")

        # 输出完整HTML
        print()
        print("=" * 70)
        print("  HTML内容（前2000字符）")
        print("=" * 70)
        print()
        print(page_content[:2000])
        print()

        # 保存完整HTML到文件
        output_file = PROJECT_DIR / "output" / "xhs_page.html"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(page_content)
        print(f"📁 完整HTML已保存到: {output_file}")
        print()

        # 提取所有笔记链接（带 xsec_token）
        print("=" * 70)
        print("  从HTML中提取的完整链接（带xsec_token）")
        print("=" * 70)
        print()

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
                        const idMatch = href.match(/\\/explore\\/([a-f0-9]{24})/);
                        if (!idMatch) return;

                        const noteId = idMatch[1];

                        // 去重
                        if (seen.has(noteId)) return;
                        seen.add(noteId);

                        // 直接返回完整URL（带xsec_token）
                        result.push(href);
                    }
                });

                return result;
            }
        ''')

        print(f"找到 {len(links)} 个链接\n")

        # 输出完整链接
        for link in links:
            print(link)

        # 保存到文件
        output_file = PROJECT_DIR / "output" / "xhs_links.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for link in links:
                f.write(link + '\n')

        print()
        print("=" * 70)
        print(f"📁 已保存到: {output_file}")
        print("=" * 70)

        await browser.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
