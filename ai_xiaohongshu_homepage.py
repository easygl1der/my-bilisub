#!/usr/bin/env python3
"""
AI自动刷小红书推荐并总结

一键完成：
1. 刷新小红书推荐页（自定义次数）
2. 采集推荐内容（视频/图文、作者信息）
3. 导出CSV
4. AI生成分析报告

使用示例:
    python ai_xiaohongshu_homepage.py
"""

import argparse
import asyncio
import sys
import csv
import re
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

# ==================== 路径配置 ====================
PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / "output" / "xiaohongshu_homepage"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Cookie 读取 ====================
def read_xhs_cookie():
    """从 config/cookies.txt 读取小红书Cookie"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        print("❌ Cookie文件不存在: config/cookies.txt")
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


# ==================== Playwright 采集 ====================
async def scrape_xiaohongshu_homepage(
    refresh_count: int = 3,
    max_notes: int = 50,
    cookie: str = ""
) -> list:
    """使用Playwright爬取小红书推荐页"""
    notes_collected = []
    seen_urls = set()

    async with async_playwright() as p:
        # 启动浏览器
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
                print("✅ Cookie已设置")
            except Exception as e:
                print(f"⚠️  Cookie设置失败: {e}")

        page = await context.new_page()

        print(f"\n📡 访问小红书首页...")
        try:
            await page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"⚠️  页面加载问题: {e}")
            print("💡 浏览器已打开，请检查网络连接")

        # 检查登录状态
        page_content = await page.content()
        if '登录' in page_content and '注册' in page_content:
            print("\n⚠️  检测到未登录状态")
            print("💡 请在浏览器中手动登录")
            print("⏳ 等待90秒...登录完成后会自动继续")
            await asyncio.sleep(90)
            print("✅ 继续执行...")

        print(f"\n🔄 开始采集推荐内容（刷新{refresh_count}次）...")

        for i in range(refresh_count):
            print(f"\n  刷新 {i+1}/{refresh_count}")

            # 滚动加载
            for scroll in range(10):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1)

            # 等待内容加载
            await asyncio.sleep(2)

            # 获取所有链接和信息
            try:
                notes_data = await page.evaluate('''
                    () => {
                        const notes = [];
                        const seen = new Set();

                        // 查找所有笔记卡片
                        const cards = document.querySelectorAll('section, section > div');

                        cards.forEach(card => {
                            const link = card.querySelector('a[href*="/explore/"]');
                            if (!link) return;

                            const url = link.href;
                            const idMatch = url.match(/\\/explore\\/([a-f0-9]+)/);
                            if (!idMatch) return;
                            const noteId = idMatch[1];

                            if (seen.has(noteId)) return;
                            seen.add(noteId);

                            // 尝试获取标题
                            let title = "无标题";
                            const titleElems = card.querySelectorAll('span, div[class*="title"]');
                            for (const elem of titleElems) {
                                const text = elem.textContent?.trim();
                                if (text && text.length > 3 && text.length < 100) {
                                    title = text.substring(0, 50);
                                    break;
                                }
                            }

                            // 尝试获取作者
                            let author = "未知作者";
                            const authorElems = card.querySelectorAll('span[class*="user"], span[class*="name"]');
                            for (const elem of authorElems) {
                                const text = elem.textContent?.trim();
                                if (text && text.length > 1 && text.length < 30) {
                                    author = text;
                                    break;
                                }
                            }

                            // 判断类型
                            const hasVideo = card.querySelector('video');
                            const type = hasVideo ? 'video' : 'image';

                            notes.push({
                                url: url,
                                noteId: noteId,
                                title: title,
                                author: author,
                                type: type
                            });
                        });

                        return notes;
                    }
                ''')

                print(f"    找到 {len(notes_data)} 个笔记")

                for note in notes_data:
                    note_id = note['noteId']

                    # 去重
                    if note_id in seen_urls:
                        continue
                    seen_urls.add(note_id)

                    note_data = {
                        '序号': len(notes_collected) + 1,
                        '标题': note['title'],
                        '链接': note['url'],
                        '笔记ID': note_id,
                        '作者': note['author'],
                        '点赞数': '0',
                        '类型': note['type'],
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    notes_collected.append(note_data)
                    print(f"    ✓ [{len(notes_collected)}] {note['type']} - {note['title']}")

                    if len(notes_collected) >= max_notes:
                        break

            except Exception as e:
                print(f"    ⚠️  解析出错: {e}")

            # 刷新
            if i < refresh_count - 1:
                print("    刷新页面...")
                await page.reload(wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(3)

        await browser.close()

    print(f"\n✅ 采集完成！共获取 {len(notes_collected)} 个笔记")
    return notes_collected


# ==================== CSV导出 ====================
def export_to_csv(notes, output_path):
    """导出笔记到CSV"""
    csv_columns = ['序号', '标题', '链接', '笔记ID', '作者', '点赞数', '类型', '采集时间']

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(notes)

    print(f"📁 CSV已保存: {output_path}")


# ==================== 主程序 ====================
async def main():
    parser = argparse.ArgumentParser(description='AI自动刷小红书推荐并总结')

    parser.add_argument('--refresh-count', type=int, default=3,
                       help='刷新次数（默认: 3）')
    parser.add_argument('--max-notes', type=int, default=50,
                       help='最多采集笔记数（默认: 50）')
    parser.add_argument('--mode', type=str, default='scrape',
                       choices=['scrape', 'full'],
                       help='模式: scrape=仅采集, full=采集+AI分析')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  AI自动刷小红书推荐")
    print(f"{'='*70}")
    print(f"\n📊 配置:")
    print(f"  • 刷新次数: {args.refresh_count}")
    print(f"  • 最多笔记: {args.max_notes}")
    print(f"  • 分析模式: {args.mode}")

    # 读取Cookie
    cookie = read_xhs_cookie()
    if not cookie:
        print("\n⚠️  未找到Cookie，将使用无Cookie模式（需要手动登录）")

    # 采集数据
    notes = await scrape_xiaohongshu_homepage(
        refresh_count=args.refresh_count,
        max_notes=args.max_notes,
        cookie=cookie
    )

    if not notes:
        print("\n❌ 未采集到任何笔记")
        return

    # 导出CSV
    date_str = datetime.now().strftime('%Y-%m-%d')
    csv_path = OUTPUT_DIR / f"xiaohongshu_homepage_{date_str}.csv"
    export_to_csv(notes, csv_path)

    # AI分析（待实现）
    if args.mode == 'full':
        print("\n⚠️  AI分析功能待实现")

    print(f"\n{'='*70}")
    print(f"  ✅ 完成！")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
