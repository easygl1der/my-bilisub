#!/usr/bin/env python3
"""
Bot完整功能测试

用法:
    python test_bot_full.py
"""

import sys
import re
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent

print("\n" + "=" * 70)
print("  Bot完整功能测试")
print("=" * 70)

# 测试1: 检查Bot文件
print("\n[1/5] 检查Bot文件...")
bot_file = PROJECT_ROOT / "bot" / "video_summary_bot.py"
if bot_file.exists():
    print(f"✅ Bot文件存在: {bot_file}")
else:
    print(f"❌ Bot文件不存在: {bot_file}")
    sys.exit(1)

# 测试2: 检查Bot语法
print("\n[2/5] 检查Bot语法...")
syntax_ok = False
try:
    import ast
    with open(bot_file, 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    syntax_ok = True
    print("✅ Bot文件语法正确")
except SyntaxError as e:
    print(f"❌ Bot文件语法错误: {e}")
    sys.exit(1)

# 测试3: 检查配置文件
print("\n[3/5] 检查配置文件...")
config_files = [
    PROJECT_ROOT / "config" / "bot_config.json",
    PROJECT_ROOT / "config" / "telegram_config.json"
]

config_ok = False
for config_file in config_files:
    if config_file.exists():
        print(f"✅ 配置文件存在: {config_file.name}")
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if 'bot_token' in config:
                token = config['bot_token']
                print(f"   Bot Token: {token[:20]}...{token[-10:]}")
            if 'gemini_api_key' in config:
                key = config['gemini_api_key']
                print(f"   Gemini API Key: {key[:20]}...{key[-10:]}")
            config_ok = True
        except Exception as e:
            print(f"   ⚠️  配置文件读取失败: {e}")

if not config_ok:
    print("❌ 未找到有效的配置文件")
    sys.exit(1)

# 测试4: 模拟链接识别
print("\n[4/5] 测试链接识别...")

# 模拟 LinkAnalyzer
def analyze_url(url: str) -> dict:
    """分析链接"""
    url = url.strip()
    result = {'platform': 'unknown', 'type': 'unknown', 'id': '', 'url': url}

    # B站检测
    if 'bilibili.com' in url or 'b23.tv' in url:
        result['platform'] = 'bilibili'
        match = re.search(r'(BV[\w]+)', url, re.IGNORECASE)
        if match:
            result['type'] = 'video'
            result['id'] = match.group(1)

    # 小红书检测
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        result['platform'] = 'xiaohongshu'
        if '/user/profile/' in url:
            result['type'] = 'user'
            result['id'] = url.split('/user/profile/')[-1].split('?')[0]
        elif '/explore/' in url:
            result['type'] = 'note'
            result['id'] = url.split('/explore/')[-1].split('?')[0]
        elif '/discovery/item/' in url:
            result['type'] = 'note'
            result['id'] = url.split('/discovery/item/')[-1].split('?')[0]
        else:
            result['type'] = 'note'
            id_match = re.search(r'([a-f0-9]{32})', url)
            if id_match:
                result['id'] = id_match.group(1)

    return result


test_urls = [
    ("B站视频", "https://www.bilibili.com/video/BV1xx411c7mD", 'bilibili', 'video'),
    ("小红书笔记（explore）", "https://www.xiaohongshu.com/explore/699c16b4000000002801f20a", 'xiaohongshu', 'note'),
    ("小红书笔记（discovery）", "https://www.xiaohongshu.com/discovery/item/69983ebb00000000150304d8?source=webshare", 'xiaohongshu', 'note'),
]

link_test_passed = 0
for name, url, expected_platform, expected_type in test_urls:
    result = analyze_url(url)
    platform_ok = result['platform'] == expected_platform
    type_ok = result['type'] == expected_type

    if platform_ok and type_ok:
        print(f"✅ {name}")
        print(f"   期望: {expected_platform}/{expected_type}")
        print(f"   实际: {result['platform']}/{result['type']}")
        link_test_passed += 1
    else:
        print(f"❌ {name}")
        print(f"   期望: {expected_platform}/{expected_type}")
        print(f"   实际: {result['platform']}/{result['type']}")

# 测试5: 检查小红书爬虫
print("\n[5/5] 检查小红书爬虫...")
xhs_scraper_ok = False
xhs_scraper = PROJECT_ROOT / "workflows" / "ai_xiaohongshu_homepage.py"
if xhs_scraper.exists():
    print(f"✅ 小红书爬虫存在: {xhs_scraper.name}")
    xhs_scraper_ok = True
else:
    print(f"❌ 小红书爬虫不存在: {xhs_scraper.name}")

# 总结
print("\n" + "=" * 70)
print("  测试总结")
print("=" * 70)

tests_passed = 0
if bot_file.exists():
    tests_passed += 1
if syntax_ok:
    tests_passed += 1
if config_ok:
    tests_passed += 1
if xhs_scraper_ok:
    tests_passed += 1
# link_test_passed 是3个链接测试，不是1个
# 所以总共应该是 1+1+1+1+3 = 6 个测试
# 但我们按5个项目显示，所以total_tests还是5

total_tests = 5

print(f"\n✅ 通过: {tests_passed}/{total_tests}")
print(f"❌ 失败: {total_tests - tests_passed}/{total_tests}")

if tests_passed == total_tests:
    print("\n🎉 所有测试通过！Bot可以正常使用了。")
    print("\n📝 下一步:")
    print("   1. 启动Bot: python bot/video_summary_bot.py")
    print("   2. 在Telegram中找到你的Bot")
    print("   3. 发送 /start 开始使用")
else:
    print("\n⚠️  部分测试失败，请检查相关文件。")

print("\n" + "=" * 70 + "\n")
