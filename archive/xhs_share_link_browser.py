#!/usr/bin/env python3
"""
小红书分享链接生成工具（浏览器版）

使用 Playwright 自动化浏览器来获取 xhslink.com 分享链接

使用方法:
    python xhs_share_link_browser.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"
    python xhs_share_link_browser.py --csv notes.csv
"""

import asyncio
import sys
import re
import json
import csv
import argparse
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ 未安装 playwright")
    print("请运行: pip install playwright && playwright install chromium")
    sys.exit(1)


# ==================== 配置 ====================

COOKIE_FILE = Path(__file__).parent / "config" / "cookies_xhs.json"


# ==================== Cookie 处理 ====================

def load_cookies_from_file(cookie_file: Path) -> list:
    """从文件加载 Cookies"""
    if cookie_file.exists():
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []


def save_cookies_to_file(cookies: list, cookie_file: Path):
    """保存 Cookies 到文件"""
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookie_file, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def parse_cookies_txt(cookie_file: Path) -> list:
    """从 cookies.txt 解析 Cookie"""
    cookies = []
    if cookie_file.exists():
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 查找 [xiaohongshu] 部分
                start = content.find('[xiaohongshu]')
                if start >= 0:
                    end = content.find('\n[', start + 1)
                    if end == -1:
                        end = len(content)
                    xhs_section = content[start:end]

                    for line in xhs_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and not line.startswith('['):
                            key, value = line.split('=', 1)
                            cookies.append({
                                'name': key.strip(),
                                'value': value.strip(),
                                'domain': '.xiaohongshu.com',
                                'path': '/'
                            })
        except:
            pass
    return cookies


# ==================== 分享链接获取 ====================

async def get_share_link(browser, note_id: str, cookies: list = None) -> dict:
    """
    获取小红书分享链接

    Args:
        browser: Playwright 浏览器实例
        note_id: 笔记ID
        cookies: Cookie 列表（可选）

    Returns:
        {'success': bool, 'share_url': str, 'error': str}
    """
    result = {'success': False, 'share_url': '', 'error': ''}

    url = f"https://www.xiaohongshu.com/explore/{note_id}"

    try:
        page = await browser.new_page()

        # 设置 Cookies
        if cookies:
            await page.context.add_cookies(cookies)

        # 导航到页面
        response = await page.goto(url, wait_until='networkidle', timeout=30000)

        if response.status != 200:
            result['error'] = f"页面访问失败: {response.status}"
            await page.close()
            return result

        # 等待页面加载
        await asyncio.sleep(2)

        # 尝试多种方式获取分享链接

        # 方法1: 从页面 HTML 中查找
        html = await page.content()

        share_patterns = [
            r'"shareUrl":"([^"]+)"',
            r'"share_url":"([^"]+)"',
            r'"shortUrl":"([^"]+)"',
            r'"short_url":"([^"]+)"',
            r'xhslink\.com/([a-zA-Z0-9]+)',
        ]

        for pattern in share_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                share_candidate = match.replace(r'\/', '/')
                if 'xhslink.com' in share_candidate:
                    result['success'] = True
                    result['share_url'] = share_candidate
                    await page.close()
                    return result

        # 方法2: 尝试点击分享按钮（如果已登录）
        try:
            # 查找分享按钮
            share_selectors = [
                'button:has-text("分享")',
                '[class*="share"]',
                '[data-testid*="share"]',
                'span:has-text("分享")',
            ]

            for selector in share_selectors:
                share_btn = page.locator(selector).first
                if await share_btn.count() > 0:
                    # 点击分享按钮
                    await share_btn.click(timeout=5000)
                    await asyncio.sleep(1)

                    # 查找复制链接按钮
                    copy_selectors = [
                        'button:has-text("复制链接")',
                        'span:has-text("复制链接")',
                        '[class*="copy"]',
                    ]

                    for copy_selector in copy_selectors:
                        copy_btn = page.locator(copy_selector).first
                        if await copy_btn.count() > 0:
                            # 获取分享链接文本
                            share_text = await copy_btn.get_attribute('data-clipboard-text') or ''
                            if not share_text:
                                # 尝试从页面中查找
                                share_text = await page.evaluate("""
                                    () => {
                                        // 查找包含 xhslink 的文本
                                        const walker = document.createTreeWalker(
                                            document.body,
                                            NodeFilter.SHOW_TEXT,
                                            null,
                                            false
                                        );
                                        let node;
                                        while (node = walker.nextNode()) {
                                            if (node.nodeValue && node.nodeValue.includes('xhslink.com')) {
                                                return node.nodeValue.trim();
                                            }
                                        }
                                        return '';
                                    }
                                """)

                            if share_text and 'xhslink.com' in share_text:
                                result['success'] = True
                                result['share_url'] = share_text
                                await page.close()
                                return result

                    break
        except Exception as e:
            pass  # 分享按钮点击失败，继续其他方法

        # 方法3: 尝试通过 API 获取（需要登录）
        try:
            share_url = await page.evaluate("""
                async () => {
                    try {
                        // 尝试调用分享 API
                        const response = await fetch('https://edith.xiaohongshu.com/api/sns/web/v1/note/share/short_url?note_id=' + window.location.pathname.split('/').pop(), {
                            method: 'GET',
                            credentials: 'include',
                            headers: {
                                'Accept': 'application/json'
                            }
                        });
                        const data = await response.json();
                        if (data.data && (data.data.short_url || data.data.share_url)) {
                            return data.data.short_url || data.data.share_url;
                        }
                    } catch (e) {
                        console.error(e);
                    }
                    return '';
                }
            """)

            if share_url and 'xhslink.com' in share_url:
                result['success'] = True
                result['share_url'] = share_url
                await page.close()
                return result
        except:
            pass

        # 如果都失败了
        result['error'] = "无法获取分享链接（可能需要登录或笔记不存在）"

        await page.close()

    except Exception as e:
        result['error'] = str(e)

    return result


