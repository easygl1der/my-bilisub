#!/usr/bin/env python3
"""
视频下载测试工具

简单的视频下载测试脚本，支持 B站、小红书、YouTube

使用示例:
    # 测试 B站视频
    python test_video_download.py -u "https://www.bilibili.com/video/BV1UPZtBiEFS"

    # 测试小红书视频
    python test_video_download.py -u "https://www.xiaohongshu.com/explore/xxxxx"

    # 测试 YouTube 视频
    python test_video_download.py -u "https://www.youtube.com/watch?v=xxxxx"

    # 只检查不下载
    python test_video_download.py -u "VIDEO_URL" --info-only
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path
from typing import Optional

import yt_dlp

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 配置 ====================
OUTPUT_DIR = Path("downloaded_videos")
BILI_COOKIE_FILE = "config/cookies.txt"
# ============================================


class ProgressHook:
    """下载进度钩子"""
    def __init__(self):
        self.start_time = time.time()

    def __call__(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)

            if total > 0:
                percent = downloaded / total * 100
                downloaded_mb = downloaded / 1024 / 1024
                total_mb = total / 1024 / 1024

                speed_str = f"{speed / 1024 / 1024:.1f}MB/s" if speed > 0 else "--"
                eta_str = f"{eta}s" if eta > 0 else "--"

                print(f"\r   进度: {percent:.1f}% | {downloaded_mb:.1f}/{total_mb:.1f}MB | {speed_str} | ETA: {eta_str}", end='')

        elif d['status'] == 'finished':
            elapsed = time.time() - self.start_time
            print(f"\n   下载完成! 耗时: {elapsed:.1f}秒")


def detect_platform(url: str) -> str:
    """检测视频平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    return 'unknown'


def extract_xhs_note_url(url: str) -> Optional[str]:
    """
    从小红书链接中提取实际的笔记链接

    如果是用户主页链接，返回第一个笔记链接
    如果是笔记链接，直接返回
    """
    import re

    # 检查是否是笔记链接（包含 explore 或直接笔记ID）
    if '/explore/' in url or ('user/profile' in url and re.search(r'/\d{19,20}\?xsec_token', url)):
        # 这是笔记链接，直接返回
        return url

    # 如果是纯用户主页（不包含笔记ID）
    if '/user/profile/' in url and 'xsec_token' not in url:
        print("❌ 需要完整的用户主页链接（包含 xsec_token）")
        return None

    # 如果是用户主页 + 笔记ID 的格式，但可能不是视频笔记
    return url


def get_bili_cookie() -> str:
    """获取 B站 Cookie"""
    if os.environ.get('BILIBILI_COOKIE'):
        return os.environ['BILIBILI_COOKIE']

    cookie_file = Path(BILI_COOKIE_FILE)
    if cookie_file.exists():
        with open(cookie_file, 'r', encoding='utf-8') as f:
            return f.read().strip()

    return None


def get_video_info(url: str) -> dict:
    """获取视频信息（不下载）"""
    platform = detect_platform(url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }

    # 添加平台特定配置
    if platform == 'bilibili':
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/',
        }
        cookie = get_bili_cookie()
        if cookie:
            headers['Cookie'] = cookie
        ydl_opts['http_headers'] = headers

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return info


