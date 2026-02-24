#!/usr/bin/env python3
"""
YouTube 频道视频批量下载与转录工具

支持两种模式：
1. API模式：使用 YouTube Data API 获取视频列表（需要 API Key）
2. 普通模式：使用 yt-dlp 获取视频列表

功能：
1. 从 YouTube 频道/用户/播放列表链接提取所有视频
2. 批量下载视频到本地
3. 使用 Gemini API 进行视频内容分析转录

使用示例:
    # 使用 API 模式（推荐，更稳定）
    python youtube_channel_downloader.py --channel "https://www.youtube.com/@username" --api-key YOUR_API_KEY

    # 普通模式
    python youtube_channel_downloader.py --channel "https://www.youtube.com/@username"

    # 下载并转录
    python youtube_channel_downloader.py --channel "https://www.youtube.com/@username" --transcribe

    # 使用代理
    set HTTPS_PROXY=http://127.0.0.1:7890
    python youtube_channel_downloader.py --channel "https://www.youtube.com/@username"
"""

import os
import sys
import csv
import re
import time
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

try:
    import yt_dlp
except ImportError:
    print("❌ 未安装 yt-dlp 库")
    print("请运行: pip install yt-dlp")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ 未安装 requests 库")
    print("请运行: pip install requests")
    sys.exit(1)

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 配置 ====================

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

# 导入 API 配置
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config_api import API_CONFIG
    DEFAULT_API_KEY = API_CONFIG.get('youtube', {}).get('api_key', '')
except ImportError:
    DEFAULT_API_KEY = ''


# ==================== 工具函数 ====================

def sanitize_filename(name: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    name = ''.join(char for char in name if ord(char) >= 32)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]
    return name or "untitled"


def detect_channel_type(url: str) -> str:
    """检测 YouTube 链接类型"""
    url_lower = url.lower()

    if 'youtube.com/playlist' in url_lower or 'list=' in url_lower:
        return 'playlist'
    elif '/channel/' in url_lower or '/c/' in url_lower or '/@' in url_lower:
        return 'channel'
    elif '/watch?v=' in url_lower or 'youtu.be/' in url_lower:
        return 'video'
    else:
        return 'unknown'


def extract_channel_id_from_url(url: str) -> str:
    """
    从 YouTube URL 中提取频道 ID

    支持的格式：
    - https://www.youtube.com/@username
    - https://www.youtube.com/c/username
    - https://www.youtube.com/channel/UCxxxxxx
    """
    # 直接是频道 ID
    if '/channel/UC' in url:
        match = re.search(r'/channel/(UC[\w-]+)', url)
        if match:
            return match.group(1)

    return None


