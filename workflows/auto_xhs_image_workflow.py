#!/usr/bin/env python3
"""
小红书图文分析工作流

一键完成：
1. 抓取用户图文笔记列表
2. 下载图片和文案
3. 生成AI分析报告（Gemini，支持风格检测）

使用示例:
    # 基本用法 - 获取最新10个图文并完成全部流程
    python auto_xhs_image_workflow.py --url "小红书用户主页链接" --count 10

    # 从已有CSV开始，跳过笔记抓取
    python auto_xhs_image_workflow.py --csv "output/xhs_images/用户ID.csv" --count 20

    # 仅抓取图文笔记，不生成AI分析
    python auto_xhs_image_workflow.py --url "用户主页链接" --count 30 --no-analysis

    # 仅生成AI分析（已有图片）
    python auto_xhs_image_workflow.py --user "用户ID" --analysis-only
"""

import os
import sys
import csv
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict

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
IMAGES_OUTPUT = OUTPUT_DIR / "xhs_images"
ANALYSIS_OUTPUT = OUTPUT_DIR / "xhs_analysis"

# 工作流脚本
FETCH_IMAGES_SCRIPT = PROJECT_ROOT / "platforms" / "xiaohongshu" / "fetch_xhs_image_notes.py"
IMAGE_ANALYSIS_SCRIPT = PROJECT_ROOT / "analysis" / "xhs_image_analysis.py"


# ==================== 步骤1: 抓取图文笔记列表 ====================

def fetch_image_notes(url: str, count: int = None) -> tuple:
    """
    步骤1: 抓取用户图文笔记列表

    Returns:
        (success: bool, user_id: str, csv_path: Path)
    """
    print("\n" + "=" * 70)
    print("📋 步骤 1/3: 抓取用户图文笔记列表")
    print("=" * 70)

    if not FETCH_IMAGES_SCRIPT.exists():
        print(f"❌ 找不到脚本: {FETCH_IMAGES_SCRIPT}")
        return False, None, None

    print(f"🔍 正在抓取图文笔记列表...")

    # 构建命令
    cmd = [sys.executable, str(FETCH_IMAGES_SCRIPT), '--url', url]

    if count:
        cmd.extend(['--count', str(count)])

    print(f"📝 命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=PROJECT_ROOT
        )

        # 查找生成的CSV文件
        output_files = list((PROJECT_ROOT / "output" / "xhs_images").glob("xhs_images_*.csv"))

        if not output_files:
            print("❌ 未找到生成的CSV文件")
            return False, None, None

        # 获取最新的CSV文件
        csv_path = max(output_files, key=lambda p: p.stat().st_mtime)

        # 从CSV文件名中提取user_id
        user_id = csv_path.stem.split('_')[2] if len(csv_path.stem.split('_')) > 2 else "unknown"

        print(f"✅ 图文笔记列表已保存: {csv_path}")
        print(f"📊 用户ID: {user_id}")

        return True, user_id, csv_path

    except subprocess.CalledProcessError as e:
        print(f"❌ 抓取图文笔记列表失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return False, None, None


# ==================== 步骤2: 下载图片 ====================

def download_images(csv_path: Path, user_id: str, count: int = None) -> bool:
    """
    步骤2: 批量下载图片和文案

    Args:
        csv_path: 图文笔记列表CSV文件
        user_id: 用户ID
        count: 处理数量限制

    Returns:
        是否成功
    """
    print("\n" + "=" * 70)
    print("📸 步骤 2/3: 下载图片和文案")
    print("=" * 70)

    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    # 创建输出目录
    images_base_dir = IMAGES_OUTPUT / user_id
    images_base_dir.mkdir(parents=True, exist_ok=True)

    # 读取CSV文件
    notes_data = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                notes_data.append(row)

        # 限制数量
        if count and len(notes_data) > count:
            notes_data = notes_data[:count]

        print(f"📊 共 {len(notes_data)} 个图文笔记需要处理")

    except Exception as e:
        print(f"❌ 读取CSV文件失败: {e}")
        return False

    # 逐个处理笔记
    success_count = 0
    for i, note in enumerate(notes_data, 1):
        title = note.get('标题', '') or note.get('title', '未知标题')
        url = note.get('链接', '') or note.get('url', '')
        note_id = note.get('笔记ID', '') or note.get('note_id', '')

        print(f"\n[{i}/{len(notes_data)}] 处理: {title[:50]}")

        # 清理标题作为文件夹名
        safe_title = sanitize_filename(title)
        note_dir = images_base_dir / f"{i:03d}_{safe_title}"

        try:
            # 创建笔记目录
            note_dir.mkdir(parents=True, exist_ok=True)

            # 保存文案
            content_file = note_dir / "content.txt"
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"标题: {title}\n")
                f.write(f"链接: {url}\n")
                f.write(f"笔记ID: {note_id}\n")
                f.write(f"\n{'='*50}\n\n")
                # TODO: 这里需要从笔记页面提取正文内容
                f.write(f"[正文内容待提取]")

            # TODO: 实际下载图片
            # 这里需要使用MediaCrawler或download_xhs_image_only.py的逻辑
            # 暂时跳过图片下载
            print(f"   📁 创建目录: {note_dir.name}")
            print(f"   ⚠️  图片下载功能待实现")

            success_count += 1

        except Exception as e:
            print(f"   ❌ 失败: {e}")

    print(f"\n📊 图片下载完成: {success_count}/{len(notes_data)}")

    return success_count > 0


