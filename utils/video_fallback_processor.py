#!/usr/bin/env python3
"""
视频备选方案处理器 - 处理无字幕视频

当视频没有内置字幕时，使用以下流程作为备选方案：
1. 下载视频文件
2. 使用 Gemini 分析视频内容（复用 video_understand_gemini.py）
3. 生成结构化的学习笔记

使用示例:
    python video_fallback_processor.py --csv "bilibili_videos_output/作者名.csv"
"""

import os
import sys
import csv
import re
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径以导入其他模块
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# ==================== 配置 ====================
VIDEO_DOWNLOAD_DIR = SCRIPT_DIR / "downloaded_videos"
SUBTITLE_OUTPUT_DIR = SCRIPT_DIR / "MediaCrawler" / "bilibili_subtitles"

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


def get_bili_cookie() -> str:
    """获取 B站 Cookie"""
    # 优先从环境变量读取
    cookie = os.environ.get('BILIBILI_COOKIE', '').strip()
    if cookie:
        return cookie

    # 从配置文件读取
    cookie_files = [
        SCRIPT_DIR / "config" / "cookies.txt",
        SCRIPT_DIR / "config" / "cookies_bilibili_api.txt",
        SCRIPT_DIR / "cookies_bilibili.txt",
    ]

    for cookie_file in cookie_files:
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception:
                continue

    return None


# ==================== 视频下载（复用现有代码）====================

