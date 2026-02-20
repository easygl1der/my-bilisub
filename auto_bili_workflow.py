#!/usr/bin/env python3
"""
B站用户视频自动化工作流程

一键完成：
1. 抓取用户视频列表
2. 批量提取字幕
3. 生成AI摘要报告

使用示例:
    # 基本用法 - 获取最新10个视频并完成全部流程
    python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 10

    # 指定 Gemini 模型和并发数
    python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 20 --model flash -j 5

    # 从已有CSV开始，跳过视频抓取
    python auto_bili_workflow.py --csv "MediaCrawler/bilibili_videos_output/用户名.csv" --count 20

    # 仅抓取视频和提取字幕，不生成AI摘要
    python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 30 --no-summary
"""

import argparse
import asyncio
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 路径配置 ====================

SCRIPT_DIR = Path(__file__).parent
MEDIA_CRAWLER_DIR = SCRIPT_DIR / "MediaCrawler"
SUBTITLE_FETCH_SCRIPT = SCRIPT_DIR / "utils" / "batch_subtitle_fetch.py"
SUMMARY_SCRIPT = SCRIPT_DIR / "analysis" / "gemini_subtitle_summary.py"

# 输出路径
MEDIA_CRAWLER_OUTPUT = MEDIA_CRAWLER_DIR / "bilibili_videos_output"
SUBTITLE_OUTPUT = SCRIPT_DIR / "output" / "subtitles"


# ==================== 步骤1: 抓取视频列表 ====================

def fetch_video_list(url: str, count: int = None) -> tuple:
    """
    步骤1: 抓取用户视频列表

    Returns:
        (success: bool, user_name: str, csv_path: Path)
    """
    print("\n" + "=" * 70)
    print("📋 步骤 1/3: 抓取用户视频列表")
    print("=" * 70)

    # 提取UID
    uid = extract_uid_from_url(url)
    if not uid:
        print(f"❌ 无法从URL提取UID: {url}")
        return False, None, None

    print(f"🔍 用户UID: {uid}")

    # 调用 MediaCrawler 的 fetch 脚本
    # 由于该脚本使用交互式输入，我们需要创建一个临时脚本或使用 stdin

    fetch_script = MEDIA_CRAWLER_DIR / "fetch_bilibili_videos.py"

    if not fetch_script.exists():
        print(f"❌ 找不到脚本: {fetch_script}")
        return False, None, None

    print(f"📡 正在抓取视频列表...")

    # 使用 stdin 传递 URL
    try:
        result = subprocess.run(
            [sys.executable, str(fetch_script)],
            input=f"{url}\n",
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=600  # 10分钟超时
        )

        # 输出结果
        if result.stdout:
            # 只打印关键信息
            for line in result.stdout.split('\n'):
                if any(keyword in line for keyword in ['✅', '❌', '⚠️', '用户名', 'CSV', '新增视频']):
                    print(line)

        if result.returncode != 0 and result.stderr:
            print(f"⚠️ 抓取过程有警告: {result.stderr[:200]}")

    except subprocess.TimeoutExpired:
        print("⚠️ 视频抓取超时")
        return False, None, None
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return False, None, None

    # 查找生成的CSV文件
    csv_files = list(MEDIA_CRAWLER_OUTPUT.glob("*.csv"))
    if csv_files:
        # 按修改时间排序，取最新的
        latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
        user_name = latest_csv.stem
        print(f"\n📁 找到CSV: {latest_csv}")
        print(f"👤 用户名: {user_name}")
        return True, user_name, latest_csv
    else:
        print("❌ 未找到生成的CSV文件")
        return False, None, None


# ==================== 步骤2: 批量提取字幕 ====================

