#!/usr/bin/env python3
"""
Bot配置测试脚本

验证Bot配置是否正确，无需真正启动Bot

用法:
    python test_bot_config.py
"""

import sys
import json
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent
CONFIG_PATH = PROJECT_ROOT / "config" / "bot_config.json"

print("\n" + "=" * 70)
print("  Bot配置测试")
print("=" * 70)

# 1. 检查配置文件
print("\n1️⃣  检查配置文件")
print("-" * 70)

if CONFIG_PATH.exists():
    print(f"✅ 配置文件存在: {CONFIG_PATH}")
else:
    print(f"❌ 配置文件不存在: {CONFIG_PATH}")
    print(f"\n💡 请创建配置文件:")
    print(f"   1. cp config/bot_config.template.json config/bot_config.json")
    print(f"   2. 编辑 config/bot_config.json，填入Bot Token")
    sys.exit(1)

# 2. 读取配置
print("\n2️⃣  读取配置")
print("-" * 70)

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print("✅ 配置文件格式正确")
except Exception as e:
    print(f"❌ 配置文件格式错误: {e}")
    sys.exit(1)

# 3. 验证配置
print("\n3️⃣  验证配置")
print("-" * 70)

# 检查Bot Token
bot_token = config.get('bot_token', '')
if not bot_token or bot_token == 'YOUR_TELEGRAM_BOT_TOKEN':
    print("❌ Bot Token未配置")
    print("\n💡 请配置Bot Token:")
    print("   1. 打开 config/bot_config.json")
    print("   2. 将 \"YOUR_TELEGRAM_BOT_TOKEN\" 替换为你的Token")
    print("   3. 获取Token: https://t.me/BotFather")
    sys.exit(1)
else:
    print(f"✅ Bot Token已配置: {bot_token[:20]}...{bot_token[-10:]}")

# 检查其他配置
allowed_users = config.get('allowed_users', [])
print(f"✅ 允许的用户: {len(allowed_users)} 个 ({'所有用户' if len(allowed_users) == 0 else '限制用户'})")

proxy_url = config.get('proxy_url')
if proxy_url:
    print(f"✅ 代理配置: {proxy_url}")
else:
    print("✅ 无代理配置")

# 4. 测试Bot连接
print("\n4️⃣  测试Bot连接")
print("-" * 70)

try:
    import urllib.request
    import json as json_mod

    # 测试Bot API
    test_url = f"https://api.telegram.org/bot{bot_token}/getMe"

    print("📡 连接Telegram...")
    response = urllib.request.urlopen(test_url, timeout=10)
    data = json_mod.loads(response.read().decode('utf-8'))

    if data.get('ok'):
        bot_info = data.get('result', {})
        print("✅ Bot连接成功！")
        print(f"   Bot名称: @{bot_info.get('username', 'N/A')}")
        print(f"   Bot ID: {bot_info.get('id', 'N/A')}")
        print(f"   Bot名称: {bot_info.get('first_name', 'N/A')}")
    else:
        print(f"❌ Bot连接失败: {data.get('description', '未知错误')}")

except urllib.error.URLError as e:
    print(f"❌ 网络错误: {e}")
    print("\n💡 请检查:")
    print("   1. 网络连接是否正常")
    print("   2. Bot Token是否正确")
    print("   3. 是否需要代理")
except Exception as e:
    print(f"❌ 测试失败: {e}")

# 5. 检查依赖
print("\n5️⃣  检查依赖")
print("-" * 70)

try:
    import telegram
    print("✅ python-telegram-bot 已安装")
    print(f"   版本: {telegram.__version__}")
except ImportError:
    print("❌ python-telegram-bot 未安装")
    print("\n💡 请安装:")
    print("   pip install python-telegram-bot")

# 6. 总结
print("\n" + "=" * 70)
print("  测试完成")
print("=" * 70)

print("\n📝 下一步:")
print("\n1️⃣  如果所有测试通过，可以启动Bot:")
print("   python start_bot.py")

print("\n2️⃣  在Telegram中测试:")
print("   /start - 查看欢迎消息")
print("   /help - 查看帮助")
print("   /analyze <链接> - 测试分析功能")

print("\n3️⃣  查看详细文档:")
print("   docs/BOT_TESTING_GUIDE.md")

print("\n" + "=" * 70)