def download_single_video(url: str, title: str, output_dir: Path, show_progress: bool = True,
                          quality: str = 'best') -> Optional[Path]:
    """
    下载单个视频文件（从 download_videos_from_csv.py 复用）

    Args:
        url: 视频URL
        title: 视频标题
        output_dir: 输出目录
        show_progress: 是否显示进度
        quality: 视频质量选项
            - 'best': 最高质量（默认）
            - '1080p': 1080p
            - '720p': 720p
            - '480p': 480p
            - '360p': 360p
            - 'audio_only': 仅音频（最快，最小）

    Returns:
        下载的视频文件路径，失败返回 None
    """
    import yt_dlp

    safe_title = sanitize_filename(title)
    output_file = output_dir / f"{safe_title}.mp4"

    # 检查是否已存在
    if output_file.exists():
        if show_progress:
            file_size = output_file.stat().st_size / 1024 / 1024
            print(f"   └─ ⏭️  视频已存在 ({file_size:.1f}MB)")
        return output_file

    if show_progress:
        quality_label = {
            'best': '最高质量',
            '1080p': '1080p',
            '720p': '720p',
            '480p': '480p',
            '360p': '360p',
            'audio_only': '仅音频'
        }.get(quality, quality)
        print(f"   └─ 📥 开始下载视频 (质量: {quality_label})...")

    try:
        # 根据质量设置格式选择器
        format_selectors = {
            'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
            '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best',
            'audio_only': 'bestaudio[ext=m4a]/bestaudio/best'
        }

        video_format = format_selectors.get(quality, format_selectors['best'])

        # 基础配置
        ydl_opts = {
            'format': video_format,
            'outtmpl': str(output_dir / f"{safe_title}.%(ext)s"),
            'quiet': not show_progress,
            'no_warnings': True,
            'concurrentfragments': 4,
        }

        # B站特殊处理
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
        }

        # 添加 Cookie
        bili_cookie = get_bili_cookie()
        if bili_cookie:
            headers['Cookie'] = bili_cookie
            if show_progress:
                print(f"   └─ 🍪 使用 Cookie 认证")
        else:
            if show_progress:
                print(f"   └─ ⚠️  未找到 Cookie，可能无法下载高清视频")

        ydl_opts['http_headers'] = headers

        start_time = time.time()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        elapsed = time.time() - start_time

        # 查找下载的文件
        if output_file.exists():
            if show_progress:
                file_size = output_file.stat().st_size / 1024 / 1024
                print(f"   └─ ✅ 下载完成! {elapsed:.1f}秒 | {file_size:.1f}MB")
            return output_file
        else:
            # 尝试查找任何新文件
            files = list(output_dir.glob(f"{safe_title}.*"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                if time.time() - latest.stat().st_mtime < 300:
                    if show_progress:
                        print(f"   └─ ✅ 下载完成! {elapsed:.1f}秒")
                    return latest

        if show_progress:
            print(f"   └─ ❌ 下载失败: 未找到文件")
        return None

    except Exception as e:
        if show_progress:
            print(f"   └─ ❌ 下载失败: {str(e)[:60]}")
        return None


# ==================== Gemini 视频分析（使用已有的 VideoProcessor）====================

def analyze_video_with_existing_processor(video_path: Path, title: str, model: str = 'flash-lite') -> Optional[Dict]:
    """
    使用已有的 VideoProcessor 分析视频

    Args:
        video_path: 视频文件路径
        title: 视频标题
        model: Gemini 模型

    Returns:
        分析结果字典
    """
    try:
        # 导入已有的 VideoProcessor
        from analysis.video_analyzer import VideoProcessor, get_prompt

        if show_progress := True:
            print(f"   └─ 🤖 Gemini 分析中...")

        # 创建处理器
        processor = VideoProcessor(model=model)

        # 上传视频
        video_file = processor.upload_video(str(video_path))
        if not video_file:
            return None

        # 等待处理完成
        if not processor.wait_for_processing(video_file):
            processor.delete_file(video_file)
            return None

        # 使用 knowledge 模式进行分析（生成知识库型笔记）
        prompt = get_prompt('knowledge')
        result_text, token_info = processor.analyze_video(video_file, prompt)

        # 删除上传的文件
        processor.delete_file(video_file)

        if result_text and not result_text.startswith("❌"):
            if show_progress:
                print(f"   └─ ✅ 分析完成!")
                if token_info.get('total_tokens', 0) > 0:
                    print(f"   └─ 📊 Token 使用: {token_info.get('total_tokens', 0):,}")

            return {
                'content': result_text,
                'token_info': token_info,
                'model': model
            }
        else:
            return None

    except Exception as e:
        print(f"   └─ ❌ Gemini 分析失败: {str(e)[:60]}")
        return None


# ==================== 生成 Markdown 文件（使用已有函数）====================

def save_analysis_to_subtitle_dir(title: str, video_path: Path, analysis: Dict, output_dir: Path,
                                   video_data: Dict = None, author_name: str = None) -> Path:
    """
    保存分析结果到字幕目录（与 SRT 文件放在一起）

    Args:
        title: 视频标题
        video_path: 视频文件路径
        analysis: Gemini 分析结果
        output_dir: 输出目录（字幕目录）
        video_data: 视频数据字典（来自CSV，包含链接、BV号等信息）
        author_name: UP主名称

    Returns:
        保存的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(title)
    output_file = output_dir / f"{safe_title}_视频分析.md"

    # 使用已有的 save_result 函数格式
    with open(output_file, 'w', encoding='utf-8') as f:
        # Markdown 头部
        f.write(f"# {title} - Gemini 视频分析\n\n")

        # 元信息表格
        f.write(f"## 📌 元信息\n\n")
        f.write(f"| 项目 | 内容 |\n")
        f.write(f"|------|------|\n")

        # 视频链接和基本信息
        if video_data:
            url = video_data.get('链接', '')
            bvid = video_data.get('BV号', '')
            views = video_data.get('播放量', '')
            pub_time = video_data.get('发布时间', '')

            if url:
                f.write(f"| **视频链接** | {url} |\n")
            if bvid:
                f.write(f"| **BV 号** | {bvid} |\n")
            if author_name:
                f.write(f"| **UP 主** | {author_name} |\n")
            if views:
                f.write(f"| **播放量** | {views} |\n")
            if pub_time:
                f.write(f"| **发布时间** | {pub_time} |\n")

        f.write(f"| **视频文件** | {video_path.name} |\n")
        f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write(f"| **使用模型** | {analysis.get('model', 'gemini')} |\n")
        f.write(f"| **分析方式** | Gemini 视频分析（无字幕备选方案） |\n")

        # Token 使用信息
        token_info = analysis.get('token_info', {})
        if token_info.get('total_tokens', 0) > 0:
            f.write(f"| **Token 使用** | 输入: {token_info.get('prompt_tokens', 0):,} | 输出: {token_info.get('candidates_tokens', 0):,} | **总计: {token_info.get('total_tokens', 0):,}** |\n")

        f.write(f"\n---\n\n")

        # 分析结果
        f.write(analysis['content'])
        f.write(f"\n")

    print(f"   └─ 📄 分析已保存: {output_file.name}")
    return output_file


# ==================== 主处理逻辑 ====================

def process_single_video(video_data: Dict, download_dir: Path, output_dir: Path,
                          model: str = 'flash-lite', author_name: str = None,
                          quality: str = 'best') -> Dict:
    """
    处理单个视频的备选方案

    Args:
        video_data: 视频数据字典（来自CSV）
        download_dir: 视频下载目录
        output_dir: 分析结果输出目录
        model: Gemini 模型
        author_name: UP主名称
        quality: 视频质量选项

    Returns:
        处理结果字典
    """
    url = video_data.get('链接', '')
    title = video_data.get('标题', '')
    bvid = video_data.get('BV号', '')

    result = {
        'success': False,
        'video_path': None,
        'analysis_path': None,
        'error': None
    }

    print(f"\n📹 处理: {title[:50]}...")
    print(f"   URL: {url[:60]}...")

    try:
        # 步骤1: 下载视频
        video_path = download_single_video(url, title, download_dir, quality=quality)
        if not video_path:
            result['error'] = '视频下载失败'
            return result

        result['video_path'] = str(video_path)

        # 步骤2: Gemini 分析（使用已有的 VideoProcessor）
        analysis = analyze_video_with_existing_processor(video_path, title, model)
        if not analysis:
            result['error'] = 'Gemini 分析失败'
            return result

        # 步骤3: 保存到字幕目录
        analysis_md_path = save_analysis_to_subtitle_dir(title, video_path, analysis, output_dir,
                                                         video_data=video_data, author_name=author_name)
        result['analysis_path'] = str(analysis_md_path)

        result['success'] = True
        print(f"   ✅ 处理完成!")

    except Exception as e:
        result['error'] = str(e)[:100]
        print(f"   ❌ 处理失败: {result['error']}")

    return result


def process_fallback_videos(csv_path: str, model: str = 'flash-lite', limit: int = None,
                            quality: str = 'best') -> Dict:
    """
    处理 CSV 中所有需要备选方案的视频

    Args:
        csv_path: CSV 文件路径
        model: Gemini 模型
        limit: 限制处理数量（用于测试）
        quality: 视频质量选项

    Returns:
        处理统计结果
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        return {'success': 0, 'failed': 0, 'total': 0}

    # 提取作者名
    author_name = csv_file.stem
    print(f"\n{'='*70}")
    print(f"🎬 视频备选方案处理器")
    print(f"{'='*70}")
    print(f"作者: {author_name}")
    print(f"CSV: {csv_file.name}")

    # 读取 CSV
    videos = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            videos.append(row)

    # 筛选需要备选方案的视频
    fallback_videos = [v for v in videos if v.get('fallback_needed', False) or v.get('fallback_status') == 'pending']

    if not fallback_videos:
        print(f"\n✅ 没有需要处理的视频")
        return {'success': 0, 'failed': 0, 'total': 0}

    # 应用限制
    if limit and limit < len(fallback_videos):
        fallback_videos = fallback_videos[:limit]
        print(f"\n⚠️  限制处理数量: {limit}")

    print(f"\n找到 {len(fallback_videos)} 个需要处理的无字幕视频")

    # 创建目录
    download_dir = VIDEO_DOWNLOAD_DIR / author_name
    download_dir.mkdir(parents=True, exist_ok=True)

    output_dir = SUBTITLE_OUTPUT_DIR / author_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 处理每个视频
    success_count = 0
    failed_count = 0
    total_start = time.time()

    for i, video_data in enumerate(fallback_videos, 1):
        print(f"\n[{i}/{len(fallback_videos)}]", end=" ")

        # 标记为处理中
        video_data['fallback_status'] = 'processing'

        # 处理视频
        result = process_single_video(video_data, download_dir, output_dir, model,
                                      author_name=author_name, quality=quality)

        # 更新状态
        if result['success']:
            video_data['fallback_status'] = 'completed'
            video_data['video_file_path'] = result['video_path']
            video_data['analysis_file_path'] = result['analysis_path']
            success_count += 1
        else:
            video_data['fallback_status'] = 'failed'
            video_data['fallback_error'] = result['error']
            failed_count += 1

        # 每处理一个视频就保存进度
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = list(videos[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(videos)

    total_elapsed = time.time() - total_start

    # 打印统计
    print(f"\n{'='*70}")
    print(f"📊 处理完成")
    print(f"{'='*70}")
    print(f"总计: {len(fallback_videos)}")
    print(f"成功: {success_count}")
    print(f"失败: {failed_count}")
    print(f"总耗时: {total_elapsed:.1f}秒")
    if success_count > 0:
        print(f"平均每个: {total_elapsed/success_count:.1f}秒")
    print(f"{'='*70}")

    return {
        'success': success_count,
        'failed': failed_count,
        'total': len(fallback_videos)
    }


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="视频备选方案处理器 - 处理无字幕视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python video_fallback_processor.py --csv "bilibili_videos_output/作者名.csv"
  python video_fallback_processor.py --csv "bilibili_videos_output/作者名.csv" --model flash
  python video_fallback_processor.py --csv "bilibili_videos_output/作者名.csv" --limit 3
  python video_fallback_processor.py --csv "bilibili_videos_output/作者名.csv" --quality 720p
        """
    )

    parser.add_argument('--csv', '-c', required=True, help='CSV 文件路径')
    parser.add_argument('--model', '-m', choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--limit', '-l', type=int, help='限制处理数量（测试用）')
    parser.add_argument('--quality', '-q', choices=['best', '1080p', '720p', '480p', '360p', 'audio_only'],
                       default='best', help='视频质量（默认: best）')

    args = parser.parse_args()

    # 处理视频
    result = process_fallback_videos(args.csv, args.model, args.limit, args.quality)

    if result['total'] == 0:
        return 0
    elif result['success'] > 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
