#!/usr/bin/env python3
"""
测试优化后的视频学习笔记生成器

⚠️  注意：请确保已激活 bilisub 环境
    conda activate bilisub

优化重点:
1. 关键帧不再"头重脚轻" - 均匀分布在前、中、后
2. 每个关键帧有描述和选择理由
3. 相邻帧之间有内容过渡说明
4. GitHub上传失败自动重试（5次，指数退避）
5. 更好的Markdown结构
6. 时间戳可点击跳转到视频对应位置

使用方法:
    conda activate bilisub
    python test_video_optimization.py <视频文件路径>

示例:
    python test_video_optimization.py "video.mp4"
    python test_video_optimization.py "downloaded_videos/single_download/视频标题.mp4"
"""

import sys
import subprocess
import argparse
from pathlib import Path
import os

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='测试优化后的视频学习笔记生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s video.mp4
  %(prog)s "downloaded_videos/test.mp4"
  %(prog)s "C:\\videos\\my video.mp4"
        '''
    )
    parser.add_argument(
        'video_path',
        nargs='?',
        default="downloaded_videos/single_download/盘点一周AI大事(2月15日)｜王炸视频模型.mp4",
        help='视频文件路径（默认：测试视频）'
    )
    parser.add_argument(
        '-k', '--keyframes',
        type=int,
        default=None,
        help='指定关键帧数量（不指定则自动计算）'
    )
    parser.add_argument(
        '--no-gemini',
        action='store_true',
        help='不使用 Gemini 智能检测，使用均匀采样'
    )

    args = parser.parse_args()
    test_video = Path(args.video_path)

    print("=" * 60)
    print("🧪 测试优化后的视频学习笔记生成器")
    print("=" * 60)
    print()

    # 检查 Conda 环境
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', '')
    if conda_env != 'bilisub':
        print("⚠️  警告: 当前不在 bilisub 环境中")
        print(f"   当前环境: {conda_env if conda_env else '(base)'}")
        print()
        print("请先激活 bilisub 环境:")
        print("   conda activate bilisub")
        print()
        response = input("是否继续测试? (y/N): ")
        if response.lower() != 'y':
            print("已取消测试")
            return 1
        print()
    else:
        print(f"✅ 当前环境: {conda_env}")
        print()

    # 检查视频文件是否存在
    if not test_video.exists():
        print(f"❌ 视频不存在: {test_video}")
        print()
        print("请提供有效的视频文件路径")
        print()
        print("使用方法:")
        print(f"  python test_video_optimization.py <视频路径>")
        return 1

    print(f"📹 测试视频: {test_video.name}")
    print(f"📂 视频路径: {test_video}")
    print()

    # 检查视频时长
    print("🔍 检查视频信息...")
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(test_video)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
        print(f"   ⏱️  视频时长: {duration:.0f} 秒")
    except Exception as e:
        print(f"   ⚠️  无法获取视频时长: {e}")
        duration = 0

    print()
    print("=" * 60)
    print("🚀 开始生成学习笔记")
    print("=" * 60)
    print()

    # 构建命令
    cmd = [sys.executable, "video_to_markdown.py", "-f", str(test_video)]

    # 可选参数
    if args.keyframes:
        cmd.extend(["-k", str(args.keyframes)])

    if args.no_gemini:
        cmd.append("--no-gemini")

    print(f"📝 执行命令:")
    print(f"   {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        print()
        print("📂 请检查生成的笔记文件:")
        print(f"   learning_notes/{test_video.stem}/{test_video.stem}_学习笔记.md")
        print()
        print("🔍 验证要点:")
        print("   1. 关键帧是否均匀分布（不是都在前面）")
        print("   2. 每个关键帧是否有「选择理由」")
        print("   3. 是否有「接下来 X 秒」的过渡说明")
        print("   4. Markdown 结构是否清晰无重复")
        print("   5. 时间戳是否可点击跳转")
        return 0

    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("❌ 测试失败")
        print("=" * 60)
        print(f"退出码: {e.returncode}")
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 测试出错")
        print("=" * 60)
        print(f"错误: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
