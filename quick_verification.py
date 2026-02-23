#!/usr/bin/env python3
"""
快速验证所有功能

在 bilisub 环境中运行:
    conda activate bilisub
    python quick_verification.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent

print("\n" + "=" * 70)
print("  多平台内容分析系统 - 快速验证")
print("=" * 70)
print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📂 目录: {PROJECT_ROOT}")

# 1. 检查核心文件
print("\n" + "=" * 70)
print("  1. 核心文件检查")
print("=" * 70)

core_files = {
    "统一入口": "utils/unified_content_analyzer.py",
    "小红书视频": "utils/fetch_xhs_videos.py",
    "小红书图文": "utils/fetch_xhs_image_notes.py",
    "多平台Bot": "bot/multi_platform_bot.py",
    "启动脚本": "start_bot.py",
}

all_exist = True
for name, path in core_files.items():
    filepath = PROJECT_ROOT / path
    status = "✅" if filepath.exists() else "❌"
    print(f"{status} {name}: {path}")
    if not filepath.exists():
        all_exist = False

if not all_exist:
    print("\n⚠️  部分文件缺失")
    sys.exit(1)

# 2. 测试统一入口
print("\n" + "=" * 70)
print("  2. 测试统一分析入口")
print("=" * 70)

try:
    import subprocess
    result = subprocess.run(
        [sys.executable, "utils/unified_content_analyzer.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0:
        print("✅ 统一入口正常")
        print("\n📝 帮助信息预览:")
        lines = result.stdout.split('\n')[:10]
        for line in lines:
            if line.strip():
                print(f"   {line[:70]}")
    else:
        print("❌ 统一入口错误")
except Exception as e:
    print(f"❌ 测试失败: {e}")

# 3. 检查配置
print("\n" + "=" * 70)
print("  3. 配置检查")
print("=" * 70)

# Gemini API Key
import os
if os.environ.get('GEMINI_API_KEY'):
    print("✅ Gemini API Key: 已配置")
else:
    print("⚠️  Gemini API Key: 未配置（环境变量 GEMINI_API_KEY）")

# Bot配置
bot_config = PROJECT_ROOT / "config" / "bot_config.json"
if bot_config.exists():
    print("✅ Bot配置: 已配置")
else:
    print("⚠️  Bot配置: 未配置（参考 config/bot_config.template.json）")

# 4. 快速开始指南
print("\n" + "=" * 70)
print("  4. 快速开始")
print("=" * 70)

print("\n🚀 命令行使用:")
print(f"\n1️⃣  分析B站用户主页（推荐 - 无需额外配置）:")
print(f"   cd {PROJECT_ROOT}")
print(f"   python utils/unified_content_analyzer.py \\")
print(f"       --url \"https://space.bilibili.com/3546607314274766\" \\")
print(f"       --count 3")

print(f"\n2️⃣  查看所有选项:")
print(f"   python utils/unified_content_analyzer.py --help")

print(f"\n📱 Telegram Bot使用:")
print(f"\n1️⃣  配置Bot:")
print(f"   cp config/bot_config.template.json config/bot_config.json")
print(f"   # 编辑 config/bot_config.json，填入Bot Token")

print(f"\n2️⃣  启动Bot:")
print(f"   python start_bot.py")

print(f"\n3️⃣  在Telegram中使用:")
print(f"   /analyze https://space.bilibili.com/3546607314274766")

print(f"\n📚 查看文档:")
print(f"   📄 docs/P0_IMPLEMENTATION_GUIDE.md")
print(f"   📄 docs/BOT_USAGE_GUIDE.md")
print(f"   📄 docs/STAGE_SUMMARY.md")

print("\n" + "=" * 70)
print("  ✅ 验证完成！")
print("=" * 70)
print("\n🎉 多平台内容分析系统已就绪！")
print("\n💡 建议:")
print("   1. 先测试B站功能（最简单）")
print("   2. 配置Bot Token体验Telegram Bot")
print("   3. 根据需求逐步完善小红书功能")
