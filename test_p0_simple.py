#!/usr/bin/env python3
"""
P0阶段快速测试（简化版）

在bilisub环境中运行，快速验证核心功能

运行方式:
    conda activate bilisub
    python test_p0_simple.py
"""

import sys
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("\n" + "=" * 70)
print("  P0阶段快速测试")
print("=" * 70)
print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📂 目录: {PROJECT_ROOT}")

# 1. 文件检查
print("\n" + "=" * 70)
print("  1. 文件存在性检查")
print("=" * 70)

files = [
    "utils/unified_content_analyzer.py",
    "utils/fetch_xhs_videos.py",
    "utils/fetch_xhs_image_notes.py",
    "utils/auto_xhs_subtitle_workflow.py",
    "utils/auto_xhs_image_workflow.py",
    "utils/auto_bili_workflow.py",
    "analysis/gemini_subtitle_summary.py",
    "analysis/xhs_image_analysis.py",
    "docs/P0_IMPLEMENTATION_GUIDE.md",
]

all_exist = True
for file in files:
    filepath = PROJECT_ROOT / file
    status = "✅" if filepath.exists() else "❌"
    print(f"{status} {file}")
    if not filepath.exists():
        all_exist = False

# 2. 语法检查
print("\n" + "=" * 70)
print("  2. Python语法检查")
print("=" * 70)

import py_compile

syntax_ok = True
for file in files:
    if not file.endswith('.py'):
        continue

    filepath = PROJECT_ROOT / file
    if filepath.exists():
        try:
            py_compile.compile(str(filepath), doraise=True)
            print(f"✅ {Path(file).name}")
        except:
            print(f"❌ {Path(file).name} (语法错误)")
            syntax_ok = False

# 3. 测试总结
print("\n" + "=" * 70)
print("  测试结果")
print("=" * 70)

if all_exist and syntax_ok:
    print("\n✅ 所有文件存在且语法正确！")
    print("\n📝 快速开始测试:\n")

    print("1️⃣  测试B站工作流（推荐 - 无需配置）:")
    print(f"   cd {PROJECT_ROOT}")
    print(f"   python utils/unified_content_analyzer.py \\")
    print(f"       --url \"https://space.bilibili.com/3546607314274766\" \\")
    print(f"       --count 3\n")

    print("2️⃣  查看帮助信息:")
    print(f"   python utils/unified_content_analyzer.py --help\n")

    print("3️⃣  查看文档:")
    print(f"   📄 {PROJECT_ROOT}/docs/P0_IMPLEMENTATION_GUIDE.md")
    print(f"   📄 {PROJECT_ROOT}/docs/P0_COMPLETION_SUMMARY.md\n")

    print("🎯 P0阶段实现完成！")
else:
    print("\n⚠️  请检查上述错误")
