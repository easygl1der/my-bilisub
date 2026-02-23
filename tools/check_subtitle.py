#!/usr/bin/env python3
"""
视频字幕检查工具 - 检查是否有内置字幕轨道

支持平台:
- B站: 检查 CC 字幕 / ASS 字幕
- 小红书: 检查嵌入字幕
- 通用: 检查视频文件内嵌字幕

优先级:
1. 内置字幕（最快，直接提取）
2. OCR 识别（较慢，需要提取画面）
3. Whisper 转录（最慢，但最准确）
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yt_dlp

# ==================== 配置 ====================
OUTPUT_DIR = Path("output/subtitle_check")
# ==============================================


def detect_platform(url: str) -> str:
    """识别平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    else:
        return 'unknown'


def check_bilibili_subtitles(url: str) -> Dict:
    """
    检查B站视频字幕

    Returns:
        {
            'has_subtitle': bool,
            'subtitle_type': str,  # 'cc', 'ass', 'srt', 'none'
            'subtitles': [
                {'lan': 'zh-CN', 'lan_doc': '中文（中国）', 'subtitle_url': '...'}
            ],
            'video_info': {...}
        }
    """
    try:
        # 方法1: 使用 yt-dlp 检查字幕
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'listsubs': True,  # 列出字幕
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            result = {
                'platform': 'B站',
                'has_subtitle': False,
                'subtitle_type': 'none',
                'subtitles': [],
                'automatic_captions': [],
                'video_info': {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                }
            }

            # 检查手动字幕
            if info.get('subtitles'):
                result['has_subtitle'] = True
                result['subtitle_type'] = 'manual'

                for lang, subs in info['subtitles'].items():
                    result['subtitles'].append({
                        'lang': lang,
                        'type': 'manual',
                        'data': subs
                    })

            # 检查自动字幕 (CC)
            if info.get('automatic_captions'):
                if not result['has_subtitle']:
                    result['has_subtitle'] = True
                    result['subtitle_type'] = 'automatic'

                for lang, caps in info['automatic_captions'].items():
                    result['automatic_captions'].append({
                        'lang': lang,
                        'type': 'automatic',
                        'data': caps
                    })

            return result

    except Exception as e:
        return {
            'platform': 'B站',
            'error': str(e),
            'has_subtitle': False
        }


def check_xiaohongshu_subtitles(url: str) -> Dict:
    """
    检查小红书视频字幕

    小红书一般没有独立字幕轨道，但可能在视频中嵌入
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            result = {
                'platform': '小红书',
                'has_subtitle': False,
                'subtitle_type': 'none',
                'subtitles': [],
                'video_info': {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'description': info.get('description', ''),
                }
            }

            # 检查是否有字幕轨道
            if info.get('subtitles'):
                result['has_subtitle'] = True
                for lang, subs in info['subtitles'].items():
                    result['subtitles'].append({
                        'lang': lang,
                        'data': subs
                    })

            # 检查自动字幕
            if info.get('automatic_captions'):
                result['has_subtitle'] = True
                if not result['subtitles']:
                    result['subtitle_type'] = 'automatic'

            return result

    except Exception as e:
        return {
            'platform': '小红书',
            'error': str(e),
            'has_subtitle': False
        }


def format_result(result: Dict) -> str:
    """格式化检查结果"""
    output = []
    output.append("=" * 70)
    output.append(f"📹 平台: {result.get('platform', 'Unknown')}")
    output.append("=" * 70)

    if 'error' in result:
        output.append(f"❌ 错误: {result['error']}")
        return '\n'.join(output)

    # 视频信息
    if 'video_info' in result:
        info = result['video_info']
        output.append(f"📼 标题: {info.get('title', 'N/A')}")
        output.append(f"⏱️  时长: {info.get('duration', 0)} 秒")
        if 'uploader' in info:
            output.append(f"👤 上传者: {info.get('uploader', 'N/A')}")

    output.append("")

    # 字幕状态
    if result['has_subtitle']:
        output.append("✅ 发现字幕!")
        output.append(f"   类型: {result['subtitle_type']}")

        # 手动字幕
        if result.get('subtitles'):
            output.append(f"\n📝 手动字幕 ({len(result['subtitles'])} 个):")
            for sub in result['subtitles']:
                output.append(f"   - 语言: {sub['lang']}")
                if 'url' in sub.get('data', {}):
                    output.append(f"     下载: {sub['data']['url']}")

        # 自动字幕
        if result.get('automatic_captions'):
            output.append(f"\n🤖 自动字幕/CC ({len(result['automatic_captions'])} 个):")
            for cap in result['automatic_captions']:
                output.append(f"   - 语言: {cap['lang']}")
                if 'url' in cap.get('data', {}):
                    output.append(f"     下载: {cap['data']['url']}")

        # 建议操作
        output.append("\n💡 建议:")
        output.append("   ✓ 直接提取内置字幕（最快，无需识别）")

    else:
        output.append("❌ 未发现字幕")
        output.append("\n💡 建议方案:")
        output.append("   1. 尝试 OCR 识别（视频中有文字）")
        output.append("   2. 使用 Whisper 转录（语音识别）")

    output.append("=" * 70)

    return '\n'.join(output)


def save_report(url: str, result: Dict, output_dir: Path):
    """保存检查报告"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    platform = result.get('platform', 'unknown')
    video_id = result.get('video_info', {}).get('title', 'unknown')[:50]
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in video_id)

    # JSON 报告
    json_path = output_dir / f"{platform}_{safe_name}_check.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'url': url,
            'check_result': result
        }, f, ensure_ascii=False, indent=2)

    print(f"\n📊 报告已保存: {json_path}")


def check_url(url: str) -> Dict:
    """统一检查入口"""
    platform = detect_platform(url)

    if platform == 'bilibili':
        return check_bilibili_subtitles(url)
    elif platform == 'xiaohongshu':
        return check_xiaohongshu_subtitles(url)
    else:
        return {
            'platform': 'Unknown',
            'error': '不支持的平台',
            'has_subtitle': False
        }


def main():
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import argparse
    parser = argparse.ArgumentParser(description="视频字幕检查工具")
    parser.add_argument("-u", "--url", help="视频链接")
    parser.add_argument("-f", "--file", help="批量检查文件")
    parser.add_argument("--save", action="store_true", help="保存检查报告")

    args = parser.parse_args()

    if args.url:
        # 单链接检查
        result = check_url(args.url)
        print(format_result(result))

        if args.save:
            save_report(args.url, result, OUTPUT_DIR)

    elif args.file:
        # 批量检查
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        print(f"📋 批量检查: {len(urls)} 个链接\n")

        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url[:60]}...")
            result = check_url(url)
            print(format_result(result))
            results.append({'url': url, 'result': result})

        # 保存汇总报告
        if args.save:
            summary_path = OUTPUT_DIR / "batch_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n📊 批量报告: {summary_path}")

    else:
        # 交互模式
        url = input("粘贴视频链接: ").strip()
        if url:
            result = check_url(url)
            print(format_result(result))


if __name__ == "__main__":
    main()
