#!/usr/bin/env python3
"""
增强型CSV视频批量处理工作流 - 整合MediaCrawler数据

功能：
1. 从MediaCrawler数据提取视频链接
2. 从CSV文件读取视频列表
3. 自动过滤指定状态的视频
4. 批量处理：下载 → Whisper → GLM优化
5. 更新CSV处理状态
"""

import os
import sys
import csv
import json
import time
from pathlib import Path
from datetime import datetime
import subprocess
import shutil
from typing import List, Dict

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== MediaCrawler数据提取模块 ====================

def find_latest_file(directory, pattern):
    """查找最新的文件"""
    files = list(Path(directory).glob(pattern))
    if not files:
        return None
    return max(files, key=lambda x: x.stat().st_mtime)


def extract_from_mediacrawler_csv(csv_file):
    """从MediaCrawler的CSV提取链接"""
    videos = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            note_id = row.get('note_id', row.get('笔记ID', ''))
            title = row.get('title', row.get('标题', '无标题'))
            note_type = row.get('type', row.get('类型', 'video'))

            if note_id:
                url = f"https://www.xiaohongshu.com/explore/{note_id}"
                videos.append({
                    'note_id': note_id,
                    'title': title,
                    'url': url,
                    'type': note_type,
                    'source': 'mediacrawler_csv',
                    'status': '',
                    'error': ''
                })
    return videos


def extract_from_mediacrawler_json(json_file):
    """从MediaCrawler的JSON提取链接"""
    videos = []
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

        # 处理不同的JSON格式
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('notes', data.get('videos', []))
        else:
            items = []

        for item in items:
            note_id = item.get('note_id', '')
            title = item.get('title', '无标题')
            note_type = item.get('type', 'video')

            if note_id:
                url = f"https://www.xiaohongshu.com/explore/{note_id}"
                videos.append({
                    'note_id': note_id,
                    'title': title,
                    'url': url,
                    'type': note_type,
                    'source': 'mediacrawler_json',
                    'status': '',
                    'error': ''
                })
    return videos


def extract_links_from_mediacrawler(data_dir="data/xhs"):
    """
    从MediaCrawler数据目录提取视频链接

    Args:
        data_dir: MediaCrawler数据目录

    Returns:
        list: 视频信息列表
    """
    print(f"\n🔍 正在查找MediaCrawler数据...")
    print(f"   目录: {data_dir}")

    if not os.path.exists(data_dir):
        print(f"   ❌ 数据目录不存在")
        return None

    # 查找CSV文件
    csv_file = find_latest_file(data_dir, "xhs_notes_*.csv")
    json_file = find_latest_file(data_dir, "xhs_notes_*.json")

    videos = None

    if csv_file:
        print(f"   ✅ 找到CSV: {csv_file.name}")
        videos = extract_from_mediacrawler_csv(csv_file)
    elif json_file:
        print(f"   ✅ 找到JSON: {json_file.name}")
        videos = extract_from_mediacrawler_json(json_file)
    else:
        print(f"   ❌ 未找到数据文件")
        return None

    if not videos:
        print(f"   ⚠️  数据文件为空")
        return None

    print(f"   ✅ 提取到 {len(videos)} 个视频链接")
    return videos


# ==================== CSV读取模块 ====================

def read_csv_with_filter(csv_file, status_filter=None):
    """
    从CSV读取视频并过滤

    Args:
        csv_file: CSV文件路径
        status_filter: 状态过滤器（None=全部, 'success'=只成功的, 'fail'=只失败的）

    Returns:
        list: 视频信息列表
    """
    videos = []

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # 跳过没有链接的行
            if not row.get('链接'):
                continue

            # 状态过滤
            if status_filter:
                current_status = row.get('subtitle_status', '').strip().lower()
                if status_filter == 'success' and current_status != 'success':
                    continue
                elif status_filter == 'fail' and current_status != 'fail':
                    continue

            videos.append({
                'index': row.get('序号', ''),
                'title': row.get('标题', ''),
                'url': row['链接'],
                'type': row.get('类型', 'video'),
                'likes': row.get('点赞数', ''),
                'comments': row.get('评论数', ''),
                'publish_time': row.get('发布时间', ''),
                'status': row.get('subtitle_status', ''),
                'error': row.get('subtitle_error', ''),
                'source': 'csv_file'
            })

    return videos


def save_videos_to_csv(videos, output_file):
    """将视频列表保存为CSV文件"""
    if not videos:
        print("❌ 没有视频数据可保存")
        return None

    # 确定字段
    fieldnames = ['序号', '标题', '链接', '类型', '点赞数', '评论数', '发布时间', 'subtitle_status', 'subtitle_error']

    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, video in enumerate(videos, 1):
            writer.writerow({
                '序号': i,
                '标题': video.get('title', ''),
                '链接': video.get('url', ''),
                '类型': video.get('type', 'video'),
                '点赞数': video.get('likes', ''),
                '评论数': video.get('comments', ''),
                '发布时间': video.get('publish_time', ''),
                'subtitle_status': video.get('status', ''),
                'subtitle_error': video.get('error', '')
            })

    print(f"✅ 视频列表已保存: {output_file}")
    return output_file


