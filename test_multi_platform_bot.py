#!/usr/bin/env python3
"""
测试多平台Bot配置

用法:
    python test_multi_platform_bot.py
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
BOT_FILE = PROJECT_ROOT / "bot" / "multi_platform_summary_bot.py"

print("\n" + "=" * 70)
print("  多平台Bot配置测试")
print("=" * 70)

# 测试1: 检查Bot文件存在
print("\n[1/4] 检查Bot文件...")
if BOT_FILE.exists():
    print(f"✅ Bot文件存在: {BOT_FILE}")
else:
    print(f"❌ Bot文件不存在: {BOT_FILE}")
    sys.exit(1)

# 测试2: 检查Bot文件语法
print("\n[2/4] 检查Bot文件语法...")
try:
    import ast
    with open(BOT_FILE, 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print("✅ Bot文件语法正确")
except SyntaxError as e:
    print(f"❌ Bot文件语法错误: {e}")
    sys.exit(1)

# 测试3: 读取配置
print("\n[3/4] 读取配置文件...")
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print("✅ 配置文件读取成功")
except Exception as e:
    print(f"❌ 配置文件读取失败: {e}")
    sys.exit(1)

# 测试4: 验证配置
print("\n[4/4] 验证配置...")

bot_token = config.get('bot_token', '')
if not bot_token:
    print("❌ Bot Token未配置")
    sys.exit(1)
print(f"✅ Bot Token: {bot_token[:20]}...{bot_token[-10:]}")

gemini_key = config.get('gemini_api_key', '')
if gemini_key:
    print(f"✅ Gemini API Key: {gemini_key[:20]}...{gemini_key[-10:]}")
else:
    print("⚠️  Gemini API Key未配置")

# 测试5: 测试Bot连接
print("\n[额外] 测试Bot连接...")
try:
    test_url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = urllib.request.urlopen(test_url, timeout=5)
    data = json.loads(response.read().decode('utf-8'))

    if data.get('ok'):
        bot_info = data.get('result', {})
        print("✅ Bot连接成功！")
        print(f"   Bot用户名: @{bot_info.get('username', 'N/A')}")
        print(f"   Bot名称: {bot_info.get('first_name', 'N/A')}")
        print(f"   Bot ID: {bot_info.get('id', 'N/A')}")

        # 检查URL检测逻辑
        print("\n[额外] 测试URL检测逻辑...")
        import re

        test_urls = [
            ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili", "video"),
            ("https://space.bilibili.com/3546607314274766", "bilibili", "user"),
            ("https://www.xiaohongshu.com/explore/12345", "xiaohongshu", "note"),
            ("https://www.xiaohongshu.com/user/profile/12345", "xiaohongshu", "user"),
        ]

        for url, expected_platform, expected_type in test_urls:
            # B站检测
            if 'bilibili.com' in url or 'b23.tv' in url:
                platform = 'bilibili'
                match = re.search(r'(BV[\w]+)', url, re.IGNORECASE)
                content_type = 'video' if match else 'user'
            # 小红书检测
            elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
                platform = 'xiaohongshu'
                if '/user/profile/' in url:
                    content_type = 'user'
                elif '/explore/' in url:
                    content_type = 'note'
                else:
                    content_type = 'note'
            else:
                platform = 'unknown'
                content_type = 'unknown'

            status = "✅" if (platform == expected_platform and content_type == expected_type) else "❌"
            print(f"   {status} {url}")
            print(f"      期望: {expected_platform}/{expected_type}, 实际: {platform}/{content_type}")

        print("\n" + "=" * 70)
        print("  ✅ 所有配置测试通过！")
        print("=" * 70)
        print("\n📝 下一步:")
        print("\n1️⃣  安装python-telegram-bot:")
        print("   pip install python-telegram-bot")
        print("\n2️⃣  启动Bot:")
        print("   python bot/multi_platform_summary_bot.py")
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
