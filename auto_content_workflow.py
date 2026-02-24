#!/usr/bin/env python3
"""
自动内容处理工作流

根据输入 URL 自动识别平台和内容类型，并调用相应的处理工具：
- B站视频：下载视频
- 小红书图文：下载图片 + AI 分析
- 小红书视频：下载视频

用法: python auto_content_workflow.py "URL"
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
    # B站视频（自动下载）
    python auto_content_workflow.py "https://www.bilibili.com/video/BV1UPZtBiEFS"

    # 小红书（自动识别图文/视频，图文默认使用 GitHub 图床）
    python auto_content_workflow.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx"

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
                       help='Gemini 模型（仅图文分析，默认: flash-lite）')
    parser.add_argument('-o', '--output', help='输出目录（仅视频下载）')
    parser.add_argument('--info-only', action='store_true',
                       help='只获取信息，不下载（仅视频下载）')
    parser.add_argument('--upload-github', action='store_true',
                       help='上传图片到 GitHub CDN（仅图文分析）')

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
        print("\n" + "-"*80)
        print("📥 下载视频")
        print("-"*80)

        # 构建 test_video_download.py 的命令
        cmd = [sys.executable, str(VIDEO_DOWNLOAD_SCRIPT), '-u', url]

        if args.info_only:
            cmd.append('--info-only')

        if args.output:
            cmd.extend(['-o', args.output])

        # 执行
        result = subprocess.run(cmd, cwd=SCRIPT_DIR)

    elif platform == 'xiaohongshu':
        # 小红书内容类型判断
        content_type = args.type

        if content_type == 'auto':
            # 自动检测图文还是视频
            content_type = 'video' if is_xhs_video(url) else 'image'
        else:
            # 用户手动指定
            print(f"内容类型: {'视频' if content_type == 'video' else '图文'}（手动指定）")

        if content_type == 'video':
            # 小红书视频下载
            print("\n" + "-"*80)
            print("📥 下载视频")
            print("-"*80)

            cmd = [sys.executable, str(VIDEO_DOWNLOAD_SCRIPT), '-u', url]

            if args.info_only:
                cmd.append('--info-only')

            if args.output:
                cmd.extend(['-o', args.output])

            result = subprocess.run(cmd, cwd=SCRIPT_DIR)

        else:
            # 小红书图文分析（默认使用 GitHub 图床）
            print("\n" + "-"*80)
            print("📸 下载图片 + 🤖 AI 分析")
            print("-"*80)

            cmd = [sys.executable, str(XHS_IMAGE_WORKFLOW), url, '--model', args.model]

            # 默认上传到 GitHub 图床
            cmd.append('--upload-github')

            result = subprocess.run(cmd, cwd=SCRIPT_DIR)

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
