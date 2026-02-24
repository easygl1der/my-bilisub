#!/usr/bin/env python3
"""
AI自动刷小红书推荐并总结（完整版）

功能：
1. 刷新小红书推荐页（自定义次数）
2. 采集推荐内容（视频/图文、作者信息）
3. 导出CSV
4. AI生成分析报告（可选）

使用示例:
    python ai_xiaohongshu_homepage.py

    # 仅采集（不生成AI报告）
    python ai_xiaohongshu_homepage.py --mode scrape

    # 完整流程（采集+AI分析）
    python ai_xiaohongshu_homepage.py --mode full
"""

import argparse
import asyncio
import sys
import csv
import re
import os
from pathlib import Path
from datetime import datetime

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

            # 获取所有链接和信息（最终版）
            try:
                notes_data = await page.evaluate('''
                    () => {
                        const notes = [];
                        const seen = new Set();

                        // 查找所有笔记卡片（使用更通用的选择器）
                        const cards = document.querySelectorAll('section, article, [class*="note"], [class*="card"], div[class*="item"]');

                        cards.forEach(card => {
                            // 直接查找带 xsec_token 的链接
                            const link = card.querySelector('a[href*="xsec_token"]');
                            if (!link) return;

                            const url = link.href;

                            // 从 URL 中提取 xsec_token 和 xsec_source
                            let xsecToken = '';
                            let xsecSource = 'pc_homepage';  // 默认来源为首页

                            try {
                                const urlParams = new URLSearchParams(url.split('?')[1]);
                                xsecToken = urlParams.get('xsec_token') || '';
                                if (urlParams.get('xsec_source')) {
                                    xsecSource = urlParams.get('xsec_source');
                                }
                            } catch (e) {
                                // URL 解析失败，继续使用空值
                            }

                            // 提取笔记ID
                            let noteId = "";
                            if (url.includes('/explore/')) {
                                const idMatch = url.match(/\\/explore\\/([a-f0-9]{24})/);
                                if (idMatch) noteId = idMatch[1];
                            } else if (url.includes('/discovery/item/')) {
                                const idMatch = url.match(/\\/discovery\\/item\\/([a-f0-9]{24})/);
                                if (idMatch) noteId = idMatch[1];
                            }

                            if (!noteId) return;
                            if (seen.has(noteId)) return;
                            seen.add(noteId);

                            // 获取标题（使用多种方法）
                            let title = "无标题";

                            // 方法1: 查找span或div中的文本
                            const textNodes = card.querySelectorAll('span, div, p, h1, h2, h3');
                            for (const node of textNodes) {
                                const text = node.textContent?.trim();
                                // 标题特征：3-100字符，不含数字序号
                                if (text && text.length > 3 && text.length < 100 && !/^\\d+$/.test(text)) {
                                    // 排除明显不是标题的内容
                                    if (!text.includes('赞') && !text.includes('关注') &&
                                        !text.includes('分享') && !text.includes('收藏')) {
                                        title = text.substring(0, 100);
                                        break;
                                    }
                                }
                            }

                            // 方法2: 从链接的title属性获取
                            if (title === "无标题") {
                                const linkTitle = link.getAttribute('title');
                                if (linkTitle && linkTitle.length > 3) {
                                    title = linkTitle.substring(0, 100);
                                }
                            }

                            // 获取作者
                            let author = "未知作者";
                            const authorNodes = card.querySelectorAll('span, a');
                            for (const node of authorNodes) {
                                const text = node.textContent?.trim();
                                // 作者特征：1-30字符，可能是人名
                                if (text && text.length > 1 && text.length < 30) {
                                    // 排除包含数字的（可能是点赞数）
                                    if (!/\\d/.test(text)) {
                                        author = text;
                                        break;
                                    }
                                }
                            }

                            // 获取点赞数（改进版）
                            let likes = "0";
                            const allNodes = card.querySelectorAll('*');
                            for (const node of allNodes) {
                                const text = node.textContent?.trim();
                                // 查找包含数字的节点（可能是点赞数）
                                if (text && /^\\d+/.test(text)) {
                                    // 验证父元素是否有like、count等class
                                    const parentClass = node.parentElement?.className || '';
                                    if (parentClass.includes('like') || parentClass.includes('count') ||
                                        parentClass.includes('interact')) {
                                        // 排除明显过大的数字
                                        const num = parseInt(text);
                                        if (num < 1000000 && num > 0) {
                                            likes = text;
                                            break;
                                        }
                                    }
                                }
                            }

                            // 判断类型（最终版）
                            let type = 'image';

                            // 方法1: 检查video标签
                            const hasVideo = card.querySelector('video');
                            if (hasVideo) {
                                type = 'video';
                            } else {
                                // 方法2: 检查是否有播放图标或时长标记
                                const hasPlayIcon = card.querySelector('[class*="play"], [class*="video"], svg[class*="play"]');
                                const hasDuration = card.textContent.includes(':') && card.textContent.match(/\\d+:\\d+/);
                                if (hasPlayIcon || hasDuration) {
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
                                xsecToken: xsecToken,      // 新增字段
                                xsecSource: xsecSource     // 新增字段
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
                await page.reload(wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(3)

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

    # 配置API（修正拼写：GEMINI -> GEMINI）
    api_key = os.environ.get('GEMINI_API_KEY', '')
    config_file = PROJECT_DIR / "config" / "bot_config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if 'gemini_api_key' in config:
                api_key = config['gemini_api_key']
        except:
            pass

    if not api_key:
        print("⚠️  未设置GEMINI_API_KEY")
        print("💡 设置: set GEMINI_API_KEY=your_key_here")
        return

    # 根据SDK版本使用不同的API
    if use_new_sdk:
        # 新 SDK (google-genai)
        client = genai.Client(api_key=api_key)
    else:
        # 旧 SDK (google.generativeai)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

    # 生成报告
    notes_text = "\n\n".join([
        f"{i+1}. {note.get('title', '无标题')}\n"
        f"   作者: {note.get('author', '未知')}\n"
        f"   类型: {note.get('type', '未知')}\n"
        f"   点赞: {note.get('likes', '0')}\n"
        f"   链接: {note.get('url', '')}\n"
        for i, note in enumerate(notes[:15])  # 只分析前15个
    ])

    prompt = f"""你是一个专业的社交媒体内容分析师。请分析以下小红书推荐内容，生成一份趋势报告。

小红书推荐内容：
{notes_text}

请生成以下格式的报告：

## 📊 小红书推荐趋势分析

### 🎯 内容概览
- 采集笔记数：{len(notes)}篇
- 视频占比：{notes.count(lambda x: x['type'] == 'video')}篇 ({notes.count(lambda x: x['type'] == 'video')/len(notes)*100:.1f}%)
- 图文占比：{notes.count(lambda x: x['type'] == 'image')}篇 ({notes.count(lambda x: x['type'] == 'image')/len(notes)*100:.1f}%)

### 🔥 热门主题（Top 5）
提取最受欢迎的5个主题

### 👥 热门作者（Top 5）
列举发布最多内容的5个作者

### 📈 趋势分析
分析当前小红书推荐的内容趋势，包括：
- 热门话题
- 内容偏好
- 受欢迎的内容类型

### 💎 值得关注的笔记
推荐3-5个值得深入阅读的笔记（附链接）

请确保报告结构完整，每个部分都要有实质内容。"""

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
