#!/usr/bin/env python3
"""
一键安装依赖并启动Bot

用法:
    python install_and_start_bot.py
"""

import sys
import subprocess
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent

print("\n" + "=" * 70)
print("  Bot一键安装和启动")
print("=" * 70)

# 步骤1: 安装依赖
print("\n📦 步骤 1/2: 安装依赖")
print("-" * 70)

try:
    print("正在安装 python-telegram-bot...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "python-telegram-bot"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ 安装成功！")
    else:
        print(f"⚠️  安装可能有问题：{result.stderr[-100:]}")
        print("尝试继续启动Bot...")

except Exception as e:
    print(f"❌ 安装失败: {e}")
    print("\n💡 请手动安装:")
    print("   pip install python-telegram-bot")
    input("\n按Enter继续...")

# 步骤2: 启动Bot
print("\n🚀 步骤 2/2: 启动Bot")
print("-" * 70)
print("正在启动Bot...")
print("按 Ctrl+C 停止Bot\n")

try:
    # 导入并启动Bot
    sys.path.insert(0, str(PROJECT_ROOT))
    from bot.multi_platform_bot import MultiPlatformBot

    print("✅ Bot模块导入成功")
    print("🔧 正在初始化Bot...")

    bot = MultiPlatformBot()
    print("✅ Bot初始化成功")
    print("🚀 开始运行Bot...")
    print("=" * 70)

    bot.run()

except KeyboardInterrupt:
    print("\n\n⚠️  Bot 已停止")
except ImportError as e:
    print(f"\n❌ 导入失败: {e}")
    print("\n💡 请确保已安装 python-telegram-bot:")
    print("   pip install python-telegram-bot")
    import traceback
    print("\n详细错误:")
    traceback.print_exc()
except Exception as e:
    print(f"\n❌ 启动失败: {e}")
    print(f"   错误类型: {type(e).__name__}")

    # 显示详细错误
    import traceback
    print("\n详细错误:")
    traceback.print_exc()

    print("\n💡 故障排除:")
    print("   1. 检查配置文件: config/bot_config.json")
    print("   2. 测试配置: python test_bot_config.py")
    print("   3. 查看文档: docs/BOT_TESTING_GUIDE.md")

    input("\n按Enter退出...")
