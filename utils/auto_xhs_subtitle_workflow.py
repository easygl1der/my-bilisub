#!/usr/bin/env python3
"""
小红书视频字幕分析工作流

一键完成：
1. 抓取用户视频列表
2. 下载音频并转录字幕（Whisper）
3. 生成AI摘要报告（Gemini）

使用示例:
    # 基本用法 - 获取最新10个视频并完成全部流程
    python auto_xhs_subtitle_workflow.py --url "小红书用户主页链接" --count 10

    # 从已有CSV开始，跳过视频抓取
    python auto_xhs_subtitle_workflow.py --csv "output/xhs_videos/用户ID.csv" --count 20

    # 仅抓取视频和提取字幕，不生成AI摘要
    python auto_xhs_subtitle_workflow.py --url "用户主页链接" --count 30 --no-summary

    # 仅生成AI摘要（已有字幕）
    python auto_xhs_subtitle_workflow.py --user "用户ID" --summary-only
"""

import os
import sys
import csv
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 路径配置 ====================

OUTPUT_DIR = PROJECT_ROOT / "output" / "xhs_workflows"
SUBTITLE_OUTPUT = OUTPUT_DIR / "subtitles"

# 工作流脚本
FETCH_VIDEOS_SCRIPT = PROJECT_ROOT / "utils" / "fetch_xhs_videos.py"
TRANSCRIBE_SCRIPT = PROJECT_ROOT / "ultimate_transcribe.py"
SUMMARY_SCRIPT = PROJECT_ROOT / "analysis" / "gemini_subtitle_summary.py"


# ==================== 步骤1: 抓取视频列表 ====================

