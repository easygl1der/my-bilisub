#!/usr/bin/env python3
"""
批量视频处理工具 - 完整流程

功能：
1. 从文件读取多个视频链接
2. 自动处理每个视频：下载 + Whisper识别 + GLM优化
3. 生成完整的批量处理报告

支持格式：
- B站视频
- 小红书视频
- CSV文件（第一列为URL）
- 纯文本文件（每行一个URL）
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import subprocess

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def detect_platform(url):
    """检测视频平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    else:
        return 'unknown'


def process_video(url, whisper_model='medium', prompt_type='optimization'):
    """
    处理单个视频的完整流程

    Args:
        url: 视频URL
        whisper_model: Whisper模型（默认medium）
        prompt_type: GLM优化模式

    Returns:
        dict: 处理结果
    """
    result = {
        'url': url,
        'platform': detect_platform(url),
        'success': False,
        'error': None,
        'transcribe_time': 0,
        'optimize_time': 0,
        'total_time': 0,
        'srt_path': None,
        'optimized_path': None
    }

    print(f"\n{'='*80}")
    print(f"🎬 处理视频 [{result['platform'].upper()}]")
    print(f"📎 URL: {url[:80]}...")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        # 步骤1：Whisper识别
        print("\n📝 步骤 1/2: Whisper语音识别...")
        print(f"   模型: {whisper_model}")

        transcribe_start = time.time()
        cmd_transcribe = [
            'python', 'ultimate_transcribe.py',
            '-u', url,
            '--model', whisper_model,
            '--no-ocr'
        ]

        transcribe_result = subprocess.run(
            cmd_transcribe,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=1800  # 30分钟超时
        )

        transcribe_time = time.time() - transcribe_start
        result['transcribe_time'] = transcribe_time

        if transcribe_result.returncode != 0:
            result['error'] = f"Whisper识别失败: {transcribe_result.stderr[-200:]}"
            print(f"❌ {result['error']}")
            return result

        print(f"✅ Whisper完成 (耗时: {transcribe_time:.2f}秒)")

        # 查找生成的SRT文件
        import glob
        srt_files = glob.glob('output/transcripts/*.srt')

        if not srt_files:
            result['error'] = "未找到生成的SRT文件"
            print(f"❌ {result['error']}")
            return result

        # 使用最新的SRT文件
        srt_file = max(srt_files, key=os.path.getmtime)
        result['srt_path'] = srt_file
        print(f"📄 字幕文件: {os.path.basename(srt_file)}")

        # 步骤2：GLM优化
        print("\n🤖 步骤 2/2: GLM字幕优化...")
        print(f"   模式: {prompt_type}")

        optimize_start = time.time()
        cmd_optimize = [
            'python', 'optimize_srt_glm.py',
            '-s', srt_file,
            '-p', prompt_type
        ]

        optimize_result = subprocess.run(
            cmd_optimize,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300  # 5分钟超时
        )

        optimize_time = time.time() - optimize_start
        result['optimize_time'] = optimize_time

        if optimize_result.returncode != 0:
            result['error'] = f"GLM优化失败: {optimize_result.stderr[-200:]}"
            print(f"⚠️  {result['error']}")
            print("💡 Whisper成功，但优化失败，已保留原始字幕")
            result['success'] = True  # 部分成功
        else:
            print(f"✅ GLM优化完成 (耗时: {optimize_time:.2f}秒)")

            # 查找优化后的文件
            optimized_file = srt_file.replace('/transcripts/', '/optimized_srt/')
            optimized_file = optimized_file.replace('.srt', '_optimized.srt')
            if os.path.exists(optimized_file):
                result['optimized_path'] = optimized_file
                print(f"📄 优化文件: {os.path.basename(optimized_file)}")

            result['success'] = True

        total_time = time.time() - start_time
        result['total_time'] = total_time

        print(f"\n✅ 视频处理完成!")
        print(f"   总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")

    except subprocess.TimeoutExpired:
        result['error'] = "处理超时"
        print(f"❌ {result['error']}")
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ 处理出错: {e}")

    return result


def read_urls_from_file(file_path):
    """从文件读取视频URL列表"""
    urls = []

    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == '.csv':
        # 从CSV文件读取（假设第一列是URL）
        import csv
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    url = row[0].strip()
                    if url and not url.startswith('#'):  # 跳过注释
                        urls.append(url)

    else:
        # 纯文本文件（每行一个URL）
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):  # 跳过空行和注释
                    urls.append(url)

    return urls