def get_channel_id_by_handle(api_key: str, handle: str) -> str:
    """
    通过 @username 获取频道 ID

    Args:
        api_key: YouTube Data API Key
        handle: @username (不含@符号)

    Returns:
        频道 ID 或 None
    """
    params = {
        'key': api_key,
        'part': 'id',
        'forHandle': handle
    }

    try:
        response = requests.get(f"{YOUTUBE_API_URL}/channels", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('items'):
            return data['items'][0]['id']
    except Exception as e:
        print(f"   └─ ⚠️  API 获取频道 ID 失败: {e}")

    return None


def get_channel_videos_by_api(api_key: str, channel_id: str, limit: int = None) -> List[Dict]:
    """
    使用 YouTube Data API 获取频道的所有视频

    Args:
        api_key: YouTube Data API Key
        channel_id: 频道 ID (UCxxxxxx)
        limit: 限制数量

    Returns:
        视频列表
    """
    videos = []
    next_page_token = None
    total_retrieved = 0

    print(f"   📡 使用 YouTube API 获取视频列表...")

    while True:
        params = {
            'key': api_key,
            'part': 'snippet',
            'channelId': channel_id,
            'order': 'date',  # 按日期排序
            'type': 'video',
            'maxResults': min(50, limit - total_retrieved) if limit else 50,
        }

        if next_page_token:
            params['pageToken'] = next_page_token

        try:
            response = requests.get(f"{YOUTUBE_API_URL}/search", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 获取视频详情（包含时长）
            video_ids = [item['id']['videoId'] for item in data.get('items', [])]
            if video_ids:
                videos_details = get_videos_details(api_key, video_ids)

                for item in data.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    details = videos_details.get(video_id, {})

                    videos.append({
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'title': snippet['title'],
                        'id': video_id,
                        'duration': details.get('duration', 0),
                        'published_at': snippet.get('publishedAt', ''),
                        'description': snippet.get('description', '')[:200],
                    })

                total_retrieved = len(videos)
                percent = (total_retrieved / limit * 100) if limit else total_retrieved
                print(f"\r   📡 已获取 {total_retrieved} 个视频{'...' if limit and total_retrieved < limit else ''}", end='', flush=True)

            # 检查是否继续
            if limit and total_retrieved >= limit:
                break

            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break

        except Exception as e:
            print(f"\r   ⚠️  API 请求失败: {e}")
            break

    print()  # 换行
    return videos[:limit] if limit else videos


def get_videos_details(api_key: str, video_ids: List[str]) -> Dict[str, Dict]:
    """
    批量获取视频详情

    Args:
        api_key: YouTube Data API Key
        video_ids: 视频 ID 列表

    Returns:
        {video_id: {duration, ...}}
    """
    details = {}

    # YouTube API 一次最多查询 50 个视频
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]

        params = {
            'key': api_key,
            'part': 'contentDetails',
            'id': ','.join(batch)
        }

        try:
            response = requests.get(f"{YOUTUBE_API_URL}/videos", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data.get('items', []):
                video_id = item['id']
                # 解析时长 (PT1H30M15S -> seconds)
                duration_str = item['contentDetails'].get('duration', 'PT0S')
                duration = parse_duration(duration_str)

                details[video_id] = {
                    'duration': duration,
                    'duration_str': duration_str
                }

        except Exception as e:
            print(f"\n   ⚠️  获取视频详情失败: {e}")

    return details


def parse_duration(duration_str: str) -> int:
    """
    解析 ISO 8601 时长格式 (PT1H30M15S) 为秒数

    Args:
        duration_str: PT 格式的时长字符串

    Returns:
        秒数
    """
    if not duration_str or not duration_str.startswith('PT'):
        return 0

    duration_str = duration_str[2:]  # 移除 PT 前缀
    hours = minutes = seconds = 0

    # 解析小时
    if 'H' in duration_str:
        h_idx = duration_str.index('H')
        hours = int(duration_str[:h_idx])
        duration_str = duration_str[h_idx+1:]

    # 解析分钟
    if 'M' in duration_str:
        m_idx = duration_str.index('M')
        minutes = int(duration_str[:m_idx])
        duration_str = duration_str[m_idx+1:]

    # 解析秒
    if 'S' in duration_str:
        s_idx = duration_str.index('S')
        seconds = int(duration_str[:s_idx])

    return hours * 3600 + minutes * 60 + seconds


def extract_channel_videos_with_api(channel_url: str, api_key: str, limit: int = None) -> Dict[str, List[Dict]]:
    """
    使用 YouTube Data API 提取频道视频

    Args:
        channel_url: YouTube 频道链接
        api_key: YouTube Data API Key
        limit: 限制数量

    Returns:
        dict: {channel_name, videos}
    """
    result = {
        'channel_name': 'YouTube_Channel',
        'videos': []
    }

    link_type = detect_channel_type(channel_url)

    # 获取频道 ID
    channel_id = extract_channel_id_from_url(channel_url)

    # 如果是 @username 格式，需要先获取频道 ID
    if not channel_id:
        if link_type == 'channel':
            # 从 URL 提取 handle
            if '/@' in channel_url:
                handle = channel_url.split('/@')[-1].split('/')[0]
            elif '/c/' in channel_url:
                handle = channel_url.split('/c/')[-1].split('/')[0]
            else:
                print("   ⚠️  无法识别频道格式")
                return result

            print(f"   📡 获取频道 ID: @{handle}")
            channel_id = get_channel_id_by_handle(api_key, handle)

            if not channel_id:
                print("   ❌ 无法获取频道 ID")
                return result

    # 获取频道名称
    try:
        params = {
            'key': api_key,
            'part': 'snippet',
            'id': channel_id
        }
        response = requests.get(f"{YOUTUBE_API_URL}/channels", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('items'):
            result['channel_name'] = sanitize_filename(data['items'][0]['snippet']['title'])

    except Exception as e:
        print(f"   ⚠️  获取频道信息失败: {e}")

    # 获取视频列表
    videos = get_channel_videos_by_api(api_key, channel_id, limit)
    result['videos'] = videos

    print(f"   ✅ 成功提取 {len(videos)} 个视频")

    return result


def extract_channel_videos_ytdlp(channel_url: str, limit: int = None) -> Dict[str, List[Dict]]:
    """
    使用 yt-dlp 提取频道视频（备用方案）

    Args:
        channel_url: YouTube 频道链接
        limit: 限制数量

    Returns:
        dict: {channel_name, videos}
    """
    result = {
        'channel_name': 'YouTube_Channel',
        'videos': []
    }

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_search',
        'playlistend': limit,
    }

    print(f"   📡 使用 yt-dlp 获取视频列表...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            if info:
                if info.get('title'):
                    result['channel_name'] = sanitize_filename(info['title'])
                elif info.get('channel'):
                    result['channel_name'] = sanitize_filename(info['channel'])
                elif info.get('uploader'):
                    result['channel_name'] = sanitize_filename(info['uploader'])

                entries = []
                if 'entries' in info:
                    entries = info['entries']
                elif detect_channel_type(channel_url) == 'video':
                    entries = [info]

                for entry in entries:
                    if entry is None:
                        continue

                    video_url = entry.get('url')
                    if not video_url and entry.get('id'):
                        video_url = f"https://www.youtube.com/watch?v={entry['id']}"

                    if video_url:
                        result['videos'].append({
                            'url': video_url,
                            'title': entry.get('title', 'Untitled'),
                            'id': entry.get('id', ''),
                            'duration': entry.get('duration', 0)
                        })

    except Exception as e:
        print(f"   ❌ 获取视频列表失败: {e}")

    print(f"   ✅ 成功提取 {len(result['videos'])} 个视频")
    return result


def save_temp_csv(videos: List[Dict], channel_name: str, output_dir: str) -> str:
    """保存视频列表到临时 CSV 文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = output_path / f"{channel_name}_{timestamp}.csv"

    print(f"   📄 正在保存 CSV 文件...")

    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['序号', '标题', '链接', '时长'])

        for i, video in enumerate(videos, 1):
            duration_str = f"{video['duration']}秒" if video.get('duration') else ''
            writer.writerow([
                i,
                video['title'],
                video['url'],
                duration_str
            ])

    print(f"   ✅ CSV 文件已保存: {csv_file.name}")
    return str(csv_file)


def download_videos(csv_file: str, output_dir: str) -> tuple:
    """
    调用 download_videos_from_csv.py 进行批量下载

    Returns:
        (成功数量, 失败数量, 跳过数量)
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))

        from download_videos_from_csv import parse_csv, batch_download, get_author_name_from_csv

        print(f"   📖 正在解析 CSV 文件...")
        videos = parse_csv(csv_file)
        if not videos:
            print("   ❌ 没有找到视频")
            return (0, 0, 0)

        print(f"   📥 开始批量下载 {len(videos)} 个视频...")
        results = batch_download(videos, get_author_name_from_csv(csv_file), output_dir)

        success = sum(1 for r in results if r['success'] and 'skip_reason' not in r)
        skipped = sum(1 for r in results if r['success'] and 'skip_reason' in r)
        failed = sum(1 for r in results if not r['success'])

        return (success, failed, skipped)

    except Exception as e:
        print(f"   ❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return (0, 1, 0)


def transcribe_videos(
    video_dir: str,
    output_dir: str = "gemini_analysis",
    mode: str = "knowledge",
    model: str = "flash-lite"
) -> tuple:
    """
    调用 video_understand_gemini.py 进行批量转录

    Returns:
        (成功数量, 失败数量)
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))

        from video_understand_gemini import (
            VideoProcessor, get_prompt, batch_analyze, load_completed_videos
        )
        from pathlib import Path

        video_path = Path(video_dir)

        if not video_path.exists():
            print(f"   ❌ 视频目录不存在: {video_dir}")
            return (0, 0)

        videos = list(video_path.glob("*.mp4")) + list(video_path.glob("*.mov")) + \
                list(video_path.glob("*.avi")) + list(video_path.glob("*.mkv"))
        videos = list(set(videos))

        if not videos:
            print(f"   ⚠️  没有找到视频文件")
            return (0, 0)

        completed = load_completed_videos(output_dir)
        pending = [v for v in videos if v.stem not in completed]

        print(f"   📹 找到 {len(videos)} 个视频文件")
        print(f"   ⏭️  跳过已完成的: {len(videos) - len(pending)} 个")
        print(f"   📝 待处理: {len(pending)} 个")

        if not pending:
            print(f"   ✅ 所有视频都已处理完成!")
            return (len(videos), 0)

        print(f"   🔧 初始化 Gemini 模型: {model}...")
        processor = VideoProcessor(model=model)

        prompt = get_prompt(mode)

        batch_analyze(
            video_dir=video_dir,
            processor=processor,
            prompt=prompt,
            output_dir=output_dir,
            skip_completed=True
        )

        return (len(pending), 0)

    except Exception as e:
        print(f"   ❌ 转录失败: {e}")
        import traceback
        traceback.print_exc()
        return (0, 1)


def show_video_list(videos: List[Dict], show_count: int = 20):
    """显示视频列表"""
    print("\n" + "=" * 80)
    print("📋 视频列表预览")
    print("=" * 80)

    display_count = min(show_count, len(videos))
    for i, video in enumerate(videos[:display_count], 1):
        duration = video.get('duration', 0)
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "--:--"
        print(f"{i:3}. [{duration_str}] {video['title'][:55]}...")

    if len(videos) > show_count:
        print(f"\n   ... 还有 {len(videos) - show_count} 个视频未显示")

    print("=" * 80)


def print_summary(results: Dict[str, int], start_time: float):
    """打印执行摘要"""
    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("📊 执行摘要")
    print("=" * 80)

    if results.get('extracted'):
        print(f"   📡 提取视频: {results['extracted']} 个")

    if results.get('downloaded') is not None:
        print(f"   📥 下载视频: {results['downloaded']} 个成功 | {results.get('failed_dl', 0)} 个失败 | {results.get('skipped', 0)} 个跳过")

    if results.get('transcribed') is not None:
        print(f"   📝 转录视频: {results['transcribed']} 个成功 | {results.get('failed_trans', 0)} 个失败")

    print(f"   ⏱️  总耗时: {elapsed:.1f} 秒")
    print("=" * 80)


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="YouTube 频道视频批量下载与转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 使用 YouTube API（推荐，稳定）:
   python youtube_channel_downloader.py --channel "https://www.youtube.com/@username" --api-key YOUR_API_KEY

2. 不使用 API:
   python youtube_channel_downloader.py --channel "https://www.youtube.com/@username"

3. 下载并转录:
   python youtube_channel_downloader.py --channel "https://www.youtube.com/@username" --transcribe

4. 限制数量:
   python youtube_channel_downloader.py --channel "https://www.youtube.com/@username" --limit 3

获取 YouTube API Key:
1. 访问 https://console.cloud.google.com/
2. 创建项目并启用 YouTube Data API v3
3. 创建 API Key（无需设置 OAuth）
4. 免费配额: 10,000 单位/天（获取视频列表约消耗 1-5 单位/频道）
        """
    )

    parser.add_argument('-c', '--channel', required=True, help='YouTube 频道/播放列表链接')
    parser.add_argument('-o', '--output', default='youtube_videos', help='输出目录（默认: youtube_videos）')
    parser.add_argument('-t', '--transcribe', action='store_true', help='下载后使用 Gemini 进行转录')
    parser.add_argument('--transcribe-dir', help='只转录已有视频，不下载（指定视频目录）')
    parser.add_argument('-m', '--mode', choices=['summary', 'brief', 'detailed', 'transcript', 'knowledge'],
                        default='knowledge', help='转录提示词模式（默认: knowledge）')
    parser.add_argument('--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--limit', type=int, help='限制下载数量')
    parser.add_argument('--no-download', action='store_true', help='不下载，只提取视频列表')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过确认直接开始')
    parser.add_argument('--api-key', help='YouTube Data API Key（推荐使用）')

    args = parser.parse_args()

    start_time = time.time()
    results = {}

    # 只转录模式
    if args.transcribe_dir:
        print(f"\n{'='*80}")
        print(f"📝 只转录模式")
        print(f"{'='*80}")
        print(f"视频目录: {args.transcribe_dir}")
        print(f"转录模式: {args.mode}")
        print(f"使用模型: {args.model}")

        if args.yes or input("\n是否开始转录? (y/n): ").strip().lower() == 'y':
            success, failed = transcribe_videos(args.transcribe_dir, args.output, args.mode, args.model)
            results['transcribed'] = success
            results['failed_trans'] = failed
            print_summary(results, start_time)
        return

    # 提取视频列表
    print(f"\n{'='*80}")
    print(f"🎬 YouTube 频道下载工具")
    print(f"{'='*80}")
    print(f"🔗 链接: {args.channel}")

    link_type = detect_channel_type(args.channel)
    type_names = {
        'channel': '频道',
        'playlist': '播放列表',
        'video': '单个视频',
        'unknown': '未知类型'
    }
    print(f"📋 类型: {type_names.get(link_type, '未知')}")

    # 提取视频
    api_key = args.api_key or DEFAULT_API_KEY
    if api_key:
        print(f"🔑 使用 API 模式")
        channel_info = extract_channel_videos_with_api(args.channel, api_key, args.limit)
    else:
        print(f"📡 使用 yt-dlp 模式（可能不稳定）")
        channel_info = extract_channel_videos_ytdlp(args.channel, args.limit)

    if not channel_info['videos']:
        print("❌ 未找到视频")
        return

    results['extracted'] = len(channel_info['videos'])
    channel_name = channel_info['channel_name']
    videos = channel_info['videos']

    print(f"📺 频道名称: {channel_name}")
    print(f"🔢 视频数量: {len(videos)}")

    total_duration = sum(v.get('duration', 0) for v in videos)
    hours = total_duration // 3600
    minutes = (total_duration % 3600) // 60
    print(f"⏱️  总时长: {hours}小时{minutes}分钟")

    show_video_list(videos)

    # 只提取模式
    if args.no_download:
        csv_file = save_temp_csv(videos, channel_name, args.output)
        print(f"\n✅ 视频列表已保存到: {csv_file}")
        print_summary(results, start_time)
        return

    # 确认下载
    if not args.yes:
        response = input("\n⚠️  是否开始下载? (y/n): ").strip().lower()
        if response != 'y':
            print("⏭️  已取消")
            return

    # 保存临时 CSV
    print(f"\n{'='*80}")
    print(f"📥 第1步: 准备下载")
    print(f"{'='*80}")
    csv_file = save_temp_csv(videos, channel_name, args.output)

    # 下载视频
    print(f"\n{'='*80}")
    print(f"📥 第2步: 下载视频")
    print(f"{'='*80}")
    print(f"   💡 提示: 如果遇到 403 错误，请设置代理或导出 cookies")
    print(f"   💡 代理: set HTTPS_PROXY=http://127.0.0.1:7890")
    print(f"   💡 Cookies: 导出为 cookies_youtube.txt")

    downloaded, failed_dl, skipped = download_videos(csv_file, args.output)
    results['downloaded'] = downloaded
    results['failed_dl'] = failed_dl
    results['skipped'] = skipped

    # 转录
    if args.transcribe:
        print(f"\n{'='*80}")
        print(f"📥 第3步: 转录视频")
        print(f"{'='*80}")
        print(f"   模式: {args.mode}")
        print(f"   模型: {args.model}")

        video_dir = Path(args.output) / channel_name

        if video_dir.exists():
            transcribed, failed_trans = transcribe_videos(str(video_dir), args.output, args.mode, args.model)
            results['transcribed'] = transcribed
            results['failed_trans'] = failed_trans
        else:
            print(f"   ⚠️  视频目录不存在: {video_dir}")
            results['transcribed'] = 0

    print_summary(results, start_time)
    print(f"\n✅ 全部完成!")


if __name__ == "__main__":
    main()
