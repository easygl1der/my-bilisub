#!/usr/bin/env python3
"""
测试脚本：验证字幕提取和AI总结是否正常工作
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 60)
print("测试字幕提取和AI总结")
print("=" * 60)

# 测试1: 检查字幕提取脚本
print("\n[测试1] 检查字幕提取脚本...")
batch_fetch = Path(__file__).parent.parent / "utils" / "batch_subtitle_fetch.py"
if batch_fetch.exists():
    print(f"✅ 字幕提取脚本存在: {batch_fetch}")
else:
    print(f"❌ 字幕提取脚本不存在: {batch_fetch}")

# 测试2: 检查 Gemini API
print("\n[测试2] 检查 Gemini API...")
try:
    from analysis.gemini_subtitle_summary import GeminiClient, get_api_key
    api_key = get_api_key()
    if api_key:
        print(f"✅ Gemini API Key 存在: {api_key[:10]}...{api_key[-10:]}")

        # 测试调用
        client = GeminiClient(model='flash-lite')
        result = client.generate_content("请简单回复：测试成功")
        if result['success']:
            print(f"✅ Gemini API 调用成功!")
            print(f"   回复: {result['text'][:50]}...")
        else:
            print(f"❌ Gemini API 调用失败: {result.get('error')}")
    else:
        print("❌ 未找到 Gemini API Key")
        print("   请设置 config_api.py 中的 GEMINI_API_KEY")
except Exception as e:
    print(f"❌ Gemini API 测试失败: {e}")

# 测试3: 检查配置文件
print("\n[测试3] 检查配置文件...")
cookie_file = Path(__file__).parent.parent / "config" / "cookies_bilibili_api.txt"
if cookie_file.exists():
    print(f"✅ B站 Cookie 文件存在")
else:
    print(f"❌ B站 Cookie 文件不存在: {cookie_file}")
    print("   字幕提取需要这个文件")

telegram_config = Path(__file__).parent.parent / "config" / "telegram_config.json"
if telegram_config.exists():
    print(f"✅ Telegram 配置文件存在")
    import json
    with open(telegram_config, 'r') as f:
        config = json.load(f)
        print(f"   Bot Token: {config.get('bot_token', 'N/A')[:20]}...")
else:
    print(f"❌ Telegram 配置文件不存在")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