# ==================== 视频处理模块 ====================

def process_single_video(video_info, model='medium', prompt='optimization'):
    """
    处理单个视频

    Returns:
        dict: 处理结果
    """
    url = video_info['url']

    result = {
        'url': url,
        'title': video_info['title'],
        'success': False,
        'error': None,
        'whisper_time': 0,
        'optimize_time': 0,
        'total_time': 0
    }

    print(f"\n{'='*80}")
    print(f"🎬 处理视频: {video_info['title']}")
    print(f"📎 URL: {url[:80]}...")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        # 步骤1：Whisper识别
        print("\n📝 步骤 1/2: Whisper语音识别...")
        whisper_start = time.time()

        cmd = [
            'python', 'ultimate_transcribe.py',
            '-u', url,
            '--model', model,
            '--no-ocr'
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=1800
        )

        result['whisper_time'] = time.time() - whisper_start

        if proc.returncode != 0:
            result['error'] = "Whisper失败"
            print(f"❌ {result['error']}")
            return result

        print(f"✅ Whisper完成 (耗时: {result['whisper_time']:.1f}秒)")

        # 查找SRT文件
        import glob
        srt_files = glob.glob('output/transcripts/*.srt')
        if not srt_files:
            result['error'] = "未找到SRT文件"
            print(f"❌ {result['error']}")
            return result

        srt_file = max(srt_files, key=os.path.getmtime)
        print(f"📄 字幕文件: {os.path.basename(srt_file)}")

        # 步骤2：GLM优化
        print("\n🤖 步骤 2/2: GLM字幕优化...")
        print(f"   模式: {prompt}")

        optimize_start = time.time()
        cmd = [
            'python', 'optimize_srt_glm.py',
            '-s', srt_file,
            '-p', prompt
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300
        )

        result['optimize_time'] = time.time() - optimize_start

        if proc.returncode != 0:
            print(f"⚠️  GLM优化失败，但保留了原始字幕")
        else:
            print(f"✅ GLM优化完成 (耗时: {result['optimize_time']:.1f}秒)")

        result['success'] = True
        result['total_time'] = time.time() - start_time

        print(f"\n✅ 处理完成! 总耗时: {result['total_time']:.1f}秒")

    except subprocess.TimeoutExpired:
        result['error'] = "处理超时"
        print(f"❌ {result['error']}")
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ 处理出错: {e}")

    return result


def update_csv_status(csv_file, processed_results):
    """
    更新CSV文件的处理状态

    Args:
        csv_file: 原CSV文件
        processed_results: 处理结果列表
    """
    # 备份原文件
    backup_file = csv_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    shutil.copy2(csv_file, backup_file)
    print(f"\n💾 原文件已备份到: {os.path.basename(backup_file)}")

    # 读取原数据
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # 创建URL到结果的映射
    url_to_result = {}
    for result in processed_results:
        url_to_result[result['url']] = result

    # 更新状态
    for row in rows:
        url = row.get('链接', '')
        if url in url_to_result:
            result = url_to_result[url]
            if result['success']:
                row['subtitle_status'] = 'success'
                row['subtitle_error'] = ''
            else:
                row['subtitle_status'] = 'fail'
                row['subtitle_error'] = result.get('error', 'Unknown error')

    # 写入更新后的CSV
    output_file = csv_file.replace('.csv', '_processed.csv')
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ 更新后的CSV已保存: {output_file}")