def fetch_video_list(url: str, count: int = None) -> tuple:
    """
    步骤1: 抓取用户视频列表

    Returns:
        (success: bool, user_id: str, csv_path: Path)
    """
    print("\n" + "=" * 70)
    print("📋 步骤 1/3: 抓取用户视频列表")
    print("=" * 70)

    if not FETCH_VIDEOS_SCRIPT.exists():
        print(f"❌ 找不到脚本: {FETCH_VIDEOS_SCRIPT}")
        return False, None, None

    print(f"🔍 正在抓取视频列表...")

    # 构建命令
    cmd = [sys.executable, str(FETCH_VIDEOS_SCRIPT), '--url', url]

    if count:
        cmd.extend(['--count', str(count)])

    print(f"📝 命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        # 查找生成的CSV文件
        output_files = list((PROJECT_ROOT / "output" / "xhs_videos").glob("xhs_videos_*.csv"))

        if not output_files:
            print("❌ 未找到生成的CSV文件")
            return False, None, None

        # 获取最新的CSV文件
        csv_path = max(output_files, key=lambda p: p.stat().st_mtime)

        # 从CSV文件名中提取user_id
        user_id = csv_path.stem.split('_')[2] if len(csv_path.stem.split('_')) > 2 else "unknown"

        print(f"✅ 视频列表已保存: {csv_path}")
        print(f"📊 用户ID: {user_id}")

        return True, user_id, csv_path

    except subprocess.CalledProcessError as e:
        print(f"❌ 抓取视频列表失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return False, None, None


# ==================== 步骤2: 下载字幕 ====================

def download_subtitles(csv_path: Path, user_id: str, count: int = None) -> bool:
    """
    步骤2: 批量下载字幕（使用Whisper转录）

    Args:
        csv_path: 视频列表CSV文件
        user_id: 用户ID
        count: 处理数量限制

    Returns:
        是否成功
    """
    print("\n" + "=" * 70)
    print("📥 步骤 2/3: 下载音频并转录字幕")
    print("=" * 70)

    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    # 创建字幕输出目录
    subtitle_dir = SUBTITLE_OUTPUT / user_id
    subtitle_dir.mkdir(parents=True, exist_ok=True)

    # 读取CSV文件，获取视频链接
    video_urls = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('链接', '') or row.get('url', '')
                if url:
                    video_urls.append(url)

        # 限制数量
        if count and len(video_urls) > count:
            video_urls = video_urls[:count]

        print(f"📊 共 {len(video_urls)} 个视频需要处理")

    except Exception as e:
        print(f"❌ 读取CSV文件失败: {e}")
        return False

    # 逐个处理视频
    success_count = 0
    for i, url in enumerate(video_urls, 1):
        print(f"\n[{i}/{len(video_urls)}] 处理: {url}")

        try:
            # 调用ultimate_transcribe.py
            cmd = [
                sys.executable,
                str(TRANSCRIBE_SCRIPT),
                '-u', url,
                '-m', 'medium',  # 使用medium模型
                '-f', 'srt',
                '-o', str(subtitle_dir)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                cwd=PROJECT_ROOT
            )

            if result.returncode == 0:
                success_count += 1
                print(f"   ✅ 成功")
            else:
                print(f"   ❌ 失败: {result.stderr[:100] if result.stderr else '未知错误'}")

        except subprocess.TimeoutExpired:
            print(f"   ⏱️  超时")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

    print(f"\n📊 字幕下载完成: {success_count}/{len(video_urls)}")

    return success_count > 0


# ==================== 步骤3: 生成AI摘要 ====================

def generate_summary(user_id: str, model: str = 'flash-lite', jobs: int = 3) -> bool:
    """
    步骤3: 生成AI摘要报告

    Args:
        user_id: 用户ID
        model: Gemini模型
        jobs: 并发数

    Returns:
        是否成功
    """
    print("\n" + "=" * 70)
    print("🤖 步骤 3/3: 生成AI摘要报告")
    print("=" * 70)

    subtitle_dir = SUBTITLE_OUTPUT / user_id

    if not subtitle_dir.exists():
        print(f"❌ 字幕目录不存在: {subtitle_dir}")
        return False

    # 检查是否有字幕文件
    srt_files = list(subtitle_dir.glob("*.srt"))

    if not srt_files:
        print(f"❌ 未找到字幕文件")
        return False

    print(f"📊 找到 {len(srt_files)} 个字幕文件")

    # 调用Gemini分析脚本
    cmd = [
        sys.executable,
        str(SUMMARY_SCRIPT),
        str(subtitle_dir),
        '--model', model,
        '-j', str(jobs)
    ]

    print(f"📝 命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=PROJECT_ROOT
        )

        print("✅ AI摘要生成完成")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ 生成AI摘要失败: {e}")
        return False


# ==================== 主程序 ====================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="小红书视频字幕分析工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 基本用法 - 获取最新10个视频并完成全部流程
    python auto_xhs_subtitle_workflow.py --url "小红书用户主页链接" --count 10

    # 从已有CSV开始
    python auto_xhs_subtitle_workflow.py --csv "output/xhs_videos/用户ID.csv"

    # 指定Gemini模型和并发数
    python auto_xhs_subtitle_workflow.py --url "用户主页链接" --count 20 --model flash -j 5

    # 仅抓取视频和提取字幕，不生成AI摘要
    python auto_xhs_subtitle_workflow.py --url "用户主页链接" --count 30 --no-summary

    # 仅生成AI摘要（已有字幕）
    python auto_xhs_subtitle_workflow.py --user "用户ID" --summary-only
        """
    )

    # 输入源（三选一）
    parser.add_argument('-u', '--url', help='小红书用户主页链接')
    parser.add_argument('--csv', help='从已有CSV文件开始')
    parser.add_argument('--user', help='用户ID（用于--summary-only）')

    # 数量限制
    parser.add_argument('-c', '--count', type=int, help='处理数量限制')

    # 功能开关
    parser.add_argument('--no-fetch', action='store_true',
                       help='跳过视频抓取（使用已有CSV）')
    parser.add_argument('--no-subtitle', action='store_true',
                       help='跳过字幕下载')
    parser.add_argument('--no-summary', action='store_true',
                       help='跳过AI摘要生成')
    parser.add_argument('--summary-only', action='store_true',
                       help='仅生成AI摘要（已有字幕）')

    # Gemini配置
    parser.add_argument('-m', '--model',
                       choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite',
                       help='Gemini模型（默认: flash-lite）')
    parser.add_argument('-j', '--jobs', type=int, default=3,
                       help='并发处理数（默认: 3）')

    args = parser.parse_args()

    # 验证参数
    if not args.url and not args.csv and not args.user:
        parser.print_help()
        print("\n❌ 请提供 --url, --csv 或 --user 参数")
        return 1

    if args.summary_only and not args.user:
        print("❌ --summary-only 需要提供 --user 参数")
        return 1

    # 打印欢迎信息
    print("\n" + "=" * 70)
    print("🎬 小红书视频字幕分析工作流")
    print("=" * 70)
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 步骤1: 抓取视频列表
        user_id = None
        csv_path = None

        if args.summary_only:
            # 仅生成摘要模式
            user_id = args.user
        elif args.csv:
            # 从CSV开始
            csv_path = Path(args.csv)
            if not csv_path.exists():
                print(f"❌ CSV文件不存在: {csv_path}")
                return 1

            # 从文件名提取user_id
            user_id = csv_path.stem.split('_')[2] if len(csv_path.stem.split('_')) > 2 else "unknown"
            print(f"📂 使用现有CSV: {csv_path}")
        elif args.url:
            # 从URL开始
            if not args.no_fetch:
                success, user_id, csv_path = fetch_video_list(args.url, args.count)

                if not success:
                    print("❌ 视频列表抓取失败")
                    return 1
            else:
                print("⏭️  跳过视频抓取")
                return 1

        # 步骤2: 下载字幕
        if not args.no_subtitle and not args.summary_only:
            if not csv_path:
                print("❌ 缺少CSV文件路径")
                return 1

            success = download_subtitles(csv_path, user_id, args.count)

            if not success:
                print("⚠️  字幕下载失败，但继续执行...")

        # 步骤3: 生成AI摘要
        if not args.no_summary or args.summary_only:
            success = generate_summary(user_id, args.model, args.jobs)

            if not success:
                print("❌ AI摘要生成失败")
                return 1

        # 完成
        print("\n" + "=" * 70)
        print("✅ 工作流执行完成!")
        print("=" * 70)

        if user_id:
            print(f"📂 输出目录: {SUBTITLE_OUTPUT / user_id}")
            print(f"📊 AI摘要: {SUBTITLE_OUTPUT.parent / f'{user_id}_AI总结.md'}")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