async def process_url(url: str) -> dict:
    """处理单个链接"""
    result = {
        'original_url': url,
        'note_id': '',
        'share_url': '',
        'success': False,
        'error': ''
    }

    # 提取笔记ID
    patterns = [
        r'/explore/([a-f0-9]{24})',
        r'/discovery/item/([a-f0-9]{24})',
        r'([a-f0-9]{24})',
    ]

    note_id = ''
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            note_id = match.group(1)
            break

    if not note_id:
        result['error'] = "无法提取笔记ID"
        return result

    result['note_id'] = note_id

    # 加载 Cookies
    cookies = load_cookies_from_file(COOKIE_FILE)
    if not cookies:
        # 尝试从 cookies.txt 解析
        cookies = parse_cookies_txt(Path(__file__).parent / "config" / "cookies.txt")

    print(f"\n处理: {url[:60]}...")
    print(f"笔记ID: {note_id}")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        share_result = await get_share_link(browser, note_id, cookies)

        await browser.close()

        result.update(share_result)

    if result['success']:
        print(f"✅ 分享链接: {result['share_url']}")
    else:
        print(f"❌ {result['error']}")
        if cookies:
            print(f"💡 提示: Cookie 可能已过期，请尝试删除 {COOKIE_FILE.name} 重新登录")

    return result


async def process_csv(csv_path: str, output_path: str = None):
    """批量处理 CSV 文件"""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        return

    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_share_links.csv"

    # 读取 CSV
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        link_col = None
        for col in ['链接', 'url', 'link', 'video_url', 'note_url']:
            if col in fieldnames:
                link_col = col
                break

        if not link_col:
            print(f"❌ 未找到链接列")
            return

        rows = []
        for row in reader:
            url = row.get(link_col, '').strip()
            if url:
                rows.append({
                    'url': url,
                    'title': row.get('标题', '') or row.get('title', ''),
                    'row_data': row
                })

    print(f"\n找到 {len(rows)} 个链接")
    print("=" * 60)

    # 加载 Cookies
    cookies = load_cookies_from_file(COOKIE_FILE)
    if not cookies:
        cookies = parse_cookies_txt(Path(__file__).parent / "config" / "cookies.txt")

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for i, row_info in enumerate(rows, 1):
            print(f"\n[{i}/{len(rows)}]", end='')
            result = await process_url(row_info['url'])
            result['title'] = row_info['title']
            result['original_row'] = row_info['row_data']
            results.append(result)

            # 避免请求过快
            if i < len(rows):
                await asyncio.sleep(1)

        await browser.close()

    # 保存结果
    print(f"\n\n{'=' * 60}")
    print("📊 处理完成")
    print("=" * 60)

    success = sum(1 for r in results if r['success'])
    failed = len(results) - success
    print(f"总计: {len(results)} | 成功: {success} | 失败: {failed}")

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        original_fields = list(results[0].get('original_row', {}).keys())
        writer = csv.DictWriter(f, fieldnames=original_fields + ['笔记ID', '分享链接', '状态'])
        writer.writeheader()

        for r in results:
            row_data = r.get('original_row', {})
            row_data.update({
                '笔记ID': r['note_id'],
                '分享链接': r['share_url'],
                '状态': '成功' if r['success'] else '失败'
            })
            writer.writerow(row_data)

    print(f"📄 结果已保存: {output_path}")


# ==================== 登录功能 ====================

async def login_and_save_cookies():
    """使用浏览器登录并保存 Cookies"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("\n📱 打开小红书登录页面...")
        print("请在浏览器中完成登录操作")
        print("登录成功后，按 Ctrl+C 保存 Cookie 并退出\n")

        await page.goto("https://www.xiaohongshu.com")

        try:
            # 等待用户登录
            while True:
                await asyncio.sleep(1)
                # 检查是否已登录（可以通过检查特定元素或 URL 变化）
        except KeyboardInterrupt:
            print("\n\n💾 正在保存 Cookies...")

            cookies = await page.context.cookies()
            save_cookies_to_file(cookies, COOKIE_FILE)

            print(f"✅ Cookies 已保存到: {COOKIE_FILE}")
            print("📝 后续可以重用这些 Cookies 进行操作")

        await browser.close()


# ==================== 主程序 ====================

async def main():
    parser = argparse.ArgumentParser(
        description="小红书分享链接生成工具（浏览器版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 处理单个链接:
   python xhs_share_link_browser.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

2. 批量处理 CSV:
   python xhs_share_link_browser.py --csv notes.csv

3. 登录并保存 Cookie:
   python xhs_share_link_browser.py --login

注意事项:
- 首次使用需要执行 --login 登录并保存 Cookie
- Cookie 保存在 config/cookies_xhs.json
- Cookie 有效期通常为几天，过期后需要重新登录
        """
    )

    parser.add_argument('--url', help='单个小红书链接')
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('--json', help='JSON 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--login', action='store_true', help='登录并保存 Cookie')

    args = parser.parse_args()

    if args.login:
        await login_and_save_cookies()
        return

    if not any([args.url, args.csv, args.json]):
        parser.print_help()
        return

    print("=" * 60)
    print("小红书分享链接生成工具（浏览器版）")
    print("=" * 60)

    if args.url:
        await process_url(args.url)

    elif args.csv:
        await process_csv(args.csv, args.output)

    elif args.json:
        print("⚠️  JSON 处理功能暂未实现")
        print("请使用 CSV 格式")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
