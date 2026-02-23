#!/usr/bin/env python3
"""
B站和小红书评论爬取统一入口

使用方法:
    # 爬取B站评论
    python fetch_comments.py "https://www.bilibili.com/video/BV1xx411c7mD/"

    # 爬取小红书评论
    python fetch_comments.py "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

    # 批量处理
    python fetch_comments.py --csv urls.csv

    # 指定平台
    python fetch_comments.py --platform bilibili --url "xxx"
    python fetch_comments.py --platform xiaohongshu --url "xxx"

    # 指定评论数量
    python fetch_comments.py "URL" -n 100
"""

import asyncio
import sys
import csv
import argparse
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from platforms.comments import PlatformDetector, CommentCrawlerFactory
from platforms.comments.output_formatter import CSVOutputFormatter, JSONOutputFormatter


async def main():
    parser = argparse.ArgumentParser(
        description="B站和小红书评论爬取统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 爬取B站评论:
   python fetch_comments.py "https://www.bilibili.com/video/BV1xx411c7mD/"

2. 爬取小红书评论:
   python fetch_comments.py "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

3. 批量处理CSV:
   python fetch_comments.py --csv urls.csv

4. 指定平台:
   python fetch_comments.py --platform bilibili --url "xxx"
   python fetch_comments.py --platform xiaohongshu --url "xxx"

5. 指定评论数量:
   python fetch_comments.py "URL" -n 100

注意:
- B站评论爬取使用纯HTTP方式，只需要Cookie即可
- 小红书评论爬取依赖MediaCrawler框架，需要Playwright等依赖
- Cookie统一存储在 config/cookies.txt 中
        """
    )

    parser.add_argument('url', nargs='?', help='要爬取的链接（可选，如果使用--url参数）')
    parser.add_argument('--url', help='指定链接')
    parser.add_argument('--platform', '-p', choices=['bilibili', 'xhs', 'xiaohongshu', 'auto'],
                        default='auto', help='指定平台（默认自动识别）')
    parser.add_argument('--count', '-n', type=int, default=50, help='爬取评论数量（默认50）')
    parser.add_argument('--csv', help='批量处理CSV文件')
    parser.add_argument('--output', '-o', help='输出目录（默认comments_output）')
    parser.add_argument('--format', '-f', choices=['csv', 'json'], default='csv', help='输出格式（默认csv）')
    parser.add_argument('--no-headless', action='store_true', help='小红书使用非无头模式')

    args = parser.parse_args()

    # 确定URL
    target_url = args.url if args.url else args.url if hasattr(args, 'url') else args.url

    # 确定平台
    platform = args.platform
    if platform == 'xhs':
        platform = 'xiaohongshu'

    # 输出目录
    output_dir = Path(args.output) if args.output else Path("comments_output")

    # 如果是批量处理
    if args.csv:
        await process_csv(args.csv, platform, args.count, output_dir, args.format)
        return

    # 单个链接处理
    if not target_url:
        print("错误：请提供URL或使用--csv参数")
        parser.print_help()
        return

    await fetch_single_url(target_url, platform, args.count, output_dir, args.format, not args.no_headless)


async def fetch_single_url(url, platform, count, output_dir, output_format, headless=True):
    """
    爬取单个URL的评论

    Args:
        url: URL
        platform: 平台名称
        count: 最大评论数
        output_dir: 输出目录
        output_format: 输出格式
        headless: 是否使用无头模式
    """
    print(f"\n{'='*70}")
    print("统一评论爬取工具")
    print(f"{'='*70}")
    print(f"\nURL: {url}")

    # 检测平台
    if platform == 'auto':
        detector = PlatformDetector()
        detected_platform = detector.detect(url)
        print(f"检测到平台: {detected_platform}")
        platform = detected_platform
    else:
        print(f"指定平台: {platform}")

    if platform == 'unknown':
        print("\n错误：无法识别的平台")
        print("支持的平台：bilibili, xiaohongshu")
        return

    # 创建爬虫
    try:
        factory = CommentCrawlerFactory()
        crawler = factory.create(platform, headless=headless)
    except Exception as e:
        print(f"\n错误：{e}")
        return

    # 执行爬取
    print(f"\n开始爬取评论（目标数量: {count}）...")

    try:
        comments = await crawler.fetch(url, max_comments=count)
    except Exception as e:
        print(f"\n错误：爬取失败 - {e}")

        if platform == 'xiaohongshu':
            print("\n提示：小红书评论爬取需要MediaCrawler依赖")
            print("      如果遇到依赖问题，可以单独运行:")
            print("      python platforms/xiaohongshu/fetch_xhs_comments.py <URL>")
        return

    if not comments:
        print("\n未获取到评论")
        return

    print(f"成功获取 {len(comments)} 条评论")

    # 保存结果
    formatter = CSVOutputFormatter() if output_format == 'csv' else JSONOutputFormatter()
    output_file = formatter.save(comments, url, output_dir)

    print(f"已保存到: {output_file}")

    # 显示预览
    print(f"\n评论预览（前5条）:")
    print("-" * 70)
    for i, comment in enumerate(comments[:5], 1):
        content = comment.get('content', '')[:60]
        if len(content) == 60:
            content += "..."
        print(f"{i}. [{comment['likes']}赞] {comment['author']}: {content}")

    if len(comments) > 5:
        print(f"... 还有 {len(comments) - 5} 条")

    print(f"\n{'='*70}")
    print("完成！")
    print(f"{'='*70}")


async def process_csv(csv_path, platform, count, output_dir, output_format):
    """
    批量处理CSV文件

    Args:
        csv_path: CSV文件路径
        platform: 平台名称
        count: 每个URL的评论数量
        output_dir: 输出目录
        output_format: 输出格式
    """
    print(f"\n{'='*70}")
    print("批量处理模式")
    print(f"{'='*70}")
    print(f"\n处理CSV文件: {csv_path}")

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # 查找URL列
            url_col = None
            for col in ['链接', 'url', 'link', 'video_url', 'note_url']:
                if col in reader.fieldnames:
                    url_col = col
                    break

            if not url_col:
                print(f"\n错误：未找到URL列，可用列: {reader.fieldnames}")
                return

            print(f"使用列: {url_col}")
            print(f"平台: {platform}")
            print(f"每个URL评论数: {count}\n")

            results = []
            for i, row in enumerate(reader, 1):
                url = row.get(url_col, '').strip()
                if not url:
                    continue

                print(f"[{i}] 处理: {url[:60]}...")

                try:
                    await fetch_single_url(url, platform, count, output_dir, output_format)
                    results.append({'url': url, 'success': True})
                except Exception as e:
                    print(f"  失败: {e}")
                    results.append({'url': url, 'success': False, 'error': str(e)})

        # 输出汇总
        print(f"\n{'='*70}")
        print(f"批量处理完成")
        print(f"{'='*70}")
        success_count = sum(1 for r in results if r['success'])
        print(f"总计: {len(results)} | 成功: {success_count} | 失败: {len(results)-success_count}")

    except FileNotFoundError:
        print(f"\n错误：文件不存在 - {csv_path}")
    except Exception as e:
        print(f"\n错误：{e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
