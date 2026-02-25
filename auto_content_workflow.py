#!/usr/bin/env python3
"""
自动内容处理工作流

根据输入 URL 自动识别平台和内容类型，并调用相应的处理工具：

支持的平台：
- Bilibili: 视频下载 / 字幕分析 / AI 摘要 / 评论爬取
- 小红书: 图文分析 / 视频下载 / 评论爬取
- YouTube: 视频下载

基本用法:
    python auto_content_workflow.py "URL"

B站用法:
    # 下载视频（默认）
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS"

    # 提取字幕 + AI 分析
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --bili-mode subtitle

    # 下载视频 + 生成学习笔记
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --generate-notes

    # 爬取评论（默认前50条最热评论）
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --fetch-comments

    # 爬取前20条最热评论
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --fetch-comments -c 20

    # 组合使用
    python auto_content_workflow.py "B站URL" --bili-mode subtitle --fetch-comments

小红书用法:
    # 自动识别图文/视频（图文默认上传 GitHub）
    python auto_content_workflow.py "https://www.xiaohongshu.com/explore/699dc1eb0000000026033531?xsec_token=AB2DFzRej3IQKdq3P0GZ9PybEPNU2qAmBRWFmt6Bd0wjs=&xsec_source=pc_feed"

    python auto_content_workflow.py "https://www.xiaohongshu.com/explore/699e557e000000001d024d0e?xsec_token=ABavXPUj3ZYaRIn8_xSrh7u7fO9X9SCztwYXgiUOHWQZo=&xsec_source="

    # 指定内容类型
    python auto_content_workflow.py "XHS_URL" -t image  # 图文
    python auto_content_workflow.py "XHS_URL" -t video  # 视频

    # 指定 AI 模型（仅图文分析）
    python auto_content_workflow.py "XHS_URL" -m flash

    # 爬取评论（无头模式）
    python auto_content_workflow.py "https://www.xiaohongshu.com/explore/699e557e000000001d024d0e?xsec_token=ABavXPUj3ZYaRIn8_xSrh7u7fO9X9SCztwYXgiUOHWQZo=&xsec_source=" --fetch-comments --headless

YouTube用法:
    # 下载视频
    python auto_content_workflow.py "https://www.youtube.com/watch?v=xxx"

    # 下载 + 生成学习笔记
    python auto_content_workflow.py "YouTubeURL" --generate-notes

参数说明:
    -t, --type          内容类型：video/image/auto（默认：auto）
    -m, --model         Gemini 模型：flash/flash-lite/pro（默认：flash-lite）
    -o, --output        输出目录
    --info-only          只获取信息不下载（仅视频下载）
    --upload-github       上传图片到 GitHub CDN（仅图文分析和学习笔记）
    --fetch-comments      爬取评论（B站默认前50条最热评论）
    --headless          评论爬取使用无头模式（不显示浏览器窗口，仅小红书）
    -c, --comment-count 评论数量（仅 B站，0=全部最热，默认50）
    --bili-mode          B站模式：video/subtitle（默认：video）
    --generate-notes      生成学习笔记（关键帧 + AI 分析）
    --keyframes         关键帧数量（学习笔记生成，默认：自动计算）
    --no-gemini         学习笔记生成时禁用 Gemini 智能检测，使用均匀采样
"""

import os
import sys
import subprocess
import argparse
import re
import requests
from pathlib import Path

# 添加项目根目录到Python路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 路径配置 ====================

VIDEO_DOWNLOAD_SCRIPT = SCRIPT_DIR / "tools" / "test_video_download.py"
XHS_IMAGE_WORKFLOW = SCRIPT_DIR / "workflows" / "auto_xhs_image_workflow.py"
XHS_COMMENT_SCRIPT = SCRIPT_DIR / "platforms" / "xiaohongshu" / "fetch_xhs_comments.py"
BILI_COMMENT_SCRIPT = SCRIPT_DIR / "platforms" / "bilibili" / "fetch_bili_comments.py"
BILI_SUBTITLE_WORKFLOW = SCRIPT_DIR / "workflows" / "auto_bili_workflow.py"
VIDEO_TO_NOTES_SCRIPT = SCRIPT_DIR / "workflows" / "video_to_notes.py"
# ================================================


