#!/usr/bin/env python3
"""
快速启动Bot的脚本

用法:
    python start_bot.py
"""

import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("\n" + "=" * 70)
print("  多平台内容分析 Bot 启动器")
print("=" * 70)

# 检查配置
config_file = PROJECT_ROOT / "config" / "bot_config.json"
template_file = PROJECT_ROOT / "config" / "bot_config.template.json"

if not config_file.exists():
    print(f"\n⚠️ 配置文件不存在: {config_file}")
    print(f"\n📝 请按以下步骤配置:")

    if template_file.exists():
        print(f"\n1. 复制模板文件:")
        print(f"   cp {template_file} {config_file}")

    print(f"\n2. 编辑配置文件，填入你的 Telegram Bot Token:")
    print(f"   获取 Token: https://t.me/BotFather")

    print(f"\n3. 确保 Gemini API Key 已配置:")
    print(f"   环境变量: GEMINI_API_KEY")

    print(f"\n4. 然后重新运行此脚本")
    sys.exit(1)

# 检查依赖
print("\n📦 检查依赖...")

try:
    import telegram
    print("   ✅ python-telegram-bot")
except ImportError:
    print("   ❌ python-telegram-bot 未安装")
    print("\n请运行: pip install python-telegram-bot")
    sys.exit(1)

# 启动Bot
print("\n🚀 启动 Bot...")
print(f"📅 时间: {__import__('datetime').datetime.now()}")

try:
    from bot.multi_platform_bot import MultiPlatformBot

    bot = MultiPlatformBot()
    bot.run()

except KeyboardInterrupt:
    print("\n\n⚠️ Bot 已停止")
except Exception as e:
    print(f"\n❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
