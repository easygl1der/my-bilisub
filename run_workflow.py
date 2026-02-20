#!/usr/bin/env python3
"""
BiliSub 工作流程脚本（半自动版本）

使用说明：
1. 先在 Colab 运行 MediaCrawler 爬取视频信息，得到 CSV 文件
2. 本地运行此脚本，自动完成：下载字幕 → AI 生成摘要

使用示例:
    # 处理指定 UP 主（需要先有 CSV 文件）
    python run_workflow.py "小天fotos"

    # 指定并发数
    python run_workflow.py "小天fotos" --jobs 5
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def print_step(step_num: int, title: str):
    """打印步骤标题"""
    print("\n" + "=" * 60)
    print(f"[步骤 {step_num}] {title}")
    print("=" * 60)


def check_csv_exists(author_name: str) -> Path:
    """检查 CSV 文件是否存在"""
    base_dir = Path(__file__).parent
    possible_paths = [
        base_dir / "MediaCrawler" / "bilibili_videos_output" / f"{author_name}.csv",
        base_dir / "output" / "subtitles" / f"{author_name}.csv",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def check_api_key() -> bool:
    """检查 API Key 是否设置"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        print(f"✅ GEMINI_API_KEY 已设置")
        return True
    else:
        print("❌ GEMINI_API_KEY 未设置")
        return False


def run_command(cmd: list, description: str) -> bool:
    """运行命令并返回是否成功"""
    print(f"\n执行: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # 实时显示输出
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False


def show_colab_instructions(author_name: str):
    """显示 Colab 操作指引"""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║                    先完成步骤 A（Colab 爬取）                   ║
╚════════════════════════════════════════════════════════════════╝

在 Google Colab 中执行以下操作：

1. 打开 Colab: https://colab.research.google.com/

2. 挂载 Google Drive（如果需要）
   from google.colab import drive
   drive.mount('/content/drive')

3. 进入项目目录
   %cd /content/drive/MyDrive/my-projects/my-bilisub/MediaCrawler

4. 修改配置文件 config.yaml，设置爬取的 UP 主名称
   - 找到 bilibili_videos 部分
   - 设置 keyword: "{author_name}"

5. 运行爬取脚本
   !python fetch_bilibili_videos.py

6. 等待完成后，CSV 文件保存在：
   MediaCrawler/bilibili_videos_output/{author_name}.csv

7. 下载 CSV 文件到本地：
   - 在 Colab 文件面板找到文件
   - 右键 → 下载
   - 放到本项目的 MediaCrawler/bilibili_videos_output/ 目录

完成后按回车继续...
""")


def workflow(author_name: str, max_workers: int = 3):
    """
    本地工作流程（步骤 B + C）

    Args:
        author_name: UP 主名称
        max_workers: AI 处理并发数
    """

    base_dir = Path(__file__).parent
    csv_dir = base_dir / "MediaCrawler" / "bilibili_videos_output"
    csv_file = csv_dir / f"{author_name}.csv"
    subtitle_dir = base_dir / "output" / "subtitles" / author_name

    total_start = time.time()

    # ==================== 检查 CSV 文件 ====================
    print("\n" + "=" * 60)
    print("BiliSub 工作流程（半自动版本）")
    print("=" * 60)
    print(f"\n目标 UP 主: {author_name}")

    # 检查 CSV 是否存在
    csv_path = check_csv_exists(author_name)
    if not csv_path:
        print(f"\n❌ 未找到 CSV 文件: {csv_file}")
        print(f"\n请先在 Colab 完成爬取步骤")
        show_colab_instructions(author_name)
        input("\n完成后按回车继续...")

        # 再次检查
        csv_path = check_csv_exists(author_name)
        if not csv_path:
            print("❌ 仍未找到 CSV 文件，退出")
            return

    print(f"✅ 找到 CSV 文件: {csv_path}")

    # ==================== 步骤 B: 下载字幕 ====================
    print_step("B", "批量下载字幕")

    fetch_script = base_dir / "batch_subtitle_fetch.py"

    cmd = [sys.executable, str(fetch_script), str(csv_path)]
    success = run_command(cmd, "下载字幕")

    if not success:
        print("❌ 字幕下载失败")
        return

    print(f"✅ 字幕保存位置: {subtitle_dir}")

    # ==================== 步骤 C: AI 生成摘要 ====================
    print_step("C", "AI 生成知识库摘要")

    summary_script = base_dir / "gemini_subtitle_summary.py"

    # 检查 API Key
    if not check_api_key():
        print("\n请先设置环境变量:")
        print("  set GEMINI_API_KEY=你的API Key")
        print("  或")
        print("  setx GEMINI_API_KEY \"你的API Key\"")
        print("然后重新运行脚本")
        return

    cmd = [
        sys.executable,
        str(summary_script),
        str(subtitle_dir),
        "-j", str(max_workers)
    ]

    success = run_command(cmd, "AI 摘要")

    if not success:
        print("❌ AI 摘要失败")
        return

    # ==================== 完成 ====================
    total_elapsed = time.time() - total_start

    output_file = base_dir / "output" / "subtitles" / f"{author_name}_AI总结.md"

    print("\n" + "=" * 60)
    print("🎉 工作流程完成!")
    print("=" * 60)
    print(f"UP 主: {author_name}")
    print(f"总耗时: {total_elapsed:.1f}秒")
    print(f"\n输出文件:")
    print(f"  - CSV: {csv_path}")
    print(f"  - 字幕: {subtitle_dir}")
    print(f"  - AI 摘要: {output_file}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="BiliSub 工作流程：下载字幕 → AI 生成知识库摘要",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 处理 UP 主（需要先在 Colab 爬取得到 CSV）
    python run_workflow.py "小天fotos"

    # 指定并发数
    python run_workflow.py "小天fotos" --jobs 5

完整流程:
    A. Colab 爬取 → 生成 CSV
    B. 本地下载字幕 → 生成 SRT
    C. 本地 AI 摘要 → 生成报告
        """
    )

    parser.add_argument('author', help='UP 主名称')
    parser.add_argument('-j', '--jobs', type=int, default=3,
                        help='AI 处理并发数（默认: 3）')

    args = parser.parse_args()

    workflow(
        author_name=args.author,
        max_workers=args.jobs
    )


if __name__ == "__main__":
    main()