def sanitize_filename(name: str) -> str:
    """清理文件名"""
    import re
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    return name.strip('. ')[:50] or "unnamed"


# ==================== 步骤3: 生成AI分析 ====================

def generate_analysis(user_id: str, model: str = 'flash-lite') -> bool:
    """
    步骤3: 生成AI分析报告（调用analysis/xhs_image_analysis.py）

    Args:
        user_id: 用户ID
        model: Gemini模型

    Returns:
        是否成功
    """
    print("\n" + "=" * 70)
    print("🤖 步骤 3/3: 生成AI分析报告")
    print("=" * 70)

    images_dir = IMAGES_OUTPUT / user_id

    if not images_dir.exists():
        print(f"❌ 图片目录不存在: {images_dir}")
        return False

    # 检查是否有笔记目录
    note_dirs = [d for d in images_dir.iterdir() if d.is_dir()]

    if not note_dirs:
        print(f"❌ 未找到笔记目录")
        return False

    print(f"📊 找到 {len(note_dirs)} 个笔记")

    # 调用xhs_image_analysis.py
    if not IMAGE_ANALYSIS_SCRIPT.exists():
        print(f"❌ 分析脚本不存在: {IMAGE_ANALYSIS_SCRIPT}")
        return False

    # 构建命令
    # 注意：xhs_image_analysis.py 需要笔记目录作为参数
    cmd = [
        sys.executable,
        str(IMAGE_ANALYSIS_SCRIPT),
        '--user-dir', str(images_dir),
        '--model', model
    ]

    print(f"📝 命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=PROJECT_ROOT
        )

        print("✅ AI分析生成完成")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ 生成AI分析失败: {e}")
        return False


# ==================== 主程序 ====================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="小红书图文分析工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 基本用法 - 获取最新10个图文并完成全部流程
    python auto_xhs_image_workflow.py --url "小红书用户主页链接" --count 10

    # 从已有CSV开始
    python auto_xhs_image_workflow.py --csv "output/xhs_images/用户ID.csv"

    # 指定Gemini模型
    python auto_xhs_image_workflow.py --url "用户主页链接" --count 20 --model flash

    # 仅抓取图文笔记，不生成AI分析
    python auto_xhs_image_workflow.py --url "用户主页链接" --count 30 --no-analysis

    # 仅生成AI分析（已有图片）
    python auto_xhs_image_workflow.py --user "用户ID" --analysis-only
        """
    )

    # 输入源（三选一）
    parser.add_argument('-u', '--url', help='小红书用户主页链接')
    parser.add_argument('--csv', help='从已有CSV文件开始')
    parser.add_argument('--user', help='用户ID（用于--analysis-only）')

    # 数量限制
    parser.add_argument('-c', '--count', type=int, help='处理数量限制')

    # 功能开关
    parser.add_argument('--no-fetch', action='store_true',
                       help='跳过笔记抓取（使用已有CSV）')
    parser.add_argument('--no-download', action='store_true',
                       help='跳过图片下载')
    parser.add_argument('--no-analysis', action='store_true',
                       help='跳过AI分析生成')
    parser.add_argument('--analysis-only', action='store_true',
                       help='仅生成AI分析（已有图片）')

    # Gemini配置
    parser.add_argument('-m', '--model',
                       choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite',
                       help='Gemini模型（默认: flash-lite）')

    args = parser.parse_args()

    # 验证参数
    if not args.url and not args.csv and not args.user:
        parser.print_help()
        print("\n❌ 请提供 --url, --csv 或 --user 参数")
        return 1

    if args.analysis_only and not args.user:
        print("❌ --analysis-only 需要提供 --user 参数")
        return 1

    # 打印欢迎信息
    print("\n" + "=" * 70)
    print("📸 小红书图文分析工作流")
    print("=" * 70)
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 步骤1: 抓取图文笔记列表
        user_id = None
        csv_path = None

        if args.analysis_only:
            # 仅生成分析模式
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
                success, user_id, csv_path = fetch_image_notes(args.url, args.count)

                if not success:
                    print("❌ 图文笔记列表抓取失败")
                    return 1
            else:
                print("⏭️  跳过笔记抓取")
                return 1

        # 步骤2: 下载图片
        if not args.no_download and not args.analysis_only:
            if not csv_path:
                print("❌ 缺少CSV文件路径")
                return 1

            success = download_images(csv_path, user_id, args.count)

            if not success:
                print("⚠️  图片下载失败，但继续执行...")

        # 步骤3: 生成AI分析
        if not args.no_analysis or args.analysis_only:
            success = generate_analysis(user_id, args.model)

            if not success:
                print("❌ AI分析生成失败")
                return 1

        # 完成
        print("\n" + "=" * 70)
        print("✅ 工作流执行完成!")
        print("=" * 70)

        if user_id:
            print(f"📂 输出目录: {IMAGES_OUTPUT / user_id}")

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
