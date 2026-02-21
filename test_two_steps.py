#!/usr/bin/env python3
"""
两步测试脚本：
1. 下载小红书笔记图片（使用已有的 download_xhs_images.py）
2. 用 Gemini 分析图片文件夹

用法：
    python test_two_steps.py "小红书笔记链接"
"""

import os
import sys
import subprocess
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def step1_download_images(note_url: str):
    """步骤1: 下载图片"""
    print("\n" + "=" * 80)
    print("步骤1: 下载小红书笔记图片")
    print("=" * 80)
    print()

    # 调用已有的下载脚本
    script_path = Path(__file__).parent / "platforms" / "xiaohongshu" / "download_xhs_images.py"

    result = subprocess.run(
        [sys.executable, str(script_path), note_url],
        capture_output=False
    )

    return result.returncode == 0


def step2_analyze_with_gemini(image_dir: str, text: str = ""):
    """步骤2: 用 Gemini 分析图片"""
    print("\n" + "=" * 80)
    print("步骤2: 用 Gemini 分析图片")
    print("=" * 80)
    print()

    # 调用已有的多模态分析脚本
    script_path = Path(__file__).parent / "analysis" / "multimodal_gemini.py"

    cmd = [sys.executable, str(script_path), "--dir", image_dir]
    if text:
        cmd.extend(["--text", text])

    result = subprocess.run(
        cmd,
        capture_output=False
    )

    return result.returncode == 0


def main():
    if len(sys.argv) < 2:
        print("用法: python test_two_steps.py \"小红书笔记链接\"")
        print("\n注意：链接必须是完整的笔记链接（带 xsec_token）")
        print("\n示例:")
        print("  python test_two_steps.py \"https://www.xiaohongshu.com/explore/xxxxx?xsec_token=xxxxx\"")
        sys.exit(1)

    note_url = sys.argv[1]

    # 步骤1: 下载图片
    success1 = step1_download_images(note_url)

    if not success1:
        print("\n❌ 步骤1 失败，跳过步骤2")
        return

    # 找到下载的图片文件夹
    xhs_dir = Path("xhs_images")
    if not xhs_dir.exists():
        print("\n❌ 未找到下载的图片文件夹")
        return

    # 获取第一个子文件夹
    subdirs = [d for d in xhs_dir.iterdir() if d.is_dir()]
    if not subdirs:
        print("\n❌ 图片文件夹为空")
        return

    image_dir = subdirs[0]
    print(f"\n✅ 图片文件夹: {image_dir}")

    # 步骤2: Gemini 分析
    step2_analyze_with_gemini(str(image_dir))


if __name__ == "__main__":
    main()