def save_batch_report(results, output_file):
    """保存批量处理报告"""
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_videos': len(results),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'total_time': sum(r['total_time'] for r in results),
        'results': results
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 同时生成Markdown报告
    md_file = output_file.replace('.json', '.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(f"# 批量视频处理报告\n\n")
        f.write(f"**时间**: {report['timestamp']}\n\n")
        f.write(f"## 📊 总体统计\n\n")
        f.write(f"- 总视频数: {report['total_videos']}\n")
        f.write(f"- 成功: {report['successful']}\n")
        f.write(f"- 失败: {report['failed']}\n")
        f.write(f"- 总耗时: {report['total_time']:.2f}秒 ({report['total_time']/60:.1f}分钟)\n")
        f.write(f"- 平均每视频: {report['total_time']/len(results):.1f}秒\n\n")

        f.write(f"## 📝 详细结果\n\n")

        for i, result in enumerate(results, 1):
            status = "✅ 成功" if result['success'] else "❌ 失败"
            f.write(f"### {i}. {result['platform'].upper()} - {status}\n\n")
            f.write(f"**URL**: {result['url'][:80]}...\n\n")
            f.write(f"- Whisper耗时: {result['transcribe_time']:.1f}秒\n")
            f.write(f"- GLM优化耗时: {result['optimize_time']:.1f}秒\n")
            f.write(f"- 总耗时: {result['total_time']:.1f}秒\n")

            if result['srt_path']:
                f.write(f"- 字幕文件: `{result['srt_path']}`\n")
            if result['optimized_path']:
                f.write(f"- 优化文件: `{result['optimized_path']}`\n")
            if result['error']:
                f.write(f"- 错误: {result['error']}\n")

            f.write("\n")

    print(f"\n📊 报告已保存:")
    print(f"   JSON: {output_file}")
    print(f"   Markdown: {md_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="批量视频处理工具 - 完整流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 单个视频URL:
   python batch_process_videos.py -u "https://www.bilibili.com/video/BVxxxxxx/"

2. 多个视频URL:
   python batch_process_videos.py -u "url1" -u "url2" -u "url3"

3. 从文本文件读取URL列表:
   python batch_process_videos.py -i urls.txt

4. 从CSV文件读取:
   python batch_process_videos.py -i videos.csv

5. 指定Whisper模型:
   python batch_process_videos.py -u "url" -m small

6. 指定GLM优化模式:
   python batch_process_videos.py -i urls.txt -p tech

7. 完整配置:
   python batch_process_videos.py -i urls.txt -m medium -p optimization

文件格式:
- 文本文件: 每行一个URL
- CSV文件: 第一列为URL
- 支持注释: 以#开头的行会被忽略
        """
    )

    # 输入源（三种模式互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '-u', '--urls',
        nargs='+',
        help='一个或多个视频URL（空格分隔）'
    )
    input_group.add_argument(
        '-i', '--input-file',
        help='包含视频URL的文件（txt/csv）'
    )

    parser.add_argument(
        '-m', '--model',
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper模型（默认: medium）'
    )
    parser.add_argument(
        '-p', '--prompt',
        default='optimization',
        choices=['optimization', 'simple', 'conservative', 'aggressive', 'tech', 'interview', 'vlog'],
        help='GLM优化模式（默认: optimization）'
    )
    parser.add_argument(
        '-o', '--output',
        default='batch_report.json',
        help='报告输出文件（默认: batch_report.json）'
    )

    args = parser.parse_args()

    # 获取URL列表
    if args.urls:
        # 直接使用命令行提供的URL
        urls = args.urls
        print(f"📖 接收到 {len(urls)} 个视频URL（命令行参数）")
    else:
        # 从文件读取
        print(f"📖 从文件读取视频列表: {args.input_file}")
        urls = read_urls_from_file(args.input_file)

    if not urls:
        print("❌ 未找到有效的视频URL")
        return

    print(f"✅ 找到 {len(urls)} 个视频URL")
    print(f"\n配置:")
    print(f"  Whisper模型: {args.model}")
    print(f"  GLM优化: {args.prompt}")
    print(f"\n开始处理...\n")

    # 批量处理
    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n{'#'*80}")
        print(f"# 进度: [{i}/{len(urls)}]")
        print(f"{'#'*80}")

        result = process_video(
            url,
            whisper_model=args.model,
            prompt_type=args.prompt
        )

        results.append(result)

        # 如果不是最后一个，休息一下
        if i < len(urls):
            print("\n⏳ 等待3秒后处理下一个视频...")
            time.sleep(3)

    # 保存报告
    print(f"\n{'='*80}")
    print("🎉 批量处理完成!")
    print(f"{'='*80}")

    save_batch_report(results, args.output)

    # 打印总结
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    total_time = sum(r['total_time'] for r in results)

    print(f"\n📊 处理总结:")
    print(f"   总数: {len(results)}")
    print(f"   成功: {successful}")
    print(f"   失败: {failed}")
    print(f"   总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")
    print(f"   平均: {total_time/len(results):.1f}秒/视频")

    if failed > 0:
        print(f"\n⚠️  有{failed}个视频处理失败，请查看报告详情")


if __name__ == "__main__":
    main()
