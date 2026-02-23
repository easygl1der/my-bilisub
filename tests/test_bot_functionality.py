#!/usr/bin/env python3
"""
Bot功能完整性测试
"""

import sys
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent

print("\n" + "=" * 70)
print("  Bot 功能完整性测试")
print("=" * 70)

# 测试1: 检查Bot文件
print("\n[1/6] 检查Bot文件...")
bot_file = PROJECT_ROOT / "bot" / "video_summary_bot.py"
if bot_file.exists():
    print(f"✅ Bot文件存在: {bot_file.name}")
else:
    print(f"❌ Bot文件不存在: {bot_file.name}")
    sys.exit(1)

# 测试2: 检查Bot语法
print("\n[2/6] 检查Bot语法...")
try:
    import ast
    with open(bot_file, 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print("✅ Bot文件语法正确")
except SyntaxError as e:
    print(f"❌ Bot文件语法错误: {e}")
    sys.exit(1)

# 测试3: 检查配置文件
print("\n[3/6] 检查配置文件...")
config_file = PROJECT_ROOT / "config" / "telegram_config.json"
if config_file.exists():
    print(f"✅ 配置文件存在: {config_file.name}")
    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'bot_token' in config:
            token = config['bot_token']
            print(f"   Bot Token: {token[:20]}...{token[-10:]}")
        else:
            print("❌ 配置文件中缺少 bot_token")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 配置文件读取失败: {e}")
        sys.exit(1)
else:
    print(f"❌ 配置文件不存在: {config_file.name}")
    sys.exit(1)

# 测试4: 检查依赖脚本
print("\n[4/6] 检查依赖脚本...")
scripts = [
    ("小红书首页刷取", PROJECT_ROOT / "workflows" / "ai_xiaohongshu_homepage.py"),
    ("统一分析入口", PROJECT_ROOT / "utils" / "unified_content_analyzer.py"),
    ("B站首页刷取", PROJECT_ROOT / "workflows" / "ai_bilibili_homepage.py"),
]

all_scripts_ok = True
for name, script_path in scripts:
    if script_path.exists():
        print(f"✅ {name}: {script_path.name}")
    else:
        print(f"❌ {name}: {script_path.name} 不存在")
        all_scripts_ok = False

if not all_scripts_ok:
    print("⚠️ 部分脚本缺失，Bot功能可能受限")

# 测试5: 检查Cookie配置
print("\n[5/6] 检查Cookie配置...")
cookie_file = PROJECT_ROOT / "config" / "cookies.txt"
if cookie_file.exists():
    print(f"✅ Cookie文件存在: {cookie_file.name}")
    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'xiaohongshu' in content.lower():
        print("   ✅ 包含小红书Cookie配置")
    if 'bilibili' in content.lower():
        print("   ✅ 包含B站Cookie配置")
else:
    print(f"⚠️ Cookie文件不存在: {cookie_file.name}")
    print("   部分功能可能需要手动登录")

# 测试6: 链接识别测试
print("\n[6/6] 测试链接识别...")

def analyze_url(url: str) -> dict:
    """分析链接"""
    import re
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
    ("小红书笔记（discovery）", "https://www.xiaohongshu.com/discovery/item/69983ebb00000000150304d8", 'xiaohongshu', 'note'),
    ("小红书用户主页", "https://www.xiaohongshu.com/user/profile/5abcd123", 'xiaohongshu', 'user'),
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

# 总结
print("\n" + "=" * 70)
print("  测试总结")
print("=" * 70)

tests_passed = 0
total_tests = 6

if bot_file.exists():
    tests_passed += 1
if ast.parse(code):
    tests_passed += 1
if config_file.exists():
    tests_passed += 1
if all_scripts_ok:
    tests_passed += 1
if cookie_file.exists():
    tests_passed += 1
if link_test_passed == len(test_urls):
    tests_passed += 1

print(f"\n✅ 通过: {tests_passed}/{total_tests}")
print(f"❌ 失败: {total_tests - tests_passed}/{total_tests}")

if tests_passed == total_tests:
    print("\n🎉 所有测试通过！Bot已准备就绪。")
    print("\n📝 下一步:")
    print("   1. 启动Bot:")
    print("      python bot/video_summary_bot.py")
    print("   2. 在Telegram中找到你的Bot (@MyVideoAnalysis_bot)")
    print("   3. 发送 /start 开始使用")
    print("\n📖 可用命令:")
    print("   • 发送B站视频链接进行分析")
    print("   • 发送小红书笔记链接进行分析")
    print("   • /scrape_bilibili - 刷B站首页推荐")
    print("   • /scrape_xiaohongshu - 刷小红书推荐")
    print("   • /mode - 切换分析模式")
    print("   • /help - 查看帮助")
else:
    print("\n⚠️ 部分测试失败，请检查相关文件。")

print("\n" + "=" * 70 + "\n")
