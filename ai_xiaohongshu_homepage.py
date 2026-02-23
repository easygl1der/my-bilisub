#!/usr/bin/env python3
"""
AI自动刷小红书推荐并总结

一键完成：
1. 刷新小红书推荐页（自定义次数）
2. 采集推荐内容（视频/图文、作者信息）
3. 导出CSV
4. AI生成分析报告

使用示例:
    # 默认配置（刷新3次，最多50个笔记）
    python ai_xiaohongshu_homepage.py

    # 仅采集，生成CSV
    python ai_xiaohongshu_homepage.py --mode scrape

    # 采集+AI分析
    python ai_xiaohongshu_homepage.py --mode full

    # 自定义刷新次数和笔记数
    python ai_xiaohongshu_homepage.py --refresh-count 5 --max-notes 100 --mode full
"""

import argparse
import asyncio
import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright
import httpx
from bs4 import BeautifulSoup
import time

# 延迟导入 Gemini API
_gemini_available = False
try:
    from google import genai
    _gemini_available = True
except ImportError:
    try:
        import google.generativeai as genai
        _gemini_available = True
    except ImportError:
        pass


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
        print("💡 请先登录小红书并导出Cookie")
        return ""

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 尝试多种格式
    cookie = ""

    # 方法1: 查找 xiaohongshu_full= 格式
    match = re.search(r'xiaohongshu_full=([^\n]+)', content)
    if match:
        cookie = match.group(1)
        print("✅ 使用 xiaohongshu_full Cookie")
        return cookie

    # 方法2: 查找 [xiaohongshu] 部分
    xhs_section = re.search(r'\[xiaohongshu\](.*?)\[', content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        # 提取所有 key=value 对
        cookies = []
        for line in section.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                cookies.append(f"{key.strip()}={value.strip()}")
        cookie = '; '.join(cookies)
        if cookie:
            print("✅ 使用 [xiaohongshu] 部分 Cookie")
            return cookie

    # 方法3: 直接查找关键Cookie
    a1_match = re.search(r'a1=([^\s\n;]+)', content)
    web_session_match = re.search(r'web_session=([^\s\n;]+)', content)
    webid_match = re.search(r'webId=([^\s\n;]+)', content)

    if a1_match and web_session_match and webid_match:
        cookie = f"a1={a1_match.group(1)}; web_session={web_session_match.group(1)}; webId={webid_match.group(1)}"
        print("✅ 手动提取关键Cookie")
        return cookie

    print("⚠️  Cookie文件中未找到有效的小红书Cookie")
    return ""


# ==================== Playwright 采集 ====================
async def scrape_xiaohongshu_homepage(
    refresh_count: int = 3,
    max_notes: int = 50,
    cookie: str = ""
) -> List[Dict]:
    """
    使用Playwright爬取小红书推荐页

    Args:
        refresh_count: 刷新次数
        max_notes: 最多采集笔记数
        cookie: 小红书Cookie

    Returns:
        笔记列表
    """
    notes_collected = []
    seen_urls = set()  # 去重

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)  # 非无头模式，可以看到登录
        context = await browser.new_context()

        # 设置Cookie
        if cookie:
            # 解析Cookie字符串并添加到context
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

        page = await context.new_page()

        print(f"\n📡 访问小红书首页...")
        await page.goto('https://www.xiaohongshu.com/', wait_until='networkidle')
        await asyncio.sleep(3)  # 等待页面加载

        # 检查是否需要登录
        try:
            login_btn = await page.query_selector('button:has-text("登录")')
            if login_btn:
                print("\n⚠️  检测到未登录状态")
                print("💡 请在浏览器中手动登录")
                print("⏳ 等待30秒...")
                await asyncio.sleep(30)
        except:
            pass

        print(f"\n🔄 开始采集推荐内容（刷新{refresh_count}次）...")

        for i in range(refresh_count):
            print(f"\n  刷新 {i+1}/{refresh_count}")

            # 滚动页面加载更多内容
            for scroll in range(5):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1)

            # 获取页面内容
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # 查找笔记元素
            # 小红书的笔记通常在特定的div中
            note_items = soup.find_all('section')  # 小红书常用的标签

            for item in note_items:
                try:
                    # 提取笔记ID和链接
                    link_elem = item.find('a', href=re.compile(r'/explore/'))
                    if not link_elem:
                        continue

                    note_url = link_elem.get('href', '')
                    if not note_url:
                        continue

                    # 补全URL
                    if note_url.startswith('//'):
                        note_url = 'https:' + note_url
                    elif note_url.startswith('/'):
                        note_url = 'https://www.xiaohongshu.com' + note_url

                    # 提取笔记ID
                    note_id_match = re.search(r'/explore/([a-f0-9]+)', note_url)
                    if not note_id_match:
                        continue
                    note_id = note_id_match.group(1)

                    # 去重
                    if note_id in seen_urls:
                        continue
                    seen_urls.add(note_id)

                    # 提取标题/描述
                    title_elem = link_elem.find('span', class_=re.compile(r'title'))
                    title = title_elem.get_text(strip=True) if title_elem else "无标题"

                    # 提取作者信息
                    author_elem = item.find('span', class_=re.compile(r'user.*name|nickname'))
                    author = author_elem.get_text(strip=True) if author_elem else "未知作者"

                    # 提取点赞数
                    like_elem = item.find('span', class_=re.compile(r'like|count'))
                    likes = like_elem.get_text(strip=True) if like_elem else "0"

                    # 判断类型（视频/图文）
                    video_elem = item.find('video')
                    note_type = 'video' if video_elem else 'image'

                    note_data = {
                        '序号': len(notes_collected) + 1,
                        '标题': title,
                        '链接': note_url,
                        '笔记ID': note_id,
                        '作者': author,
                        '点赞数': likes,
                        '类型': note_type,
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    notes_collected.append(note_data)
                    print(f"    ✓ [{len(notes_collected)}] {note_type} - {title[:30]}...")

                    # 检查是否达到上限
                    if len(notes_collected) >= max_notes:
                        break

                except Exception as e:
                    # 单个笔记解析失败不影响整体
                    continue

            # 刷新页面
            if i < refresh_count - 1:
                await page.reload(wait_until='networkidle')
                await asyncio.sleep(2)

        await browser.close()

    print(f"\n✅ 采集完成！共获取 {len(notes_collected)} 个笔记")
    return notes_collected


# ==================== CSV导出 ====================
def export_to_csv(notes: List[Dict], output_path: Path):
    """导出笔记到CSV"""

    csv_columns = [
        '序号',
        '标题',
        '链接',
        '笔记ID',
        '作者',
        '点赞数',
        '类型',
        '采集时间'
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(notes)

    print(f"📁 CSV已保存: {output_path}")


# ==================== AI分析 ====================
def generate_ai_summary(notes: List[Dict], model: str = 'flash-lite') -> Optional[str]:
    """使用Gemini生成AI摘要"""

    if not _gemini_available:
        print("⚠️  Gemini API未安装，跳过AI分析")
        return None

    # 配置API
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("⚠️  未设置GEMINI_API_KEY环境变量，跳过AI分析")
        return None

    genai.configure(api_key=api_key)
    model_obj = genai.GenerativeModel(model)

    # 准备输入数据
    notes_text = "\n\n".join([
        f"{i+1}. {note['标题']}\n"
        f"   作者: {note['作者']}\n"
        f"   类型: {note['类型']}\n"
        f"   点赞: {note['点赞数']}\n"
        f"   链接: {note['链接']}"
        for i, note in enumerate(notes[:20])  # 最多分析20个
    ])

    prompt = f"""你是一个专业的社交媒体内容分析师。请分析以下小红书推荐内容，生成一份趋势报告。

小红书推荐内容：
{notes_text}

请生成以下格式的报告：

## 📊 小红书推荐趋势分析

### 🎯 内容概览
- 采集笔记数：{len(notes)}篇
- 视频占比：XX%
- 图文占比：XX%
- 平均点赞数：XX

### 🔥 热门主题（Top 5）
提取最受欢迎的5个主题/话题

### 👥 热门作者（Top 5）
列举发布最多内容的5个作者

### 📈 趋势分析
分析当前小红书推荐的内容趋势，包括：
- 热门话题
- 内容偏好
- 受欢迎的内容类型

### 💎 值得关注的笔记
推荐3-5个值得深入阅读的笔记（附链接）

### 📝 内容质量评估
- 内容多样性评分：1-5星
- 互动热度：高/中/低
- 推荐度：1-5星

请确保报告结构完整，每个部分都要有实质内容。"""

    try:
        print("\n🤖 正在使用AI分析...")
        response = model_obj.generate_content(prompt)

        if response.text:
            print("✅ AI分析完成！")
            return response.text
        else:
            print("❌ AI分析失败：无响应")
            return None

    except Exception as e:
        print(f"❌ AI分析出错: {e}")
        return None


# ==================== 主程序 ====================
async def main():
    parser = argparse.ArgumentParser(description='AI自动刷小红书推荐并总结')

    parser.add_argument('--refresh-count', type=int, default=3,
                       help='刷新次数（默认: 3）')
    parser.add_argument('--max-notes', type=int, default=50,
                       help='最多采集笔记数（默认: 50）')
    parser.add_argument('--mode', type=str, default='full',
                       choices=['scrape', 'full'],
                       help='模式: scrape=仅采集, full=采集+AI分析')
    parser.add_argument('--model', type=str, default='flash-lite',
                       help='Gemini模型（默认: flash-lite）')

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
        print("\n❌ 未找到有效的小红书Cookie")
        print("💡 请先在浏览器中登录小红书，然后导出Cookie到 config/cookies.txt")
        return

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
        summary = generate_ai_summary(notes, args.model)
        if summary:
            # 保存摘要
            summary_path = OUTPUT_DIR / f"xiaohongshu_homepage_{date_str}_AI总结.md"
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"📁 AI总结已保存: {summary_path}")

    print(f"\n{'='*70}")
    print(f"  ✅ 完成！")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
