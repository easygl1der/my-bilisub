#!/usr/bin/env python3
"""
最简单的Bot测试 - 只验证配置和连接

用法:
    python test_bot_simple.py
"""

import sys
import json
import urllib.request
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent
CONFIG_PATH = PROJECT_ROOT / "config" / "bot_config.json"

print("\n" + "=" * 70)
print("  Bot快速测试")
print("=" * 70)

# 读取配置
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
except Exception as e:
    print(f"❌ 配置文件读取失败: {e}")
    sys.exit(1)

# 获取Bot Token
bot_token = config.get('bot_token', '')
if not bot_token:
    print("❌ Bot Token未配置")
    sys.exit(1)

print(f"✅ Bot Token: {bot_token[:20]}...{bot_token[-10:]}")

# 获取Gemini API Key
gemini_key = config.get('gemini_api_key', '')
if gemini_key:
    print(f"✅ Gemini API Key: {gemini_key[:20]}...{gemini_key[-10:]}")
    # 设置到环境变量
    import os
    os.environ['GEMINI_API_KEY'] = gemini_key

# 测试Bot连接
try:
    test_url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = urllib.request.urlopen(test_url, timeout=5)
    data = json.loads(response.read().decode('utf-8'))

    if data.get('ok'):
        bot_info = data.get('result', {})
        print("\n✅ Bot连接成功！")
        print(f"   Bot名称: @{bot_info.get('username', 'N/A')}")
        print(f"   Bot名称: {bot_info.get('first_name', 'N/A')}")
        print(f"   Bot ID: {bot_info.get('id', 'N/A')}")

        print("\n" + "=" * 70)
        print("  ✅ 所有配置正确！")
        print("=" * 70)
        print("\n📝 下一步:")
        print("\n1️⃣  安装python-telegram-bot:")
        print("   pip install python-telegram-bot")
        print("\n2️⃣  启动Bot:")
        print("   python start_bot.py")
        print("\n3️⃣  或使用批处理脚本:")
        print("   start_bot_system.bat  (系统Python)")
        print("   start_bot_conda.bat   (conda环境)")

        sys.exit(0)
    else:
        print(f"❌ Bot连接失败: {data.get('description', '未知错误')}")
        sys.exit(1)

except Exception as e:
    print(f"❌ 测试失败: {e}")
    print("\n💡 请检查:")
    print("   1. 网络连接")
    print("   2. Bot Token是否正确")
    sys.exit(1)
