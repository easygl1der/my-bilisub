#!/usr/bin/env python3
"""
AI自动刷小红书推荐并总结（完整版 - 性能优化）

功能：
1. 刷新小红书推荐页（自定义次数）
2. 采集推荐内容（视频/图文、作者信息）
3. 导出CSV
4. AI生成分析报告（可选）

性能优化：
- 智能滚动：自动检测页面是否还有新内容加载
- 优化等待策略：使用networkidle替代固定延迟
- 轮询登录检查：每5秒检查一次，最多等待90秒
- 优化DOM解析：减少不必要的DOM遍历
- 可选无头模式：--headless 运行更快（不显示浏览器）

使用示例:
    python ai_xiaohongshu_homepage.py

    # 仅采集（不生成AI报告）
    python ai_xiaohongshu_homepage.py --mode scrape

    # 完整流程（采集+AI分析）
    python ai_xiaohongshu_homepage.py --mode full

    # 使用无头模式（更快，适合自动任务）
    python ai_xiaohongshu_homepage.py --mode full --headless
"""

import argparse
import asyncio
import sys
import csv
import re
import os
from pathlib import Path
from datetime import datetime
import time

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

# ==================== 路径配置 ====================
# 使用根目录作为项目目录（无论脚本在哪个子目录运行）
PROJECT_DIR = Path(__file__).parent.parent  # 获取根目录
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
    cookie: str = "",
    headless: bool = False
) -> list:
    """使用Playwright爬取小红书推荐页"""
    notes_collected = []
    seen_urls = set()

    async with async_playwright() as p:
        # 启动浏览器（优化：禁用不必要的功能以提升速度）
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox'
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai'
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
            await page.goto('https://www.xiaohongshu.com/', wait_until='networkidle', timeout=60000)
        except Exception as e:
            print(f"⚠️  页面加载问题: {e}")
            print("💡 浏览器已打开，请检查网络连接")

        # 检查登录状态（优化：轮询检查而非固定等待90秒）
        async def check_logged_in():
            try:
                content = await page.content()
                return not ('登录' in content and '注册' in content)
            except:
                return False

        if not await check_logged_in():
            print("\n⚠️  检测到未登录状态")
            print("💡 请在浏览器中手动登录")
            print("⏳ 每5秒检查一次登录状态，最多等待90秒...")

            # 轮询检查登录状态，最多90秒
            max_wait = 18  # 18次 * 5秒 = 90秒
            for i in range(max_wait):
                await asyncio.sleep(5)
                if await check_logged_in():
                    print(f"✅ 已检测到登录！(耗时 {5 * (i+1)}秒)")
                    break
                if i == max_wait - 1:
                    print("⚠️  超时未检测到登录，继续执行...")

        print(f"\n🔄 开始采集推荐内容（刷新{refresh_count}次）...")

        for i in range(refresh_count):
            print(f"\n  刷新 {i+1}/{refresh_count}")

            # 优化：智能滚动，直到内容不再明显增加
            prev_height = 0
            scroll_stuck_count = 0
            max_scrolls = 10

            for scroll in range(max_scrolls):
                await page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')

                # 检查页面高度是否增加
                current_height = await page.evaluate('document.body.scrollHeight')
                if current_height == prev_height:
                    scroll_stuck_count += 1
                    if scroll_stuck_count >= 2:  # 连续2次高度不变则停止
                        break
                else:
                    scroll_stuck_count = 0
                    prev_height = current_height

                # 减少等待时间：首次等待稍长，后续等待时间递减
                wait_time = 0.5 if scroll < 3 else 0.3
                await asyncio.sleep(wait_time)

            # 减少内容加载等待时间
            await asyncio.sleep(1)

            # 获取所有链接和信息（优化版：减少DOM遍历，提前退出）
            try:
                notes_data = await page.evaluate('''
                    () => {
                        const notes = [];
                        const seen = new Set();
                        const MAX_NOTES = 50;  // 限制返回数量，减少数据处理时间

                        // 查找所有笔记卡片（使用更高效的选择器）
                        const links = document.querySelectorAll('a[href*="xsec_token"]');

                        for (const link of links) {
                            if (notes.length >= MAX_NOTES) break;

                            const url = link.href;
                            const card = link.closest('section, article, [class*="note"], [class*="card"], div[class*="item"]');
                            if (!card) continue;

                            // 从 URL 中提取 xsec_token 和 xsec_source
                            let xsecToken = '';
                            let xsecSource = 'pc_homepage';

                            try {
                                const urlParams = new URLSearchParams(url.split('?')[1]);
                                xsecToken = urlParams.get('xsec_token') || '';
                                if (urlParams.get('xsec_source')) {
                                    xsecSource = urlParams.get('xsec_source');
                                }
                            } catch (e) {}

                            // 提取笔记ID
                            let noteId = "";
                            if (url.includes('/explore/')) {
                                const idMatch = url.match(/\\/explore\\/([a-f0-9]{24})/);
                                if (idMatch) noteId = idMatch[1];
                            } else if (url.includes('/discovery/item/')) {
                                const idMatch = url.match(/\\/discovery\\/item\\/([a-f0-9]{24})/);
                                if (idMatch) noteId = idMatch[1];
                            }

                            if (!noteId || seen.has(noteId)) continue;
                            seen.add(noteId);

                            // 获取标题（简化版）
                            let title = "无标题";
                            const linkTitle = link.getAttribute('title');
                            if (linkTitle && linkTitle.length > 3) {
                                title = linkTitle.substring(0, 100);
                            } else {
                                // 仅查找最近级别的文本节点
                                const textNode = card.querySelector('span, div, p');
                                const text = textNode?.textContent?.trim();
                                if (text && text.length > 3 && text.length < 100 && !/^\\d+$/.test(text)) {
                                    title = text.substring(0, 100);
                                }
                            }

                            // 获取作者（简化版）
                            let author = "未知作者";
                            const authorNode = card.querySelector('a[href*="/user/profile/"], span.author');
                            if (authorNode) {
                                const text = authorNode.textContent?.trim();
                                if (text && text.length > 1 && text.length < 30 && !/\\d/.test(text)) {
                                    author = text;
                                }
                            }

                            // 获取点赞数（简化版）
                            let likes = "0";
                            const likeNode = card.querySelector('[class*="like"], [class*="count"]');
                            if (likeNode) {
                                const text = likeNode.textContent?.trim();
                                if (text && /^\\d+$/.test(text)) {
                                    const num = parseInt(text);
                                    if (num > 0 && num < 1000000) {
                                        likes = text;
                                    }
                                }
                            }

                            // 判断类型（优化版）
                            const type = card.querySelector('video, [class*="play"], [class*="duration"]') ||
                                        (card.textContent.includes(':') && /\\d+:\\d+/.test(card.textContent))
                                        ? 'video' : 'image';

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
                        }

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
                        '链接': note['url'],  # 将在下面重构
                        '完整链接': '',       # 新增字段
                        '笔记ID': note_id,
                        '作者': note['author'],
                        '点赞数': note['likes'],
                        '类型': note['type'],
                        'xsec_token': note.get('xsecToken', ''),  # 新增字段
                        'xsec_source': note.get('xsecSource', 'pc_homepage'),  # 新增字段
                        '爬取批次': i + 1,     # 新增字段：第几次爬取
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    # 重构完整链接（包含 xsec_token）
                    xsec_token = note.get('xsecToken', '')
                    xsec_source = note.get('xsecSource', 'pc_homepage')
                    if xsec_token:
                        full_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
                        note_data['完整链接'] = full_url
                        note_data['链接'] = full_url  # 更新链接字段为完整链接
                    else:
                        note_data['完整链接'] = note['url']

                    notes_collected.append(note_data)
                    type_emoji = '🎬' if note['type'] == 'video' else '🖼️'
                    print(f"    ✓ [{len(notes_collected)}] {type_emoji} {note['title']} | {note['author']} | {note['likes']}赞")

                    if len(notes_collected) >= max_notes:
                        break

            except Exception as e:
                print(f"    ⚠️  解析出错: {e}")

            # 刷新
            if i < refresh_count - 1:
                print("    刷新页面...")
                await page.reload(wait_until='networkidle', timeout=60000)
                await asyncio.sleep(1)  # 减少等待时间

        await browser.close()

    print(f"\n✅ 采集完成！共获取 {len(notes_collected)} 个笔记")
    return notes_collected


# ==================== CSV导出 ====================
def export_to_csv(notes, output_path):
    """导出笔记到CSV（增量模式）"""
    csv_columns = ['序号', '标题', '链接', '完整链接', '笔记ID', '作者', '点赞数', '类型', 'xsec_token', 'xsec_source', '爬取批次', '采集时间']

    # 读取现有数据（如果文件存在）
    existing_notes = []
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            existing_notes = list(reader)

    # 合并数据
    all_notes = existing_notes + notes

    # 重新编号
    for i, note in enumerate(all_notes, 1):
        note['序号'] = i

    # 写入所有数据
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(all_notes)

    print(f"📁 CSV已更新: {output_path}")
    print(f"   现有记录: {len(existing_notes)} 条")
    print(f"   新增记录: {len(notes)} 条")
    print(f"   总计: {len(all_notes)} 条")


# ==================== AI分析 ====================
def generate_ai_report(notes, output_dir):
    """使用Gemini生成AI报告"""
    import json

    print("\n🤖 开始AI分析...")

    # 检查Gemini是否可用
    _gemini_available = False
    use_new_sdk = False

    try:
        from google import genai as genai_new
        genai = genai_new
        use_new_sdk = True
        _gemini_available = True
    except ImportError:
        try:
            import google.generativeai as genai_old
            genai = genai_old
            use_new_sdk = False
            _gemini_available = True
        except:
            pass

    if not _gemini_available:
        print("⚠️  未安装google-generativeai，跳过AI分析")
        print("💡 安装命令: pip install google-generativeai")
        return

    # 配置API：优先从 bot_config.json 读取
    api_key = None
    config_file = PROJECT_DIR / "config" / "bot_config.json"

    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if 'gemini_api_key' in config:
                api_key = config['gemini_api_key']
                print(f"✅ API Key 读取成功: {api_key[:20]}...{api_key[-5:]}")
        except Exception as e:
            print(f"⚠️  读取配置文件失败: {e}")

    # 如果配置文件中没有，再尝试环境变量
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if api_key:
            print(f"✅ API Key 从环境变量读取: {api_key[:20]}...{api_key[-5:]}")

    if not api_key:
        print("⚠️  未设置 API Key")
        print("💡 方法1: 在 config/bot_config.json 中添加 gemini_api_key")
        print("💡 方法2: 设置环境变量: set GEMINI_API_KEY=your_key_here")
        return

    # 根据SDK版本使用不同的API
    if use_new_sdk:
        # 新 SDK (google-genai)
        client = genai.Client(api_key=api_key)
    else:
        # 旧 SDK (google.generativeai)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

    # 生成报告 - 使用与CSV相同的完整数据
    notes_text = "\n\n".join([
        f"{note.get('序号', i+1)}. 【{note.get('标题', '无标题')}】\n"
        f"   作者: {note.get('作者', '未知')}\n"
        f"   类型: {note.get('类型', '未知')}\n"
        f"   点赞: {note.get('点赞数', '0')}\n"
        f"   链接: {note.get('链接', '')}\n"
        f"   笔记ID: {note.get('笔记ID', '')}\n"
        f"   爬取批次: 第{note.get('爬取批次', 1)}次\n"
        f"   采集时间: {note.get('采集时间', '')}\n"
        for i, note in enumerate(notes)  # 分析所有笔记
    ])

    prompt = f"""你是一个专业的社交媒体内容分析师。请分析以下小红书推荐内容，生成一份详细的趋势报告。

小红书推荐内容：
{notes_text}

请生成以下格式的报告：

## 📊 小红书推荐趋势分析

### 🎯 内容概览
- 采集笔记数：{len(notes)}篇
- 视频占比：{sum(1 for n in notes if n.get('类型') == 'video')}篇 ({sum(1 for n in notes if n.get('类型') == 'video')/len(notes)*100:.1f}%)
- 图文占比：{sum(1 for n in notes if n.get('类型') == 'image')}篇 ({sum(1 for n in notes if n.get('类型') == 'image')/len(notes)*100:.1f}%)
- 爬取批次：共{max((n.get('爬取批次', 1) for n in notes), default=1)}次刷新

### 🔥 热门主题（Top 5）
基于笔记标题和内容，提取最受欢迎的5个主题

### 👥 热门作者（Top 5）
列举出现最频繁的5个作者，标注各自出现次数和平均点赞数

### 📈 趋势分析
基于所有笔记数据，分析当前小红书推荐的内容趋势：
- 热门话题分布
- 内容偏好特征
- 受欢迎的内容类型
- 不同爬取批次的内容差异（如果明显）

### 💎 值得关注的笔记
综合点赞数、内容质量，推荐3-5个值得深入阅读的笔记（附完整链接和推荐理由）

### 📋 数据洞察（可选）
如果有特别有趣的数据发现，请在此说明

请确保报告结构完整，每个部分都要有实质内容，数据引用要准确。"""

    try:
        if use_new_sdk:
            # 新 SDK 调用方式
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            report = response.text if hasattr(response, 'text') and response.text else str(response)
        else:
            # 旧 SDK 调用方式
            response = model.generate_content(prompt)
            report = response.text if hasattr(response, 'text') and response.text else "生成失败"

        # 保存报告
        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = output_dir / f"xiaohongshu_homepage_{date_str}_AI报告.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📁 AI报告已保存: {report_path}")

        # 在控制台显示摘要
        lines = report.split('\n')
        print("\n" + "=" * 70)
        print("  📖 AI分析报告")
        print("=" * 70)
        for line in lines[:20]:
            print(line)
        if len(lines) > 20:
            print(f"  ... 还有 {len(lines) - 20} 行")
        print("=" * 70)

    except Exception as e:
        print(f"❌ AI分析失败: {e}")


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
    parser.add_argument('--headless', action='store_true',
                       help='使用无头模式运行（更快，但不显示浏览器）')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  AI自动刷小红书推荐（优化版）")
    print(f"{'='*70}")
    print(f"\n📊 配置:")
    print(f"  • 刷新次数: {args.refresh_count}")
    print(f"  • 最多笔记: {args.max_notes}")
    print(f"  • 分析模式: {args.mode}")
    print(f"  • 无头模式: {'是' if args.headless else '否'}")

    # 读取Cookie
    cookie = read_xhs_cookie()
    if not cookie:
        print("\n⚠️  未找到Cookie，将使用无Cookie模式（需要手动登录）")

    # 采集数据（带性能监控）
    start_time = time.time()
    notes = await scrape_xiaohongshu_homepage(
        refresh_count=args.refresh_count,
        max_notes=args.max_notes,
        cookie=cookie,
        headless=args.headless
    )
    scrape_time = time.time() - start_time

    if not notes:
        print("\n❌ 未采集到任何笔记")
        return

    print(f"\n⏱️  采集耗时: {scrape_time:.1f}秒")
    print(f"📊 采集速度: {len(notes)/scrape_time:.2f} 笔记/秒")

    # 导出CSV
    date_str = datetime.now().strftime('%Y-%m-%d')
    csv_path = OUTPUT_DIR / f"xiaohongshu_homepage_{date_str}.csv"
    export_to_csv(notes, csv_path)

    # AI分析
    if args.mode == 'full':
        print(f"\n📊 准备进行 AI 分析，笔记数量: {len(notes)}")
        # 添加调试输出
        if notes:
            print(f"📋 第一条笔记数据示例:")
            first_note = notes[0]
            for key, value in first_note.items():
                print(f"   {key}: {value}")
        else:
            print("⚠️  notes 为空，无法进行 AI 分析")
        generate_ai_report(notes, OUTPUT_DIR)

    print(f"\n{'='*70}")
    print(f"  ✅ 完成！")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