def download_video(url: str, output_dir: Path = OUTPUT_DIR) -> bool:
    """下载视频"""
    platform = detect_platform(url)

    # 根据平台创建对应的子目录
    platform_subdir = {
        'bilibili': 'bilibili',
        'xiaohongshu': 'xhs',
        'youtube': 'youtube'
    }.get(platform, '')

    if platform_subdir:
        actual_output_dir = output_dir / platform_subdir
    else:
        actual_output_dir = output_dir

    actual_output_dir.mkdir(parents=True, exist_ok=True)

    # 先获取信息
    print("📡 获取视频信息...")
    try:
        info = get_video_info(url)
        title = info.get('title', 'unknown')
        duration = info.get('duration', 0)
        uploader = info.get('uploader') or info.get('channel', 'unknown')

        print(f"   标题: {title[:60]}...")
        if duration is not None and isinstance(duration, (int, float)):
            print(f"   时长: {duration // 60}分{duration % 60}秒")
        else:
            print("   时长: 未知")

        # 对于 B 站，在平台子目录下按 UP 主分类
        if platform == 'bilibili' and uploader:
            safe_uploader = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in uploader)[:50]
            print(f"   UP主: {uploader}")

            # 在平台子目录下创建 UP 主子目录
            uploader_dir = actual_output_dir / safe_uploader
            uploader_dir.mkdir(parents=True, exist_ok=True)

            # 下载到 UP 主子目录
            final_output_dir = uploader_dir
        else:
            final_output_dir = actual_output_dir

    except Exception as e:
        print(f"   获取信息失败: {e}")
        title = f"video_{int(time.time())}"
        final_output_dir = actual_output_dir

    # 清理文件名
    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)[:100]

    # 配置下载选项
    progress_hook = ProgressHook()
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': str(final_output_dir / f"{safe_title}.%(ext)s"),
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progress_hook],
        'concurrentfragments': 4,
    }

    # 平台特定配置
    if platform == 'xiaohongshu':
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
        }

    elif platform == 'bilibili':
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/',
        }
        cookie = get_bili_cookie()
        if cookie:
            headers['Cookie'] = cookie
            print(f"   使用 Cookie: config/cookies.txt")
        ydl_opts['http_headers'] = headers

    elif platform == 'youtube':
        ydl_opts.update({
            'format': 'bestvideo+bestaudio/best',
            'nocheckcertificate': True,
        })

    # 下载
    print("📥 开始下载...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        # 查找下载的文件
        files = list(final_output_dir.glob(f"{safe_title}.*"))
        if files:
            downloaded = max(files, key=lambda f: f.stat().st_mtime)
            size_mb = downloaded.stat().st_size / 1024 / 1024
            print(f"\n✅ 下载成功!")
            print(f"   文件: {downloaded.name}")
            print(f"   大小: {size_mb:.1f}MB")
            print(f"   路径: {downloaded}")
            return True
        else:
            print("\n❌ 下载失败: 文件未找到")
            return False

    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="视频下载测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_video_download.py -u "https://www.bilibili.com/video/BV1UPZtBiEFS"
  python test_video_download.py -u "URL" --info-only
        """
    )

    parser.add_argument('-u', '--url', required=True, help='视频链接')
    parser.add_argument('-o', '--output', default=str(OUTPUT_DIR), help='输出目录')
    parser.add_argument('--info-only', action='store_true', help='只获取视频信息，不下载')

    args = parser.parse_args()

    print("=" * 70)
    print("🎬 视频下载测试工具")
    print("=" * 70)

    url = args.url
    platform = detect_platform(url)

    print(f"平台: {platform.upper()}")
    print(f"链接: {url[:60]}...")

    if args.info_only:
        print("\n📡 获取视频信息...")
        try:
            info = get_video_info(url)
            print("\n视频信息:")
            print(f"  标题: {info.get('title', 'unknown')}")
            print(f"  时长: {info.get('duration', 'unknown')} 秒")
            print(f"  作者: {info.get('uploader', 'unknown')}")
            print(f"  观看: {info.get('view_count', 'unknown')}")
            if 'formats' in info:
                print(f"  可用格式: {len(info['formats'])} 种")
        except Exception as e:
            print(f"❌ 获取失败: {e}")
        return

    output_dir = Path(args.output)
    success = download_video(url, output_dir)

    print("=" * 70)
    if success:
        print("✅ 测试完成")
    else:
        print("❌ 测试失败")
    print("=" * 70)


if __name__ == "__main__":
    main()
