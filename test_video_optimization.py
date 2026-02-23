#!/usr/bin/env python3
"""
测试优化后的视频学习笔记生成器

⚠️  注意：请确保已激活 bilisub 环境
    conda activate bilisub

测试视频: 盘点一周AI大事(2月15日)｜王炸视频模型.mp4
视频时长: ~102秒

优化重点:
1. 关键帧不再"头重脚轻" - 均匀分布在前、中、后
2. 每个关键帧有描述和选择理由
3. 相邻帧之间有内容过渡说明
4. GitHub上传失败自动重试（5次，指数退避）
5. 更好的Markdown结构

使用方法:
    conda activate bilisub
    python test_video_optimization.py
"""

import sys
import subprocess
from pathlib import Path
import os

# 视频文件路径
TEST_VIDEO = Path("downloaded_videos/single_download/盘点一周AI大事(2月15日)｜王炸视频模型.mp4")

def main():
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
    if not TEST_VIDEO.exists():
        print(f"❌ 测试视频不存在: {TEST_VIDEO}")
        print()
        print("请确保视频文件存在，或修改 TEST_VIDEO 变量指向正确的文件")
        return 1

    print(f"📹 测试视频: {TEST_VIDEO.name}")
    print(f"📂 视频路径: {TEST_VIDEO}")
    print()

    # 检查视频时长
    print("🔍 检查视频信息...")
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(TEST_VIDEO)],
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

    # 调用优化后的 video_to_markdown.py
    # 使用 -k 参数不指定，让它自动计算
    cmd = [
        sys.executable,
        "video_to_markdown.py",
        "-f", str(TEST_VIDEO),
        # 不指定 -k，让系统自动计算最优帧数
    ]

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
        print(f"   learning_notes/{TEST_VIDEO.stem}/{TEST_VIDEO.stem}_学习笔记.md")
        print()
        print("🔍 验证要点:")
        print("   1. 关键帧是否均匀分布（不是都在前面）")
        print("   2. 每个关键帧是否有「选择理由」")
        print("   3. 是否有「接下来 X 秒」的过渡说明")
        print("   4. Markdown 结构是否清晰无重复")
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
