#!/usr/bin/env python3
"""
小红书搜索测试文件 - 完整版

功能：
1. 关键词搜索 - 搜索特定关键词的笔记
2. 用户搜索 - 搜索特定用户的笔记
3. 标签搜索 - 搜索特定标签的内容
4. 综合搜索测试 - 包含各种场景的测试用例

使用示例:
    # 运行所有测试
    python test_xhs_search.py

    # 运行特定测试
    python test_xhs_search.py --test keyword_search
    python test_xhs_search.py --test user_search

    # 指定搜索词
    python test_xhs_search.py --keyword "旅行" --test keyword_search
"""

import asyncio
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

# ==================== 路径配置 ====================
PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / "output" / "xhs_search_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==================== Cookie 读取 ====================
def read_xhs_cookie() -> Dict[str, str]:
    """从 config/cookies.txt 读取小红书Cookie（返回字典格式）"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        print("❌ Cookie文件不存在: config/cookies.txt")
        return {}

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 [xiaohongshu] 部分
    xhs_section = re.search(r'\[xiaohongshu\](.*?)\[', content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        cookies_dict = {}
        for line in section.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                cookies_dict[key.strip()] = value.strip()
        return cookies_dict

    return {}


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


# ==================== 测试结果存储 ====================
class TestResult:
    """测试结果存储类"""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.results = []
        self.start_time = None
        self.end_time = None
        self.success_count = 0
        self.failure_count = 0
        self.total_count = 0

    def start(self):
        self.start_time = datetime.now()

    def finish(self):
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        print(f"\n✅ 测试完成！耗时: {duration:.2f}秒")
        print(f"   成功: {self.success_count} | 失败: {self.failure_count} | 总计: {self.total_count}")

    def add_result(self, success: bool, message: str, data: Dict = None):
        self.total_count += 1
        if success:
            self.success_count += 1
            print(f"   ✓ {message}")
        else:
            self.failure_count += 1
            print(f"   ✗ {message}")

        self.results.append({
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    def export_to_json(self, output_file: Path):
        """导出测试结果到JSON文件"""
        report = {
            'test_name': self.test_name,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'duration': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'total_count': self.total_count,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n📁 测试结果已保存: {output_file}")


# ==================== Playwright 浏览器管理 ====================
class XHSBrowser:
    """小红书浏览器管理类"""

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

        # 设置Cookie - 使用字符串格式（参考 ai_xiaohongshu_homepage.py）
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


# ==================== 搜索功能实现 ====================
class XHSSearcher:
    """小红书搜索类"""

    def __init__(self, browser: XHSBrowser):
        self.browser = browser

    async def check_login_status(self) -> bool:
        """检查登录状态"""
        page_content = await self.browser.page.content()
        return not ('登录' in page_content and '注册' in page_content)

    async def search_by_keyword(self, keyword: str, max_notes: int = 20) -> List[Dict]:
        """通过关键词搜索

        Args:
            keyword: 搜索关键词
            max_notes: 最多获取的笔记数

        Returns:
            笔记列表
        """
        print(f"\n🔍 搜索关键词: {keyword}")

        # 先访问小红书主页确保登录状态
        try:
            await self.browser.page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️  主页加载问题: {e}")
            return []

        # 检查登录状态
        if not await self.check_login_status():
            print("⚠️  检测到未登录状态")
            return []

        # 构造搜索URL
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&type=51"

        try:
            await self.browser.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️  搜索页面加载问题: {e}")
            return []

        # 滚动加载更多内容
        try:
            # 等待页面完全加载
            await self.browser.page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass  # 忽略超时，继续执行

        # 滚动加载更多内容
        for i in range(5):
            try:
                await asyncio.sleep(1)
                await self.browser.page.evaluate('window.scrollBy(0, window.innerHeight)')
                print(f"    滚动加载 {i+1}/5")
            except Exception as e:
                print(f"⚠️  滚动失败: {e}")
                break

        await asyncio.sleep(3)

        # 提取搜索结果
        notes = await self.browser.page.evaluate('''
            () => {
                const notes = [];
                const seen = new Set();

                // 查找所有笔记卡片
                const cards = document.querySelectorAll('section, article, [class*="note"], [class*="card"], div[class*="item"]');

                cards.forEach(card => {
                    // 查找带 xsec_token 的链接
                    const link = card.querySelector('a[href*="xsec_token"]');
                    if (!link) return;

                    const url = link.href;

                    // 从 URL 中提取 xsec_token 和 xsec_source
                    let xsecToken = '';
                    let xsecSource = 'pc_search';

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

        print(f"   找到 {len(notes)} 个笔记")
        return notes[:max_notes]

    async def search_by_user(self, user_id: str, max_notes: int = 20) -> List[Dict]:
        """通过用户ID搜索用户笔记

        Args:
            user_id: 用户ID
            max_notes: 最多获取的笔记数

        Returns:
            笔记列表
        """
        print(f"\n👤 搜索用户: {user_id}")

        # 先访问小红书主页确保登录状态
        try:
            await self.browser.page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️  主页加载问题: {e}")
            return []

        # 检查登录状态
        if not await self.check_login_status():
            print("⚠️  检测到未登录状态")
            return []

        # 构造用户主页URL
        user_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"

        try:
            await self.browser.page.goto(user_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️  用户页面加载问题: {e}")
            return []

        # 滚动加载更多内容
        try:
            # 等待页面完全加载
            await self.browser.page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass  # 忽略超时，继续执行

        # 滚动加载更多内容
        for i in range(5):
            try:
                await asyncio.sleep(1)
                await self.browser.page.evaluate('window.scrollBy(0, window.innerHeight)')
                print(f"    滚动加载 {i+1}/5")
            except Exception as e:
                print(f"⚠️  滚动失败: {e}")
                break

        await asyncio.sleep(3)

        # 提取用户笔记
        notes = await self.browser.page.evaluate('''
            () => {
                const notes = [];
                const seen = new Set();

                const cards = document.querySelectorAll('section, article, [class*="note"], [class*="card"], div[class*="item"]');

                cards.forEach(card => {
                    const link = card.querySelector('a[href*="xsec_token"]');
                    if (!link) return;

                    const url = link.href;

                    let xsecToken = '';
                    let xsecSource = 'pc_user';

                    try {
                        const urlParams = new URLSearchParams(url.split('?')[1]);
                        xsecToken = urlParams.get('xsec_token') || '';
                        if (urlParams.get('xsec_source')) {
                            xsecSource = urlParams.get('xsec_source');
                        }
                    } catch (e) {}

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

                    let likes = "0";
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

        print(f"   找到 {len(notes)} 个笔记")
        return notes[:max_notes]

    async def search_by_tag(self, tag: str, max_notes: int = 20) -> List[Dict]:
        """通过标签搜索

        Args:
            tag: 标签名称
            max_notes: 最多获取的笔记数

        Returns:
            笔记列表
        """
        print(f"\n🏷️  搜索标签: {tag}")

        # 先访问小红书主页确保登录状态
        try:
            await self.browser.page.goto('https://www.xiaohongshu.com/', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️  主页加载问题: {e}")
            return []

        # 检查登录状态
        if not await self.check_login_status():
            print("⚠️  检测到未登录状态")
            return []

        # 构造标签搜索URL
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={tag}&type=51"

        try:
            await self.browser.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️  搜索页面加载问题: {e}")
            return []

        # 滚动加载更多内容
        try:
            # 等待页面完全加载
            await self.browser.page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass  # 忽略超时，继续执行

        # 滚动加载更多内容
        for i in range(5):
            try:
                await asyncio.sleep(1)
                await self.browser.page.evaluate('window.scrollBy(0, window.innerHeight)')
                print(f"    滚动加载 {i+1}/5")
            except Exception as e:
                print(f"⚠️  滚动失败: {e}")
                break

        await asyncio.sleep(3)

        # 提取搜索结果
        notes = await self.browser.page.evaluate('''
            () => {
                const notes = [];
                const seen = new Set();

                const cards = document.querySelectorAll('section, article, [class*="note"], [class*="card"], div[class*="item"]');

                cards.forEach(card => {
                    const link = card.querySelector('a[href*="xsec_token"]');
                    if (!link) return;

                    const url = link.href;

                    let xsecToken = '';
                    let xsecSource = 'pc_tag';

                    try {
                        const urlParams = new URLSearchParams(url.split('?')[1]);
                        xsecToken = urlParams.get('xsec_token') || '';
                        if (urlParams.get('xsec_source')) {
                            xsecSource = urlParams.get('xsec_source');
                        }
                    } catch (e) {}

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

                    if (title === "无标题") {
                        const linkTitle = link.getAttribute('title');
                        if (linkTitle && linkTitle.length > 3) {
                            title = linkTitle.substring(0, 100);
                        }
                    }

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

                    let likes = "0";
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

        print(f"   找到 {len(notes)} 个笔记")
        return notes[:max_notes]


# ==================== 测试用例 ====================
async def test_keyword_search(browser: XHSBrowser, keyword: str = "旅行") -> List[Dict]:
    """测试关键词搜索"""
    print(f"\n{'='*70}")
    print(f"  测试: 关键词搜索 - '{keyword}'")
    print(f"{'='*70}")

    test_result = TestResult("关键词搜索")
    test_result.start()

    searcher = XHSSearcher(browser)
    notes = await searcher.search_by_keyword(keyword, max_notes=10)

    if notes:
        test_result.add_result(True, f"成功搜索到 {len(notes)} 个笔记", {'keyword': keyword, 'count': len(notes)})

        # 显示结果
        print(f"\n📋 搜索结果:")
        for i, note in enumerate(notes[:5], 1):
            type_emoji = '🎬' if note['type'] == 'video' else '🖼️'
            print(f"  {i}. {type_emoji} {note['title']} | {note['author']} | {note['likes']}赞")
    else:
        test_result.add_result(False, "未搜索到任何笔记", {'keyword': keyword})

    test_result.finish()

    # 保存结果
    output_file = OUTPUT_DIR / f"test_keyword_search_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    test_result.export_to_json(output_file)

    return notes


async def test_user_search(browser: XHSBrowser, user_id: str = "5e7c3a8c0000000001006e32") -> List[Dict]:
    """测试用户搜索"""
    print(f"\n{'='*70}")
    print(f"  测试: 用户搜索 - '{user_id}'")
    print(f"{'='*70}")

    test_result = TestResult("用户搜索")
    test_result.start()

    searcher = XHSSearcher(browser)
    notes = await searcher.search_by_user(user_id, max_notes=10)

    if notes:
        test_result.add_result(True, f"成功搜索到 {len(notes)} 个笔记", {'user_id': user_id, 'count': len(notes)})

        # 显示结果
        print(f"\n📋 搜索结果:")
        for i, note in enumerate(notes[:5], 1):
            type_emoji = '🎬' if note['type'] == 'video' else '🖼️'
            print(f"  {i}. {type_emoji} {note['title']} | {note['author']} | {note['likes']}赞")
    else:
        test_result.add_result(False, "未搜索到任何笔记", {'user_id': user_id})

    test_result.finish()

    # 保存结果
    output_file = OUTPUT_DIR / f"test_user_search_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    test_result.export_to_json(output_file)

    return notes


async def test_tag_search(browser: XHSBrowser, tag: str = "美食") -> List[Dict]:
    """测试标签搜索"""
    print(f"\n{'='*70}")
    print(f"  测试: 标签搜索 - '{tag}'")
    print(f"{'='*70}")

    test_result = TestResult("标签搜索")
    test_result.start()

    searcher = XHSSearcher(browser)
    notes = await searcher.search_by_tag(tag, max_notes=10)

    if notes:
        test_result.add_result(True, f"成功搜索到 {len(notes)} 个笔记", {'tag': tag, 'count': len(notes)})

        # 显示结果
        print(f"\n📋 搜索结果:")
        for i, note in enumerate(notes[:5], 1):
            type_emoji = '🎬' if note['type'] == 'video' else '🖼️'
            print(f"  {i}. {type_emoji} {note['title']} | {note['author']} | {note['likes']}赞")
    else:
        test_result.add_result(False, "未搜索到任何笔记", {'tag': tag})

    test_result.finish()

    # 保存结果
    output_file = OUTPUT_DIR / f"test_tag_search_{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    test_result.export_to_json(output_file)

    return notes


async def run_comprehensive_test(browser: XHSBrowser, keyword: str = None, user_id: str = None, tag: str = None):
    """运行综合测试"""
    print(f"\n{'='*70}")
    print(f"  小红书搜索综合测试")
    print(f"{'='*70}")

    overall_result = TestResult("综合测试")
    overall_result.start()

    # 测试关键词搜索
    if keyword:
        try:
            notes = await test_keyword_search(browser, keyword)
            overall_result.add_result(len(notes) > 0, f"关键词搜索 '{keyword}'", {'count': len(notes)})
        except Exception as e:
            overall_result.add_result(False, f"关键词搜索 '{keyword}' 失败: {e}")

    # 测试用户搜索
    if user_id:
        try:
            notes = await test_user_search(browser, user_id)
            overall_result.add_result(len(notes) > 0, f"用户搜索 '{user_id}'", {'count': len(notes)})
        except Exception as e:
            overall_result.add_result(False, f"用户搜索 '{user_id}' 失败: {e}")

    # 测试标签搜索
    if tag:
        try:
            notes = await test_tag_search(browser, tag)
            overall_result.add_result(len(notes) > 0, f"标签搜索 '{tag}'", {'count': len(notes)})
        except Exception as e:
            overall_result.add_result(False, f"标签搜索 '{tag}' 失败: {e}")

    overall_result.finish()

    # 保存综合测试结果
    output_file = OUTPUT_DIR / f"test_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    overall_result.export_to_json(output_file)


# ==================== 主程序 ====================
async def main():
    parser = argparse.ArgumentParser(description='小红书搜索测试')

    parser.add_argument('--test', type=str, choices=['keyword', 'user', 'tag', 'all'],
                       default='all', help='测试类型: keyword=关键词搜索, user=用户搜索, tag=标签搜索, all=全部测试')
    parser.add_argument('--keyword', type=str, default='旅行', help='搜索关键词（默认: 旅行）')
    parser.add_argument('--user-id', type=str, default='5e7c3a8c0000000001006e32', help='用户ID')
    parser.add_argument('--tag', type=str, default='美食', help='标签名称（默认: 美食）')
    parser.add_argument('--headless', action='store_true', help='使用无头模式浏览器')
    parser.add_argument('--max-notes', type=int, default=20, help='最多获取的笔记数（默认: 20）')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  小红书搜索测试")
    print(f"{'='*70}")
    print(f"\n📊 配置:")
    print(f"  • 测试类型: {args.test}")
    print(f"  • 关键词: {args.keyword}")
    print(f"  • 用户ID: {args.user_id}")
    print(f"  • 标签: {args.tag}")
    print(f"  • 最多笔记: {args.max_notes}")
    print(f"  • 无头模式: {args.headless}")

    # 检查Cookie
    cookies_dict = read_xhs_cookie()
    if not cookies_dict:
        print("\n⚠️  未找到Cookie，将使用无Cookie模式（需要手动登录）")
    else:
        print(f"\n✅ Cookie已读取")
        print(f"   a1: {cookies_dict.get('a1', '')[:20]}...")

    # 启动浏览器
    browser = XHSBrowser()
    try:
        await browser.start(headless=args.headless)

        # 根据测试类型执行测试
        if args.test == 'keyword':
            await test_keyword_search(browser, args.keyword)
        elif args.test == 'user':
            await test_user_search(browser, args.user_id)
        elif args.test == 'tag':
            await test_tag_search(browser, args.tag)
        elif args.test == 'all':
            await run_comprehensive_test(browser, args.keyword, args.user_id, args.tag)
        else:
            print(f"⚠️  未知测试类型: {args.test}")

    finally:
        await browser.close()

    print(f"\n{'='*70}")
    print(f"  ✅ 测试完成！")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
