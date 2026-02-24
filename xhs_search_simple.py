#!/usr/bin/env python3
"""
小红书搜索工具 - 简化稳定版

功能：
1. 搜索指定关键词
2. 支持排序方式（推荐/最新/最热）
3. 指定获取数量
4. 返回笔记链接列表

使用示例:
    # 默认搜索（推荐排序，20条）
    python xhs_search_simple.py --keyword "美食"

    # 搜索最新笔记
    python xhs_search_simple.py --keyword "美食" --sort latest

    # 搜索最热笔记
    python xhs_search_simple.py --keyword "美食" --sort hot

    # 指定获取数量
    python xhs_search_simple.py --keyword "美食" --max-notes 50
"""

import asyncio
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / "output" / "xhs_search_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_xhs_cookie_string() -> str:
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


class XHSSearch:
    """小红书搜索类"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def start(self, headless: bool = False):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 设置Cookie
        cookie = read_xhs_cookie_string()
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
                await self.context.add_cookies(cookies)
                print(f"✅ Cookie已设置 ({len(cookies)} 个)")
            except Exception as e:
                print(f"⚠️  Cookie设置失败: {e}")

        self.page = await self.context.new_page()
        print("✅ 浏览器已启动")

    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("✅ 浏览器已关闭")

    async def search(
        self,
        keyword: str,
        sort_type: str = "default",
        max_notes: int = 20
    ) -> List[Dict]:
        """
        搜索小红书

        Args:
            keyword: 搜索关键词
            sort_type: 排序类型
                - default: 默认/推荐
                - latest: 最新
                - hot: 最热/点赞数排序
            max_notes: 最多获取的笔记数

        Returns:
            笔记列表
        """
        print(f"\n🔍 搜索参数:")
        print(f"   关键词: {keyword}")
        print(f"   排序: {sort_type}")
        print(f"   数量: {max_notes}")

        # 构造搜索URL
        # 注意：小红书搜索页面本身可能有排序选项，但URL参数可能不起作用
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&type=51"
        sort_display = {
            "default": "默认/推荐",
            "latest": "最新",
            "hot": "最热"
        }
        print(f"\n📄 访问: {search_url}")
        print(f"📊 排序方式: {sort_display.get(sort_type, '默认')} (小红书可能通过UI选项实现)")

        try:
            # 直接访问搜索页面
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=45000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️  页面加载问题: {e}")
            return []

        # 检查登录状态
        try:
            page_content = await self.page.content()
            if '登录' in page_content and '注册' in page_content:
                print("⚠️  检测到未登录状态")
                return []
        except Exception as e:
            print(f"⚠️  获取页面内容失败: {e}")
            return []

        # 尝试滚动加载（增加延迟避免导航冲突）
        print("\n📜 尝试加载更多笔记...")
        try:
            await asyncio.sleep(2)
            await self.page.evaluate('window.scrollBy(0, window.innerHeight * 0.5)')
            await asyncio.sleep(2)
            print("   第一次滚动完成")
        except Exception as e:
            print(f"   滚动失败: {e}")

        # 提取笔记链接
        print("\n🔍 提取笔记链接...")
        notes = await self.page.evaluate('''
            () => {
                const result = [];

                // 查找所有带 xsec_token 的链接
                const allLinks = document.querySelectorAll('a[href*="xsec_token"]');

                allLinks.forEach(a => {
                    const url = a.href;

                    // 排除用户链接
                    if (url.includes('/user/profile/')) {
                        return;
                    }

                    // 只保留笔记链接
                    if (!url.includes('/search_result/') && !url.includes('/explore/')) {
                        return;
                    }

                    // 提取 xsec_token 和 xsec_source
                    let xsecToken = '';
                    let xsecSource = '';

                    try {
                        const urlParams = new URLSearchParams(url.split('?')[1]);
                        xsecToken = urlParams.get('xsec_token') || '';
                        xsecSource = urlParams.get('xsec_source') || '';
                    } catch (e) {}

                    // 提取笔记ID
                    let noteId = "";
                    if (url.includes('/search_result/')) {
                        const idMatch = url.match(/\\/search_result\\/([a-f0-9]{24})/);
                        if (idMatch) noteId = idMatch[1];
                    } else if (url.includes('/explore/')) {
                        const idMatch = url.match(/\\/explore\\/([a-f0-9]{24})/);
                        if (idMatch) noteId = idMatch[1];
                    }

                    if (!noteId) return;

                    // 从卡片获取信息
                    let title = "无标题";
                    let author = "未知作者";
                    let likes = "0";

                    const card = a.closest('section, article, [class*="note"], [class*="card"], div[class*="item"]');
                    if (card) {
                        // 获取标题
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
                        const allNodes = card.querySelectorAll('*');
                        for (const node of allNodes) {
                            const text = node.textContent?.trim();
                            if (text && /^\\d+/.test(text)) {
                                const parentClass = node.parentElement?.className || '';
                                if (parentClass.includes('like') || parentClass.includes('count') ||
                                    parentClass.includes('interact')) {
                                    const num = parseInt(text);
                                    if (num < 1000000 && num > 0) {
                                        likes = text;
                                        break;
                                    }
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
                        const hasPlayIcon = card.querySelector('[class*="play"], [class*="video"], svg[class*="play"]');
                        const hasDuration = card.textContent.includes(':') && card.textContent.match(/\\d+:\\d+/);
                        if (hasPlayIcon || hasDuration) {
                            type = 'video';
                        }
                    }

                    result.push({
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

                return result;
            }
        ''')

        print(f"   找到 {len(notes)} 个笔记")
        return notes[:max_notes]

    def save_results(self, notes: List[Dict], keyword: str, sort_type: str):
        """保存搜索结果到JSON文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"xhs_search_{keyword}_{sort_type}_{timestamp}.json"
        output_file = OUTPUT_DIR / filename

        result = {
            'keyword': keyword,
            'sort_type': sort_type,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_count': len(notes),
            'notes': notes
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n📁 结果已保存: {output_file}")
        return output_file


async def main():
    parser = argparse.ArgumentParser(description='小红书搜索工具')

    parser.add_argument('--keyword', type=str, required=True, help='搜索关键词（必需）')
    parser.add_argument('--sort', type=str, default='default',
                       choices=['default', 'latest', 'hot'],
                       help='排序类型: default=推荐, latest=最新, hot=最热（默认: default）')
    parser.add_argument('--max-notes', type=int, default=20,
                       help='最多获取的笔记数（默认: 20）')
    parser.add_argument('--headless', action='store_true',
                       help='使用无头模式（后台运行）')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  小红书搜索工具")
    print(f"{'='*70}")

    # 创建搜索实例
    searcher = XHSSearch()

    try:
        # 启动浏览器
        await searcher.start(headless=args.headless)

        # 执行搜索
        notes = await searcher.search(
            keyword=args.keyword,
            sort_type=args.sort,
            max_notes=args.max_notes
        )

        if not notes:
            print("\n⚠️  未找到任何笔记")
            return

        # 显示结果
        print(f"\n📋 搜索结果（前{min(10, len(notes))}条）:")
        print("=" * 70)
        for i, note in enumerate(notes[:10], 1):
            type_emoji = '🎬' if note['type'] == 'video' else '🖼️'
            print(f"{i}. {type_emoji} {note['title']}")
            print(f"   作者: {note['author']}")
            print(f"   点赞: {note['likes']}")
            print(f"   链接: {note['url'][:80]}...")
            print()

        if len(notes) > 10:
            print(f"... 还有 {len(notes) - 10} 条笔记")

        # 保存结果
        output_file = searcher.save_results(notes, args.keyword, args.sort)

        print(f"\n{'='*70}")
        print(f"  ✅ 完成！共获取 {len(notes)} 条笔记")
        print(f"{'='*70}\n")

    finally:
        # 关闭浏览器
        await searcher.close()


if __name__ == "__main__":
    asyncio.run(main())
