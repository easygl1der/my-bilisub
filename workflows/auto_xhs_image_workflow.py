#!/usr/bin/env python3
"""
小红书图文分析工作流

自动流程：
1. 下载小红书笔记的图片和文案
2. 使用 AI 分析笔记内容

用法: python auto_xhs_image_workflow.py "小红书笔记链接"
"""

import sys
import subprocess
import argparse
from pathlib import Path

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

DOWNLOAD_SCRIPT = PROJECT_ROOT / "platforms" / "xiaohongshu" / "download_xhs_images.py"
ANALYSIS_SCRIPT = PROJECT_ROOT / "analysis" / "xhs_image_analysis.py"


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书图文分析工作流（下载 + AI 分析）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    python auto_xhs_image_workflow.py "小红书笔记链接"
    python auto_xhs_image_workflow.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx" --model flash-lite
        """
    )

    parser.add_argument('url', help='小红书笔记完整链接（必须包含 xsec_token）')
    parser.add_argument('-m', '--model',
                       choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite',
                       help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--upload-github', action='store_true',
                       help='上传图片到 GitHub CDN')

    args = parser.parse_args()

    # 检查脚本是否存在
    if not DOWNLOAD_SCRIPT.exists():
        print(f"❌ 找不到下载脚本: {DOWNLOAD_SCRIPT}")
        sys.exit(1)

    if not ANALYSIS_SCRIPT.exists():
        print(f"❌ 找不到分析脚本: {ANALYSIS_SCRIPT}")
        sys.exit(1)

    print("\n" + "="*80)
    print("📸 小红书图文分析工作流")
    print("="*80)

    # 步骤1: 下载图片
    print("\n" + "="*80)
    print("步骤 1/2: 下载笔记图片和文案")
    print("="*80)

    # 修改 subprocess.run 以捕获输出
    cmd = [sys.executable, str(DOWNLOAD_SCRIPT), args.url]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding='utf-8')

    # 打印下载脚本的输出
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print("\n❌ 下载失败!")
        sys.exit(1)

    # 从输出中提取下载目录路径
    # download_xhs_images.py 最后一行会打印: "位置: /path/to/xhs_images/用户名/笔记标题"
    note_dir = None
    for line in result.stdout.split('\n'):
        if line.strip().startswith('位置:'):
            note_dir = line.strip()[3:].strip()
            break

    if not note_dir:
        print("\n⚠️ 无法从输出中提取下载目录，将尝试使用 URL 方式")
        # 降级方案：使用 URL（会重复下载）
        cmd = [sys.executable, str(ANALYSIS_SCRIPT), "--url", args.url, "--model", args.model]
    else:
        # 步骤2: 分析笔记
        print("\n" + "="*80)
        print("步骤 2/2: AI 分析笔记内容")
        print("="*80)

        # 使用 --dir 参数指定已下载的目录，避免重复下载
        cmd = [sys.executable, str(ANALYSIS_SCRIPT), "--dir", note_dir, "--model", args.model]

    if args.upload_github:
        cmd.append("--upload-github")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("\n❌ 分析失败!")
        sys.exit(1)

    print("\n" + "="*80)
    print("✅ 全部完成!")
    print("="*80)


if __name__ == "__main__":
    main()