async def fetch_subtitles(csv_path: Path, count: int = None) -> bool:
    """
    步骤2: 批量提取字幕 (调用 utils/batch_subtitle_fetch.py)
    """
    print("\n" + "=" * 70)
    print("📝 步骤 2/3: 批量提取字幕")
    print("=" * 70)

    if not csv_path or not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    if not SUBTITLE_FETCH_SCRIPT.exists():
        print(f"❌ 找不到脚本: {SUBTITLE_FETCH_SCRIPT}")
        return False

    print(f"📄 CSV文件: {csv_path}")
    if count:
        print(f"🔢 限制数量: {count}")

    # 动态导入并运行
    try:
        # 添加 utils 目录到路径
        sys.path.insert(0, str(SUBTITLE_FETCH_SCRIPT.parent))

        # 导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "batch_subtitle_fetch",
            SUBTITLE_FETCH_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用主函数
        await module.process_batch(str(csv_path), limit=count)

        print("\n✅ 字幕提取完成!")
        return True

    except Exception as e:
        print(f"❌ 字幕提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 步骤3: 生成AI摘要 ====================

def generate_summary(user_name: str, model: str = 'flash-lite', jobs: int = 3) -> bool:
    """
    步骤3: 生成AI摘要报告 (调用 analysis/gemini_subtitle_summary.py)
    """
    print("\n" + "=" * 70)
    print("🤖 步骤 3/3: 生成AI摘要报告")
    print("=" * 70)

    subtitle_dir = SUBTITLE_OUTPUT / user_name

    if not subtitle_dir.exists():
        print(f"❌ 字幕目录不存在: {subtitle_dir}")
        return False

    # 检查SRT文件
    srt_files = list(subtitle_dir.glob("*.srt"))
    if not srt_files:
        print(f"❌ 没有找到SRT文件: {subtitle_dir}")
        return False

    print(f"📁 字幕目录: {subtitle_dir}")
    print(f"📄 SRT文件数: {len(srt_files)}")
    print(f"🤖 模型: {model}")
    print(f"⚡ 并发数: {jobs}")

    if not SUMMARY_SCRIPT.exists():
        print(f"❌ 找不到脚本: {SUMMARY_SCRIPT}")
        return False

    # 调用摘要脚本
    try:
        # 导入模块
        sys.path.insert(0, str(SUMMARY_SCRIPT.parent))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gemini_subtitle_summary",
            SUMMARY_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用处理函数
        module.process_subtitles(str(subtitle_dir), model=model, max_workers=jobs)

        print("\n✅ AI摘要生成完成!")
        return True

    except Exception as e:
        print(f"❌ AI摘要生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 工具函数 ====================

def extract_uid_from_url(url: str) -> str:
    """从B站用户链接中提取UID"""
    try:
        if '?' in url:
            url = url.split('?')[0]
        if 'space.bilibili.com/' in url:
            uid = url.split('space.bilibili.com/')[-1].strip('/')
            return uid
    except Exception:
        pass
    return None


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="B站用户视频自动化工作流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法 - 获取最新10个视频
  python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 10

  # 指定 Gemini 模型和并发数
  python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 20 --model flash -j 5

  # 从已有CSV开始，跳过视频抓取
  python auto_bili_workflow.py --csv "MediaCrawler/bilibili_videos_output/用户名.csv" --count 20

  # 仅抓取视频和提取字幕，不生成AI摘要
  python auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 30 --no-summary

  # 仅生成AI摘要（已有字幕）
  python auto_bili_workflow.py --user "赛雷话金" --summary-only
        """
    )

    parser.add_argument("--url", "-u", help="B站用户主页链接")
    parser.add_argument("--csv", "-c", help="直接使用已有的CSV文件（跳过步骤1）")
    parser.add_argument("--user", help="指定用户名（用于步骤2和3）")
    parser.add_argument("--count", "-n", type=int, default=None,
                        help="处理的视频数量（默认：全部）")
    parser.add_argument("--model", "-m", choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help="Gemini模型（默认: flash-lite）")
    parser.add_argument("--jobs", "-j", type=int, default=3,
                        help="并发处理数（默认: 3）")
    parser.add_argument("--no-summary", action="store_true",
                        help="跳过AI摘要生成步骤")
    parser.add_argument("--summary-only", action="store_true",
                        help="仅生成AI摘要（跳过步骤1和2）")

    args = parser.parse_args()

    # 验证参数
    if not args.summary_only and not args.csv and not args.url:
        print("❌ 错误: 必须提供 --url, --csv 或使用 --summary-only")
        parser.print_help()
        return 1

    print("\n" + "=" * 70)
    print("🚀 B站用户视频自动化工作流程")
    print("=" * 70)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化变量
    user_name = args.user
    csv_path = None

    # ==================== 步骤1: 抓取视频 ====================
    if not args.summary_only and not args.csv:
        success, name, path = fetch_video_list(args.url, args.count)
        if not success and not path:
            print("\n❌ 视频抓取失败，工作流程终止")
            return 1

        if not user_name:
            user_name = name
        csv_path = path

    # ==================== 使用已有CSV ====================
    elif args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"❌ CSV文件不存在: {csv_path}")
            return 1
        if not user_name:
            user_name = csv_path.stem
        print(f"\n📁 使用指定CSV: {csv_path}")
        print(f"👤 用户名: {user_name}")

    # ==================== 步骤2: 提取字幕 ====================
    if not args.summary_only:
        if csv_path:
            # 步骤2是异步的
            success = asyncio.run(fetch_subtitles(csv_path, args.count))
            if not success:
                print("\n⚠️ 字幕提取失败，但继续尝试生成摘要...")
        else:
            print("\n⚠️ 没有CSV文件，跳过字幕提取")

    # ==================== 步骤3: 生成AI摘要 ====================
    if not args.no_summary or args.summary_only:
        if user_name:
            success = generate_summary(user_name, args.model, args.jobs)

            if success:
                print("\n" + "=" * 70)
                print("🎉 工作流程完成!")
                print("=" * 70)
                print(f"\n📁 输出文件:")
                if csv_path:
                    print(f"  - CSV: {csv_path}")
                print(f"  - 字幕: {SUBTITLE_OUTPUT / user_name}")
                print(f"  - AI摘要: {SUBTITLE_OUTPUT / f'{user_name}_AI总结.md'}")
            else:
                print("\n⚠️ AI摘要生成失败")
                return 1
        else:
            print("\n❌ 无法确定用户名，无法生成摘要")
            return 1
    else:
        print("\n" + "=" * 70)
        print("✅ 工作流程完成 (跳过AI摘要)")
        print("=" * 70)

    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


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
