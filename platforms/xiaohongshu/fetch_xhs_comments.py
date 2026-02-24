# -*- coding: utf-8 -*-
"""
小红书笔记评论爬取工具 (HTML 爬取版)

功能：
1. 使用 Cookie 直接访问笔记页面
2. 从 HTML 中提取评论数据
3. 生成 JSON 层级文件
4. 包含回复关系：谁回复了谁，谁发言了

使用方法:
    python fetch_xhs_comments.py "笔记链接"

示例:
    python fetch_xhs_comments.py "https://www.xiaohongshu.com/explore/694f9e5300000001e013674"
"""

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright


# ==================== 配置 ====================
OUTPUT_DIR = Path("xhs_comments_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==================== Cookie 管理 ====================

def load_cookies():
    """从 config/cookies.txt 读取 Cookie"""
    cookie_file = Path("config/cookies.txt")

    if not cookie_file.exists():
        print("❌ Cookie文件不存在: config/cookies.txt")
        return None

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

    return None


def extract_note_id(url):
    """从 URL 中提取笔记 ID"""
    if '/explore/' in url:
        match = re.search(r'/explore/([a-f0-9]{24})', url)
        if match:
            return match.group(1)
    match = re.search(r'([a-f0-9]{24})', url, re.IGNORECASE)
    if match:
        return match.group(0)
    return None


def parse_cookies(cookie_str):
    """将 Cookie 字符串转换为 Playwright 格式"""
    cookies = []
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies.append({
                'name': key.strip(),
                'value': value.strip(),
                'domain': '.xiaohongshu.com',
                'path': '/'
            })
    return cookies


# ==================== 评论提取 ====================

class XHSCommentExtractor:
    """小红书评论提取器"""

    def __init__(self, note_id):
        self.note_id = note_id
        self.all_comments = {}  # {comment_id: comment_data}
        self.comment_tree = []  # 树形结构

    async def extract_comments_from_html(self, page):
        """从 HTML 页面提取评论"""
        print("\n  📝 正在提取评论数据...")

        # 使用 JavaScript 在页面中执行，提取评论数据
        comments_data = await page.evaluate('''
            () => {
                const comments = [];
                const seen = new Set();

                // 查找所有评论容器
                const commentItems = document.querySelectorAll('[class*="comment"], [class*="Comment"]');

                for (const item of commentItems) {
                    // 跳过没有内容的
                    const contentEl = item.querySelector('[class*="content"], [class*="text"]');
                    if (!contentEl || !contentEl.textContent.trim()) continue;

                    // 提取评论 ID
                    let commentId = item.getAttribute('data-id') ||
                                     item.getAttribute('data-comment-id') ||
                                     item.querySelector('[class*="id"]')?.textContent ||
                                     Math.random().toString(36).substr(2, 9);

                    if (seen.has(commentId)) continue;
                    seen.add(commentId);

                    // 提取内容
                    const content = contentEl.textContent.trim();

                    // 提取点赞数
                    let likes = 0;
                    const likeEl = item.querySelector('[class*="like"], [class*="count"], [class*="num"]');
                    if (likeEl) {
                        const text = likeEl.textContent.trim();
                        const num = parseInt(text.replace(/\\D/g, ''));
                        if (!isNaN(num)) likes = num;
                    }

                    // 提取作者信息
                    const authorEl = item.querySelector('[class*="author"], [class*="user"], a[href*="/user/profile/"]');
                    const author = {
                        nickname: authorEl?.textContent?.trim() || '未知用户',
                        avatar: authorEl?.querySelector('img')?.src || ''
                    };

                    // 提取时间
                    let createTime = '';
                    const timeEl = item.querySelector('[class*="time"], time, [datetime]');
                    if (timeEl) {
                        createTime = timeEl.textContent.trim() || timeEl.getAttribute('datetime') || '';
                    }

                    // 检测是否是回复（通过样式或结构判断）
                    let isReply = false;
                    let parentId = null;

                    const parentComment = item.closest('[class*="reply"], [class*="sub"]');
                    if (parentComment) {
                        isReply = true;
                        // 尝试找到父评论ID
                        const parentContainer = parentComment.closest('[class*="comment"]');
                        if (parentContainer) {
                            parentId = parentContainer.getAttribute('data-id') ||
                                         parentContainer.getAttribute('data-comment-id');
                        }
                    }

                    comments.push({
                        id: commentId,
                        parent_id: parentId,
                        depth: isReply ? 1 : 0,
                        content: content,
                        like_count: likes,
                        author: author,
                        create_time: createTime,
                        is_reply: isReply
                    });
                }

                return comments;
            }
        ''')

        if not comments_data:
            print("  ⚠️  未找到评论数据")
        else:
            print(f"  ✅ 提取到 {len(comments_data)} 条评论")

        return comments_data

    def build_comment_tree(self, comments):
        """构建评论树"""
        # 第一层：顶级评论
        top_level = [c for c in comments if c['depth'] == 0]

        # 构建树形结构
        tree = []
        for comment in top_level:
            node = {
                'comment': comment,
                'replies': self._build_replies(comment['id'], comments)
            }
            tree.append(node)

        return tree

    def _build_replies(self, parent_id, comments):
        """递归构建子评论"""
        replies = [c for c in comments if c.get('parent_id') == parent_id]

        result = []
        for reply in replies:
            node = {
                'comment': reply,
                'replies': self._build_replies(reply['id'], comments)
            }
            result.append(node)

        return result

    def save_json(self, tree, comments_count):
        """保存为 JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"xhs_comments_{self.note_id}_{timestamp}.json"

        result = {
            'note_id': self.note_id,
            'total_comments': comments_count,
            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'comments': tree
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"💾 JSON 已保存: {output_file}")
        return output_file

    def generate_summary(self, comments):
        """生成统计摘要"""
        if not comments:
            return {}

        total = len(comments)
        top_level = sum(1 for c in comments if c['depth'] == 0)
        replies = total - top_level

        # 作者统计
        authors = {}
        for comment in comments:
            nickname = comment['author']['nickname']
            if nickname not in authors:
                authors[nickname] = {
                    'count': 0,
                    'likes': 0,
                    'comments': []
                }
            authors[nickname]['count'] += 1
            authors[nickname]['likes'] += comment['like_count']
            authors[nickname]['comments'].append(comment['id'])

        # 活跃作者 Top 5
        sorted_authors = sorted(
            authors.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:5]

        # 回复关系统计
        reply_relations = []
        for comment in comments:
            if comment['depth'] == 1 and comment['parent_id']:
                # 找到父评论
                parent = next((c for c in comments if c['id'] == comment['parent_id']), None)
                if parent:
                    reply_relations.append({
                        'from': comment['author']['nickname'],
                        'to': parent['author']['nickname'],
                        'content': comment['content'][:50],
                        'time': comment['create_time']
                    })

        summary = {
            'total_comments': total,
            'top_level_comments': top_level,
            'reply_comments': replies,
            'unique_authors': len(authors),
            'top_authors': [
                {
                    'nickname': name,
                    'comment_count': data['count'],
                    'total_likes': data['likes']
                }
                for name, data in sorted_authors
            ],
            'sample_reply_relations': reply_relations[:10] if reply_relations else []
        }

        return summary


# ==================== 主程序 ====================

async def main_async(url: str = None):
    """异步主程序"""

    print(f"\n{'='*80}")
    print(f"小红书笔记评论爬取工具 (HTML 版)")
    print(f"{'='*80}")

    # 获取 Cookie
    print("\n[步骤 1] 加载 Cookie")
    cookie_str = load_cookies()
    if not cookie_str:
        print("❌ 未找到有效 Cookie")
        return

    print("✅ Cookie 已加载")

    # 提取笔记 ID
    print("\n[步骤 2] 解析笔记链接")
    if not url:
        print("请输入小红书笔记链接:")
        url = input("笔记链接: ").strip()

    note_id = extract_note_id(url)
    if not note_id:
        print(f"❌ 无法从链接提取笔记 ID: {url}")
        return

    print(f"✅ 笔记 ID: {note_id}")

    # 构建页面 URL（保留完整 URL，包括 xsec_token）
    # 如果原链接包含 xsec_token，则使用原链接
    if '?xsec_token=' in url:
        page_url = url
    else:
        page_url = f"https://www.xiaohongshu.com/explore/{note_id}"

    print(f"📝 页面 URL: {page_url}")

    # 爬取评论
    print("\n[步骤 3] 访问页面并提取评论")
    print("-" * 80)

    extractor = XHSCommentExtractor(note_id)

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)

        # 解析 Cookie
        cookies = parse_cookies(cookie_str)

        # 创建上下文
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        # 添加 Cookie
        if cookies:
            await context.add_cookies(cookies)
            print(f"✅ 已设置 {len(cookies)} 个 Cookie")

        page = await context.new_page()

        # 访问页面
        print(f"\n📡 正在访问笔记页面...")
        print(f"   {page_url}")

        try:
            await page.goto(page_url, wait_until='networkidle', timeout=60000)
            print("✅ 页面加载成功")

            # 滚动加载评论
            print("\n  🔄 滚动加载评论...")
            await asyncio.sleep(2)  # 等待初始加载

            # 滚动到底部多次，确保评论加载
            for i in range(3):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await asyncio.sleep(1.5)

            print("  ✅ 滚动完成")

            # 提取评论
            comments = await extractor.extract_comments_from_html(page)

            if not comments:
                print("\n❌ 未提取到任何评论")
                await browser.close()
                return

            # 构建树形结构
            print("\n  🌳 构建评论树...")
            tree = extractor.build_comment_tree(comments)
            print("  ✅ 评论树构建完成")

            # 保存 JSON
            print("\n[步骤 4] 保存结果")
            json_file = extractor.save_json(tree, len(comments))

            # 生成摘要
            print("\n[步骤 5] 生成统计摘要")
            summary = extractor.generate_summary(comments)

            print(f"\n{'-'*80}")
            print(f"统计摘要:")
            print(f"{'-'*80}")
            print(f"  总评论数: {summary['total_comments']}")
            print(f"  顶级评论: {summary['top_level_comments']}")
            print(f"  回复评论: {summary['reply_comments']}")
            print(f"  独一作者: {summary['unique_authors']}")
            print(f"\n  活跃作者 Top 5:")
            for i, author in enumerate(summary['top_authors'], 1):
                print(f"    {i}. {author['nickname']} - {author['comment_count']} 条评论，{author['total_likes']} 嵌")

            if summary['sample_reply_relations']:
                print(f"\n  回复关系示例:")
                for i, reply in enumerate(summary['sample_reply_relations'][:5], 1):
                    print(f"    {i}. {reply['from']} 回复 {reply['to']}")
                    print(f"       \"{reply['content']}\"")
                    print(f"       时间: {reply['create_time']}")

            # 保存摘要
            summary_file = json_file.with_suffix('.summary.json')
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"\n💾 摘要已保存: {summary_file}")

            await browser.close()

        except Exception as e:
            print(f"\n❌ 爬取失败: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return

    print(f"\n{'='*80}")
    print(f"✅ 完成！")
    print(f"{'='*80}\n")


def main(url: str = None):
    """同步入口"""
    asyncio.run(main_async(url))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="小红书笔记评论爬取工具 (HTML 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('url', nargs='?', help='小红书笔记链接')

    args = parser.parse_args()

    try:
        main(args.url)
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