def save_workflow_report(videos, results, output_file):
    """保存工作流报告"""
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_videos': len(videos),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'total_time': sum(r['total_time'] for r in results),
        'results': results
    }

    # JSON报告
    json_file = output_file.replace('.md', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# 视频处理工作流报告\n\n")
        f.write(f"**时间**: {report['timestamp']}\n\n")
        f.write(f"## 📊 总体统计\n\n")
        f.write(f"- 总视频数: {report['total_videos']}\n")
        f.write(f"- 成功: {report['successful']}\n")
        f.write(f"- 失败: {report['failed']}\n")
        f.write(f"- 总耗时: {report['total_time']:.1f}秒 ({report['total_time']/60:.1f}分钟)\n")
        f.write(f"- 平均: {report['total_time']/len(results):.1f}秒/视频\n\n")

        f.write(f"## 📝 详细结果\n\n")

        for i, (video, result) in enumerate(zip(videos, results), 1):
            status = "✅ 成功" if result['success'] else "❌ 失败"
            f.write(f"### {i}. {video['title']}\n\n")
            f.write(f"**状态**: {status}\n\n")
            f.write(f"- URL: {video['url'][:80]}...\n")
            f.write(f"- Whisper耗时: {result['whisper_time']:.1f}秒\n")
            f.write(f"- GLM优化耗时: {result['optimize_time']:.1f}秒\n")
            f.write(f"- 总耗时: {result['total_time']:.1f}秒\n")
            if result['error']:
                f.write(f"- 错误: {result['error']}\n")
            f.write("\n")

    print(f"\n📊 报告已保存:")
    print(f"   JSON: {json_file}")
    print(f"   Markdown: {output_file}")


# ==================== 主程序 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="增强型CSV视频批量处理工作流 - 整合MediaCrawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 从MediaCrawler数据提取并处理:
   python enhanced_workflow.py --mediacrawler

2. 从MediaCrawler数据提取并保存为CSV:
   python enhanced_workflow.py --mediacrawler --export-crawled videos.csv

3. 处理CSV中的所有视频:
   python enhanced_workflow.py --csv videos.csv

4. 只处理成功的视频:
   python enhanced_workflow.py --csv videos.csv --filter success

5. 只处理失败的视频:
   python enhanced_workflow.py --csv videos.csv --filter fail

6. 指定模型和优化模式:
   python enhanced_workflow.py --csv videos.csv --model medium --prompt tech

7. 处理前3个视频:
   python enhanced_workflow.py --csv videos.csv --limit 3
        """
    )

    # 输入源（三种模式互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--mediacrawler',
        action='store_true',
        help='从MediaCrawler数据提取链接'
    )
    input_group.add_argument(
        '--csv',
        metavar='FILE',
        help='从CSV文件读取'
    )

    parser.add_argument(
        '--data-dir',
        default='data/xhs',
        help='MediaCrawler数据目录（默认: data/xhs）'
    )
    parser.add_argument(
        '--export-crawled',
        metavar='FILE',
        help='将从MediaCrawler提取的数据导出为CSV'
    )
    parser.add_argument(
        '--filter',
        choices=['all', 'success', 'fail'],
        default='all',
        help='过滤视频状态（默认: all）'
    )
    parser.add_argument(
        '--model',
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper模型（默认: medium）'
    )
    parser.add_argument(
        '--prompt',
        default='optimization',
        choices=['optimization', 'simple', 'conservative', 'aggressive', 'tech', 'interview', 'vlog'],
        help='GLM优化模式（默认: optimization）'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='限制处理数量（0=全部）'
    )
    parser.add_argument(
        '--no-update',
        action='store_true',
        help='不更新CSV文件'
    )

    args = parser.parse_args()

    videos = None
    csv_file = None

    # 方式1: 从MediaCrawler提取
    if args.mediacrawler:
        print("\n" + "="*80)
        print("🔥 MediaCrawler数据提取模式")
        print("="*80)

        videos = extract_links_from_mediacrawler(args.data_dir)

        if not videos:
            print("\n❌ 无法从MediaCrawler提取数据")
            return

        # 如果指定了导出CSV
        if args.export_crawled:
            csv_file = args.export_crawled
            save_videos_to_csv(videos, csv_file)
            print(f"\n✅ 数据已导出到: {csv_file}")
            print("   你现在可以使用 --csv 参数处理这个文件")
            return

        # 否则创建临时CSV
        csv_file = f"temp_mediacrawler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_videos_to_csv(videos, csv_file)
        print(f"\n✅ 临时CSV已创建: {csv_file}")

    # 方式2: 从CSV读取
    elif args.csv:
        csv_file = args.csv
        print(f"\n📖 从CSV读取视频列表: {csv_file}")

        status_filter = None if args.filter == 'all' else args.filter
        videos = read_csv_with_filter(csv_file, status_filter)

        if not videos:
            print("❌ 未找到符合条件的视频")
            return

        print(f"🔍 过滤条件: {args.filter}")

    # 限制数量
    if args.limit > 0:
        original_count = len(videos)
        videos = videos[:args.limit]
        print(f"⚠️  限制处理数量: {args.limit} (原共{original_count}个)")

    print(f"\n✅ 找到 {len(videos)} 个视频")
    print(f"\n配置:")
    print(f"  Whisper模型: {args.model}")
    print(f"  GLM优化: {args.prompt}")
    print(f"  更新CSV: {'否' if args.no_update else '是'}")
    print(f"\n开始处理...\n")

    # 批量处理
    results = []
    for i, video in enumerate(videos, 1):
        print(f"\n{'#'*80}")
        print(f"# 进度: [{i}/{len(videos)}]")
        print(f"{'#'*80}")

        result = process_single_video(
            video,
            model=args.model,
            prompt=args.prompt
        )

        results.append(result)

        # 等待一下再处理下一个
        if i < len(videos):
            print("\n⏳ 等待3秒后处理下一个视频...")
            time.sleep(3)

    # 保存报告
    print(f"\n{'='*80}")
    print("🎉 批量处理完成!")
    print(f"{'='*80}")

    report_file = csv_file.replace('.csv', '_workflow_report.md')
    save_workflow_report(videos, results, report_file)

    # 更新CSV
    if not args.no_update and csv_file:
        update_csv_status(csv_file, results)

    # 打印总结
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    total_time = sum(r['total_time'] for r in results)

    print(f"\n📊 处理总结:")
    print(f"   总数: {len(results)}")
    print(f"   成功: {successful}")
    print(f"   失败: {failed}")
    print(f"   总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
    print(f"   平均: {total_time/len(results):.1f}秒/视频")


if __name__ == "__main__":
    main()
