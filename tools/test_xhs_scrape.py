#!/usr/bin/env python3
"""
小红书爬虫测试脚本

功能：
- 测试爬取小红书推荐页
- 验证完整链接是否包含 xsec_token
- 验证爬取批次是否正确记录
- 输出测试结果到 CSV

使用示例:
    python tools/test_xhs_scrape.py
    python tools/test_xhs_scrape.py --refresh-count 2
"""

import argparse
import asyncio
import sys
import csv
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

# ==================== 路径配置 ====================
PROJECT_DIR = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_DIR / "output" / "xiaohongshu_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==================== Cookie 读取 ====================
def read_xhs_cookie():
    """从 config/cookies.txt 读取小红书Cookie"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        return ""

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 xiaohongshu_full= 格式
    import re
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


# ==================== 爬取测试 ====================
async def test_scrape(
    refresh_count: int = 2,
    max_notes: int = 20,
    cookie: str = ""
) -> list:
    """测试爬取功能"""
    notes_collected = []
    seen_urls = set()

    async with async_playwright() as p:
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

        # 检查登录状态
        page_content = await page.content()
        if '登录' in page_content and '注册' in page_content:
            print("\n⚠️  检测到未登录状态")
            print("💡 请在浏览器中手动登录")
            print("⏳ 等待90秒...登录完成后会自动继续")
            await asyncio.sleep(90)
            print("✅ 继续执行...")

        print(f"\n🔄 开始测试采集（刷新{refresh_count}次）...")

        for i in range(refresh_count):
            print(f"\n{'='*60}")
            print(f"  批次 {i+1}/{refresh_count}")
            print(f"{'='*60}")

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
                        const cards = document.querySelectorAll('section, article, [class*="note"], [class*="card"], div[class*="item"]');

                        cards.forEach(card => {
                            // 查找链接
                            const link = card.querySelector('a[href*="/explore/"], a[href*="/discovery/item/"]');
                            if (!link) return;

                            const url = link.href;

                            // 获取 xsec_token
                            let xsecToken = '';
                            let xsecSource = 'pc_homepage';

                            // 从 URL 中提取 xsec_token
                            try {
                                const urlParams = new URLSearchParams(url.split('?')[1]);
                                xsecToken = urlParams.get('xsec_token') || '';
                                if (urlParams.get('xsec_source')) {
                                    xsecSource = urlParams.get('xsec_source');
                                }
                            } catch (e) {}

                            // 提取笔记ID
                            let noteId = "";
                            const idMatch = url.match(/([a-f0-9]{32})/);
                            if (idMatch) noteId = idMatch[1];

                            if (!noteId) return;
                            if (seen.has(noteId)) return;
                            seen.add(noteId);

                            // 获取标题
                            let title = "无标题";
                            const textNodes = card.querySelectorAll('span, div, p, h1, h2, h3');
                            for (const node of textNodes) {
                                const text = node.textContent?.trim();
                                if (text && text.length > 3 && text.length < 100 && !/^\\d+$/.test(text)) {
                                    if (!text.includes('赞') && !text.includes('关注') &&
                                        !text.includes('分享') && !text.includes('收藏')) {
                                        title = text.substring(0, 100);
                                        break;
                                    }
                                }
                            }

                            // 获取作者
                            let author = "未知作者";
                            const authorNodes = card.querySelectorAll('span, a');
                            for (const node of authorNodes) {
                                const text = node.textContent?.trim();
                                if (text && text.length > 1 && text.length < 30) {
                                    if (!/\\d/.test(text)) {
                                        author = text;
                                        break;
                                    }
                                }
                            }

                            // 获取点赞数
                            let likes = "0";
                            const allNodes = card.querySelectorAll('*');
                            for (const node of allNodes) {
                                const text = node.textContent?.trim();
                                if (text && /^\\d+/.test(text)) {
                                    const parentClass = node.parentElement?.className || '';
                                    if (parentClass.includes('like') || parentClass.includes('count')) {
                                        const num = parseInt(text);
                                        if (num < 1000000 && num > 0) {
                                            likes = text;
                                            break;
                                        }
                                    }
                                }
                            }

                            // 判断类型
                            let type = 'image';
                            const hasVideo = card.querySelector('video');
                            if (hasVideo) {
                                type = 'video';
                            } else {
                                const hasPlayIcon = card.querySelector('[class*="play"], [class*="video"]');
                                if (hasPlayIcon) {
                                    type = 'video';
                                }
                            }

                            notes.push({
                                url: url,
                                noteId: noteId,
                                title: title,
                                author: author,
                                likes: likes,
                                type: type,
                                xsecToken: xsecToken,
                                xsecSource: xsecSource
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

                    # 构建完整链接
                    xsec_token = note.get('xsecToken', '')
                    xsec_source = note.get('xsecSource', 'pc_homepage')
                    note['original_url'] = note['url']  # 保存原始URL

                    if xsec_token:
                        full_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
                        note['完整链接'] = full_url
                    else:
                        note['完整链接'] = note['url']

                    # 添加批次信息
                    note['爬取批次'] = i + 1
                    note['采集时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    notes_collected.append(note)
                    type_emoji = '🎬' if note['type'] == 'video' else '🖼️'

                    # 显示详细信息
                    print(f"    [{len(notes_collected)}] {type_emoji} {note['title']}")
                    print(f"        笔记ID: {note_id}")
                    print(f"        作者: {note['author']} | 点赞: {note['likes']}")
                    print(f"        xsec_token: {'✅' if xsec_token else '❌ 无'}")
                    if xsec_token:
                        print(f"        原始URL: {note['original_url'][:80]}...")
                        print(f"        完整链接: {note['完整链接'][:80]}...")
                    else:
                        print(f"        链接: {note['url'][:80]}...")

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

    return notes_collected


# ==================== 测试报告 ====================
def generate_test_report(notes: list) -> str:
    """生成测试报告"""
    report_lines = [
        "# 小红书爬虫测试报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**采集数量**: {len(notes)}",
        "",
        "---",
        "",
    ]

    # 统计 xsec_token 覆盖率
    with_token = sum(1 for n in notes if n.get('xsecToken'))
    without_token = len(notes) - with_token
    token_rate = (with_token / len(notes) * 100) if notes else 0

    report_lines.extend([
        "## 📊 测试结果统计",
        "",
        f"- **总采集数**: {len(notes)}",
        f"- **包含 xsec_token**: {with_token} ({token_rate:.1f}%)",
        f"- **不含 xsec_token**: {without_token} ({100-token_rate:.1f}%)",
        "",
    ])

    # 批次分布
    batch_count = {}
    for note in notes:
        batch = note.get('爬取批次', 0)
        batch_count[batch] = batch_count.get(batch, 0) + 1

    report_lines.extend([
        "## 🔄 批次分布",
        "",
        "| 批次 | 数量 |",
        "|------|------|",
    ])
    for batch in sorted(batch_count.keys()):
        report_lines.append(f"| 第{batch}次 | {batch_count[batch]} |")
    report_lines.append("")

    # 类型分布
    video_count = sum(1 for n in notes if n.get('type') == 'video')
    image_count = len(notes) - video_count

    report_lines.extend([
        "## 📹 类型分布",
        "",
        f"- **视频**: {video_count} ({video_count/len(notes)*100:.1f}%)" if notes else "- **视频**: 0",
        f"- **图文**: {image_count} ({image_count/len(notes)*100:.1f}%)" if notes else "- **图文**: 0",
        "",
    ])

    # 完整数据列表
    report_lines.extend([
        "## 📋 完整数据列表",
        "",
        "| 序号 | 批次 | 类型 | 标题 | 作者 | 点赞 | xsec_token | 链接 |",
        "|------|------|------|------|------|------|------------|------|",
    ])

    for i, note in enumerate(notes, 1):
        type_emoji = '🎬' if note.get('type') == 'video' else '🖼️'
        title = note.get('title', '无标题')[:30] + '...' if len(note.get('title', '')) > 30 else note.get('title', '无标题')
        link = note.get('完整链接', '')[:50] + '...' if len(note.get('完整链接', '')) > 50 else note.get('完整链接', '')
        token_status = '✅' if note.get('xsecToken') else '❌'

        report_lines.append(f"| {i} | 第{note.get('爬取批次', 0)}次 | {type_emoji} | {title} | {note.get('author', '未知')} | {note.get('likes', '0')} | {token_status} | {link} |")

    return "\n".join(report_lines)


# ==================== CSV导出 ====================
def export_to_csv(notes, output_path):
    """导出测试结果到CSV"""
    csv_columns = [
        '序号', '批次', '标题', '原始链接', '完整链接', '笔记ID',
        '作者', '点赞数', '类型', 'xsec_token', 'xsec_source', '采集时间'
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()

        for i, note in enumerate(notes, 1):
            writer.writerow({
                '序号': i,
                '批次': note.get('爬取批次', ''),
                '标题': note.get('title', ''),
                '原始链接': note.get('original_url', ''),
                '完整链接': note.get('完整链接', ''),
                '笔记ID': note.get('noteId', ''),
                '作者': note.get('author', ''),
                '点赞数': note.get('likes', ''),
                '类型': note.get('type', ''),
                'xsec_token': note.get('xsecToken', ''),
                'xsec_source': note.get('xsecSource', ''),
                '采集时间': note.get('采集时间', ''),
            })

    print(f"\n📁 CSV已保存: {output_path}")


# ==================== 主程序 ====================
async def main():
    parser = argparse.ArgumentParser(description='小红书爬虫测试脚本')

    parser.add_argument('--refresh-count', type=int, default=2,
                       help='刷新次数（默认: 2）')
    parser.add_argument('--max-notes', type=int, default=20,
                       help='最多采集笔记数（默认: 20）')

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  小红书爬虫测试")
    print(f"{'='*60}")
    print(f"\n📊 配置:")
    print(f"  • 刷新次数: {args.refresh_count}")
    print(f"  • 最多笔记: {args.max_notes}")

    # 读取Cookie
    cookie = read_xhs_cookie()
    if not cookie:
        print("\n⚠️  未找到Cookie，将使用无Cookie模式（需要手动登录）")
    else:
        print("\n✅ 已读取Cookie")

    # 采集测试数据
    notes = await test_scrape(
        refresh_count=args.refresh_count,
        max_notes=args.max_notes,
        cookie=cookie
    )

    if not notes:
        print("\n❌ 未采集到任何笔记")
        return

    # 生成测试报告
    report = generate_test_report(notes)

    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"test_report_{timestamp}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📁 测试报告已保存: {report_path}")

    # 导出CSV
    csv_path = OUTPUT_DIR / f"test_result_{timestamp}.csv"
    export_to_csv(notes, csv_path)

    # 打印报告摘要
    print("\n" + "=" * 60)
    print("  📊 测试结果摘要")
    print("=" * 60)

    with_token = sum(1 for n in notes if n.get('xsecToken'))
    token_rate = (with_token / len(notes) * 100) if notes else 0

    print(f"  总采集数: {len(notes)}")
    print(f"  xsec_token 覆盖率: {token_rate:.1f}% ({with_token}/{len(notes)})")

    video_count = sum(1 for n in notes if n.get('type') == 'video')
    print(f"  视频: {video_count} | 图文: {len(notes) - video_count}")

    print(f"\n✅ 测试完成！")
    print(f"   报告: {report_path}")
    print(f"   CSV: {csv_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