def detect_platform(url: str) -> str:
    """检测内容平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    return 'unknown'


def generate_video_notes(video_path: Path, model: str = 'flash-lite',
                       keyframes: int = None, no_gemini: bool = False,
                       upload_github: bool = False) -> bool:
    """
    生成视频学习笔记

    Args:
        video_path: 视频文件路径
        model: Gemini 模型
        keyframes: 关键帧数量
        no_gemini: 是否禁用 Gemini 智能检测
        upload_github: 是否上传图片到 GitHub

    Returns:
        是否成功
    """
    print("\n" + "-"*80)
    print("📝 生成学习笔记")
    print("-"*80)

    if not VIDEO_TO_NOTES_SCRIPT.exists():
        print("❌ 找不到学习笔记生成脚本")
        return False

    cmd = [sys.executable, str(VIDEO_TO_NOTES_SCRIPT), '-f', str(video_path),
           '--gemini-model', model]

    if keyframes:
        cmd.extend(['--keyframes', str(keyframes)])

    if no_gemini:
        cmd.append('--no-gemini')

    # 如果不传图片，视频ToNotes 默认会检查 GitHub 配置
    # 如果 upload_github 为 False，视频ToNotes 内部会使用本地图片
    # 所以这里不需要额外参数

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode == 0


def is_xhs_video(url: str) -> bool:
    """
    检测小红书链接是否为视频笔记

    通过解析页面响应来判断（基于 tools/check_xhs_note.py 的逻辑）
    """
    print("🔍 正在检测小红书笔记类型...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)

        # 检查视频特征
        has_play_addr = '"playAddr":' in response.text or '"play_addr":' in response.text
        has_media_video = re.search(r'"media":\s*\{[^}]*"video":\s*\{', response.text)

        # 计算图片数量
        img_count = response.text.count('"urlDefault"')

        # 判断逻辑：
        # 1. 检测到明确的视频特征 → 视频
        # 2. 图片数量 >= 2 → 图文
        # 3. 默认认为是图文
        if has_play_addr or has_media_video:
            print("   ✅ 检测结果: 视频笔记")
            return True
        elif img_count >= 2:
            print("   ✅ 检测结果: 图文笔记")
            return False
        else:
            print("   ✅ 检测结果: 图文笔记（默认）")
            return False

    except Exception as e:
        print(f"   ⚠️ 自动检测失败，默认使用图文模式: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="自动内容处理工作流（智能识别平台和内容类型）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # B站视频（下载视频）
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS"

    # B站视频（字幕分析 + AI 摘要）
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --bili-mode subtitle

    # B站视频 + 生成学习笔记
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --generate-notes

    # B站视频 + 爬取评论
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS" --fetch-comments

    # 小红书（自动识别图文/视频，图文默认使用 GitHub 图床）
    python auto_content_workflow.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx"

    # 小红书 + 爬取评论
    python auto_content_workflow.py "XHS_URL" --fetch-comments

    # 小红书 + 指定 AI 模型（仅图文分析）
    python auto_content_workflow.py "XHS_URL" -m flash

    # 只获取信息不下载
    python auto_content_workflow.py "URL" --info-only
        """
    )

    parser.add_argument('url', help='内容链接')
    parser.add_argument('-t', '--type',
                       choices=['video', 'image', 'auto'],
                       default='auto',
                       help='内容类型：video=视频, image=图文, auto=自动（默认）')
    parser.add_argument('-m', '--model',
                       choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite',
                       help='Gemini 模型（仅图文分析、B站字幕分析、学习笔记生成，默认: flash-lite）')
    parser.add_argument('-o', '--output', help='输出目录（仅视频下载）')
    parser.add_argument('--info-only', action='store_true',
                       help='只获取信息，不下载（仅视频下载）')
    parser.add_argument('--upload-github', action='store_true',
                       help='上传图片到 GitHub CDN（仅图文分析和学习笔记）')
    parser.add_argument('--fetch-comments', action='store_true',
                       help='同时爬取评论（仅 B站和小红书）')
    parser.add_argument('--headless', action='store_true',
                       help='评论爬取使用无头模式（不显示浏览器窗口，仅小红书）')
    parser.add_argument('-c', '--comment-count', type=int, default=50,
                       help='评论数量（仅 B站，0 表示全部最热，默认 50）')
    parser.add_argument('--only-liked', action='store_true',
                       help='只爬取有点赞数的主评论（仅 B站，子评论全部保留）')
    parser.add_argument('--comments-only', action='store_true',
                       help='只爬取评论，不下载视频（仅 B站和小红书）')
    parser.add_argument('--bili-mode',
                       choices=['video', 'subtitle'],
                       default='video',
                       help='B站处理模式：video=下载视频, subtitle=字幕+AI分析（默认: video）')
    parser.add_argument('--generate-notes', action='store_true',
                       help='视频下载后生成学习笔记（关键帧 + AI 分析）')
    parser.add_argument('--keyframes', type=int, default=None,
                       help='提取关键帧数量（学习笔记生成，默认：自动计算）')
    parser.add_argument('--no-gemini', action='store_true',
                       help='学习笔记生成时禁用 Gemini 智能检测，使用均匀采样')

    args = parser.parse_args()

    url = args.url
    platform = detect_platform(url)

    print("\n" + "="*80)
    print("🚀 自动内容处理工作流")
    print("="*80)
    print(f"平台: {platform.upper()}")
    print(f"链接: {url[:60]}{'...' if len(url) > 60 else ''}")

    # 根据平台和类型决定处理流程
    if platform == 'bilibili':
        print("内容类型: 视频")

        # 检查是否只爬取评论模式
        if args.comments_only:
            print("⚡ 只爬取评论模式（跳过视频下载）")
            result = type('obj', (object,), {'returncode': 0})()  # 标记为成功
        elif args.bili_mode == 'subtitle':
            # B站字幕分析模式
            print("\n" + "-"*80)
            print("📝 提取字幕 + 🤖 AI 分析")
            print("-"*80)

            if BILI_SUBTITLE_WORKFLOW.exists():
                cmd = [sys.executable, str(BILI_SUBTITLE_WORKFLOW), '--video-url', url, '--model', args.model]
                result = subprocess.run(cmd, cwd=SCRIPT_DIR)
            else:
                print("❌ 找不到字幕分析脚本")
                result = type('obj', (object,), {'returncode': 1})()
        else:
            # B站视频下载模式
            print("\n" + "-"*80)
            print("📥 下载视频")
            print("-"*80)

            # 输出目录
            download_dir = Path(args.output) if args.output else Path("downloaded_videos/bilibili")
            video_file = None
            skip_download = False

            # 先获取视频信息，检查是否已下载
            try:
                import yt_dlp
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.bilibili.com/',
                }
                cookie_file = Path("config/cookies.txt")
                if cookie_file.exists():
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        headers['Cookie'] = f.read().strip()
                ydl_opts['http_headers'] = headers

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'unknown')
                    uploader = info.get('uploader') or info.get('channel', 'unknown')

                    # 清理文件名
                    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)[:100]
                    safe_uploader = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in uploader)[:50]

                    print(f"👤 UP主: {uploader}")
                    print(f"📺 标题: {title[:60]}...")

                    # 创建 UP 主子目录
                    uploader_dir = download_dir / safe_uploader

                    # 在 UP 主子目录中查找是否已存在同名文件
                    if uploader_dir.exists():
                        existing_files = list(uploader_dir.glob(f"{safe_title}.*"))
                        if existing_files:
                            video_file = max(existing_files, key=lambda f: f.stat().st_mtime)
                            size_mb = video_file.stat().st_size / 1024 / 1024
                            print(f"✅ 视频已存在，跳过下载")
                            print(f"   文件: {video_file.name}")
                            print(f"   大小: {size_mb:.1f}MB")
                            print(f"   路径: {video_file}")
                            skip_download = True
                            result = type('obj', (object,), {'returncode': 0})()
            except Exception as e:
                print(f"⚠️ 无法获取视频信息: {e}")
                print("   将直接下载视频...")
                skip_download = False

            if not skip_download:
                # 构建 test_video_download.py 的命令
                cmd = [sys.executable, str(VIDEO_DOWNLOAD_SCRIPT), '-u', url]

                if args.info_only:
                    cmd.append('--info-only')

                # 指定输出目录（使用 downloaded_videos）
                output_path = args.output if args.output else "downloaded_videos"
                cmd.extend(['-o', output_path])

                # 执行视频下载
                result = subprocess.run(cmd, cwd=SCRIPT_DIR)

                # 下载完成后，查找刚下载的视频文件
                if result.returncode == 0 and not args.info_only:
                    # 在 downloaded_videos 目录下查找最新的 mp4 文件
                    if download_dir.exists():
                        video_files = list(download_dir.rglob("*.mp4"))
                        if video_files:
                            video_file = max(video_files, key=lambda f: f.stat().st_mtime)
                            size_mb = video_file.stat().st_size / 1024 / 1024
                            print(f"\n📹 下载完成: {video_file.name}")
                            print(f"   大小: {size_mb:.1f}MB")
                            print(f"   路径: {video_file}")

        # 生成学习笔记
        if args.generate_notes and result.returncode == 0:
            # 使用已找到的视频文件（如果跳过了下载）或查找最新的视频文件
            if 'video_file' in locals() and video_file:
                video_path = video_file
            else:
                # 查找最近下载的视频文件
                output_path = Path(args.output) if args.output else Path("test_downloads")
                if output_path.exists():
                    video_files = list(output_path.glob("*.mp4"))
                    video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    if video_files:
                        video_path = video_files[0]
                    else:
                        video_path = None
                else:
                    video_path = None

            if video_path and video_path.exists():
                print("\n" + "-"*80)
                print("📝 生成学习笔记")
                print("-"*80)
                print(f"📹 视频文件: {video_path.name}")

                notes_result = generate_video_notes(
                    video_path, args.model, args.keyframes,
                    args.no_gemini, args.upload_github
                )
                if not notes_result:
                    print("⚠️ 学习笔记生成失败")
            else:
                print("⚠️ 未找到视频文件，无法生成学习笔记")

        # 爬取评论
        if args.fetch_comments and result.returncode == 0:
            print("\n" + "-"*80)
            print("💬 爬取评论")
            print("-"*80)

            # 显示爬取模式信息
            count_info = f"{args.comment_count}条最热评论" if args.comment_count != 0 else "全部收集的评论"
            filter_info = "（仅有点赞数）" if args.only_liked else ""
            print(f"🔥 模式：收集多页评论后按点赞排序，爬取 {count_info}{filter_info}")
            print("-"*80)

            if BILI_COMMENT_SCRIPT.exists():
                comment_cmd = [sys.executable, str(BILI_COMMENT_SCRIPT), url, str(args.comment_count)]
                if args.only_liked:
                    comment_cmd.append('--only-liked')
                comment_result = subprocess.run(comment_cmd, cwd=SCRIPT_DIR)
                if comment_result.returncode != 0:
                    print("⚠️ 评论爬取失败")
            else:
                print("❌ 找不到评论爬取脚本")

    elif platform == 'xiaohongshu':
        # 小红书内容类型判断
        content_type = args.type

        if content_type == 'auto':
            # 自动检测图文还是视频
            print("🔍 正在检测小红书笔记类型...")
            content_type = 'video' if is_xhs_video(url) else 'image'
        else:
            # 用户手动指定
            print(f"内容类型: {'视频' if content_type == 'video' else '图文'}（手动指定）")

        if content_type == 'video':
            # 小红书视频下载
            print("\n" + "-"*80)
            print("📥 下载视频")
            print("-"*80)

            # 检查视频是否已下载
            output_path = Path(args.output) if args.output else Path("downloaded_videos/xhs")
            video_file = None
            skip_download = False

            try:
                import yt_dlp
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'unknown')

                    # 清理文件名
                    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)[:100]

                    # 检查文件是否存在
                    if output_path.exists():
                        possible_files = list(output_path.glob(f"{safe_title}.*"))

                        if not possible_files:
                            # 模糊匹配
                            title_parts = [p for p in safe_title.replace('_', ' ').split() if len(p) > 2][:5]
                            for f in output_path.glob("*.mp4"):
                                f_name = f.stem.replace('_', ' ')
                                if all(part in f_name for part in title_parts[:3]):
                                    possible_files.append(f)
                                    break

                        if possible_files:
                            video_file = max(possible_files, key=lambda f: f.stat().st_mtime)
                            size_mb = video_file.stat().st_size / 1024 / 1024
                            print(f"✅ 视频已存在，跳过下载")
                            print(f"   文件: {video_file.name}")
                            print(f"   大小: {size_mb:.1f}MB")
                            print(f"   路径: {video_file}")
                            skip_download = True
                            result = type('obj', (object,), {'returncode': 0})()
            except Exception as e:
                print(f"⚠️ 无法检查视频是否已存在: {e}")
                print("   将直接下载视频...")
                skip_download = False

            if not skip_download:
                cmd = [sys.executable, str(VIDEO_DOWNLOAD_SCRIPT), '-u', url]

                if args.info_only:
                    cmd.append('--info-only')

                if args.output:
                    cmd.extend(['-o', args.output])

                # 执行视频下载
                result = subprocess.run(cmd, cwd=SCRIPT_DIR)

            # 生成学习笔记
            if args.generate_notes and result.returncode == 0:
                # 查找最近下载的视频文件
                output_path = Path(args.output) if args.output else Path("downloaded_videos/xhs")
                if output_path.exists():
                    video_files = list(output_path.glob("*.mp4"))
                    video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    if video_files:
                        video_path = video_files[0]
                        notes_result = generate_video_notes(
                            video_path, args.model, args.keyframes,
                            args.no_gemini, args.upload_github
                        )
                        if not notes_result:
                            print("⚠️ 学习笔记生成失败")

            # 爬取评论
            if args.fetch_comments and result.returncode == 0:
                print("\n" + "-"*80)
                print("💬 爬取评论")
                print("-"*80)

                if XHS_COMMENT_SCRIPT.exists():
                    comment_cmd = [sys.executable, str(XHS_COMMENT_SCRIPT), url]
                    if args.headless:
                        comment_cmd.append('--headless')
                    comment_result = subprocess.run(comment_cmd, cwd=SCRIPT_DIR)
                    if comment_result.returncode != 0:
                        print("⚠️ 评论爬取失败")
                else:
                    print("❌ 找不到评论爬取脚本")

        else:
            # 小红书图文分析（默认使用 GitHub 图床）
            print("\n" + "-"*80)
            print("📸 下载图片 + 🤖 AI 分析")
            print("-"*80)

            cmd = [sys.executable, str(XHS_IMAGE_WORKFLOW), url, '--model', args.model]

            # 默认上传到 GitHub 图床
            cmd.append('--upload-github')

            # 执行图文分析
            result = subprocess.run(cmd, cwd=SCRIPT_DIR)

            # 爬取评论
            if args.fetch_comments and result.returncode == 0:
                print("\n" + "-"*80)
                print("💬 爬取评论")
                print("-"*80)

                if XHS_COMMENT_SCRIPT.exists():
                    comment_cmd = [sys.executable, str(XHS_COMMENT_SCRIPT), url]
                    if args.headless:
                        comment_cmd.append('--headless')
                    comment_result = subprocess.run(comment_cmd, cwd=SCRIPT_DIR)
                    if comment_result.returncode != 0:
                        print("⚠️ 评论爬取失败")
                else:
                    print("❌ 找不到评论爬取脚本")

    elif platform == 'youtube':
        print("内容类型: 视频")
        print("\n" + "-"*80)
        print("📥 下载视频")
        print("-"*80)

        cmd = [sys.executable, str(VIDEO_DOWNLOAD_SCRIPT), '-u', url]

        if args.info_only:
            cmd.append('--info-only')

        if args.output:
            cmd.extend(['-o', args.output])

        result = subprocess.run(cmd, cwd=SCRIPT_DIR)

        # 生成学习笔记
        if args.generate_notes and result.returncode == 0:
            # 查找最近下载的视频文件
            output_path = Path(args.output) if args.output else Path("downloaded_videos/youtube")
            if output_path.exists():
                video_files = list(output_path.glob("*.mp4"))
                video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                if video_files:
                    video_path = video_files[0]
                    notes_result = generate_video_notes(
                        video_path, args.model, args.keyframes,
                        args.no_gemini, args.upload_github
                    )
                    if not notes_result:
                        print("⚠️ 学习笔记生成失败")

    else:
        print("\n❌ 不支持的平台")
        print("   支持的平台: Bilibili, 小红书, YouTube")
        sys.exit(1)

    # 输出结果
    print("\n" + "="*80)
    if result.returncode == 0:
        print("✅ 处理完成!")
    else:
        print("❌ 处理失败!")
    print("="*80)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
