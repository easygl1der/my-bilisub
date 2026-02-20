# -*- coding: utf-8 -*-
"""
小红书笔记评论爬取工具 (使用 MediaCrawler)
基于 MediaCrawler 的完整功能，支持签名验证

使用方法:
    python fetch_xhs_comments.py

功能:
    1. 爬取指定笔记的所有评论
    2. 保存为 CSV 格式
    3. 支持使用已有 Cookie 或扫码登录
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============================================================================
# 配置区域 - 在这里修改设置
# ============================================================================

ENABLE_COMMENTS = True   # 启用评论爬取
MAX_COMMENTS_COUNT = 50  # 最大评论数量
HEADLESS = True          # 无头模式（有 cookie 时）
SAVE_LOGIN_STATE = True  # 保存登录状态

# 输出目录
OUTPUT_DIR = "xhs_comments_output"


# ============================================================================
# Cookie 加载 - 使用统一 Cookie 管理器
# ============================================================================

def load_cookies_from_file():
    """从 config/cookies.txt 加载 cookies（统一管理）"""
    try:
        from cookie_manager import get_cookie, check_cookie

        # 检查 cookie 是否配置
        if not check_cookie('xiaohongshu'):
            return None

        # 获取 cookie
        cookie_str = get_cookie('xiaohongshu', 'string')

        if cookie_str:
            print(f"  [Cookie] ✅ 已从 config/cookies.txt 加载小红书 Cookie")
            return cookie_str
        else:
            return None

    except Exception as e:
        print(f"  [Cookie] 读取失败: {e}")
        return None


# ============================================================================
# 配置 MediaCrawler
# ============================================================================

def setup_mediacrawler_config(note_url: str):
    """配置 MediaCrawler"""
    try:
        # 导入配置
        sys.path.insert(0, str(Path(__file__).parent / "MediaCrawler"))
        import config

        # 设置平台和类型
        config.PLATFORM = "xhs"
        config.CRAWLER_TYPE = "detail"

        # 设置目标笔记
        config.XHS_SPECIFIED_NOTE_URL_LIST = [note_url]

        # 评论配置
        config.ENABLE_GET_COMMENTS = ENABLE_COMMENTS
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = MAX_COMMENTS_COUNT
        config.SAVE_LOGIN_STATE = SAVE_LOGIN_STATE
        config.SAVE_DATA_OPTION = "json"

        # 尝试加载 cookies
        cookie_str = load_cookies_from_file()

        if cookie_str:
            config.COOKIES = cookie_str
            config.LOGIN_TYPE = "cookie"
            config.HEADLESS = HEADLESS
            print(f"  [配置] 登录方式: Cookie (Headless={HEADLESS})")
        else:
            config.LOGIN_TYPE = "qrcode"
            config.HEADLESS = False
            print(f"  [配置] 登录方式: 扫码登录")

        print(f"  [配置] 笔记链接: {note_url[:80]}...")
        print(f"  [配置] 最大评论数: {MAX_COMMENTS_COUNT}")

        return True
    except Exception as e:
        print(f"  [配置] 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 运行爬虫
# ============================================================================

async def run_crawler():
    """运行爬虫"""
    try:
        sys.path.insert(0, str(Path(__file__).parent / "MediaCrawler"))
        from main import main as crawler_main
        await crawler_main()
        return True
    except Exception as e:
        print(f"  [爬虫] 运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# 查找并读取爬取的评论数据
# ============================================================================

def find_latest_comments():
    """查找最新的评论文件"""
    possible_dirs = [
        Path("MediaCrawler/data/xhs/json"),
        Path("MediaCrawler/data/xhs"),
    ]

    # 查找包含评论的 JSON 文件
    for data_dir in possible_dirs:
        if not data_dir.exists():
            continue

        for json_file in data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 检查是否包含评论数据
                has_comments = False
                if isinstance(data, list):
                    for item in data:
                        if 'comments' in item or 'comment_list' in item:
                            has_comments = True
                            break

                if has_comments:
                    return str(json_file), data
            except:
                continue

    return None, None


def extract_comments_from_data(data: list) -> list:
    """从数据中提取评论"""
    comments = []

    for item in data:
        # 尝试多种评论字段
        comments_list = (
            item.get('comments', []) or
            item.get('comment_list', []) or
            item.get('note_comments', [])
        )

        for comment in comments_list:
            if not isinstance(comment, dict):
                continue

            # 解析评论字段
            parsed = {
                'comment_id': comment.get('id', comment.get('comment_id', '')),
                'content': (
                    comment.get('content', '') or
                    comment.get('text', '') or
                    comment.get('note_comment', '') or
                    comment.get('comment_text', '')
                ),
                'likes': (
                    comment.get('like_count', 0) or
                    comment.get('likes', 0) or
                    comment.get('liked_count', 0) or 0
                ),
                'author': (
                    comment.get('nickname', '') or
                    comment.get('user_name', '') or
                    comment.get('author', '') or '[未知]'
                ),
                'ip_location': comment.get('ip_location', ''),
                'create_time': comment.get('create_time', comment.get('ctime', '')),
                'platform': 'xiaohongshu'
            }

            if parsed['content']:
                comments.append(parsed)

    return comments


def save_comments_csv(comments: list, note_id: str) -> str:
    """保存评论到 CSV"""
    if not comments:
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = os.path.join(OUTPUT_DIR, f"xhs_comments_{note_id}_{timestamp}.csv")

    import csv
    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['comment_id', 'author', 'content', 'likes', 'ip_location', 'create_time', 'platform']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comments)

    return csv_file


# ============================================================================
# 主程序
# ============================================================================

async def main_async(note_url: str = None, count: int = None):
    """异步主程序"""
    global MAX_COMMENTS_COUNT

    print("\n" + "="*70)
    print("小红书笔记评论爬取工具 (MediaCrawler版)")
    print("="*70)

    # 获取笔记链接
    if not note_url:
        print("\n请输入小红书笔记链接:")
        print("示例: https://www.xiaohongshu.com/explore/694f9e53000000001e013674")
        note_url = input("\n笔记链接: ").strip()

    if not note_url:
        print("❌ 链接不能为空")
        return

    # 更新配置
    if count:
        MAX_COMMENTS_COUNT = count

    print(f"\n[步骤 1] 配置 MediaCrawler")
    print("-" * 50)

    if not setup_mediacrawler_config(note_url):
        print("\n❌ 配置失败")
        return

    print(f"\n[步骤 2] 运行爬虫")
    print("-" * 50)
    print("  提示: 首次运行需要扫码登录，登录状态会自动保存")

    success = await run_crawler()

    if not success:
        print("\n❌ 爬虫运行失败")

    print(f"\n[步骤 3] 提取评论数据")
    print("-" * 50)

    json_file, data = find_latest_comments()

    if not json_file:
        print("  ⚠️  未找到评论数据文件")
        print("  💡 可能的原因:")
        print("     1. 登录失败，请检查 Cookie 是否有效")
        print("     2. 笔记没有评论")
        print("     3. 触发了风控")
        return

    print(f"  ✅ 找到数据文件: {Path(json_file).name}")

    # 提取评论
    comments = extract_comments_from_data(data)

    if not comments:
        print("  ⚠️  数据中未找到评论")
        return

    print(f"  ✅ 提取到 {len(comments)} 条评论")

    # 保存到 CSV
    note_id = note_url.split('/')[-1].split('?')[0]
    csv_file = save_comments_csv(comments, note_id)

    print(f"\n[步骤 4] 保存结果")
    print("-" * 50)
    print(f"  ✅ 已保存到: {csv_file}")

    # 显示预览
    print(f"\n[评论预览]")
    print("-" * 50)
    for i, comment in enumerate(comments[:5], 1):
        content = comment.get('content', '')[:80]
        if len(content) == 80:
            content += "..."
        print(f"  {i}. [{comment['likes']}赞] {comment['author']}: {content}")

    if len(comments) > 5:
        print(f"  ... 还有 {len(comments) - 5} 条")

    print("\n" + "="*70)
    print("✅ 完成！")
    print("="*70)
    print(f"\n可以使用以下命令分析评论:")
    print(f"   python comment_analyzer.py -csv {csv_file} -o analysis.md")
    print("="*70)


def main(note_url: str = None, count: int = None):
    """同步主程序入口"""
    asyncio.run(main_async(note_url, count))


if __name__ == "__main__":
    try:
        # 支持命令行参数
        url = sys.argv[1] if len(sys.argv) > 1 else None
        cnt = int(sys.argv[2]) if len(sys.argv) > 2 else None
        main(url, cnt)
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
