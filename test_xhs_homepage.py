#!/usr/bin/env python3
"""
测试小红书首页刷取功能

用法:
    python test_xhs_homepage.py
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
print("  小红书首页刷取功能测试")
print("=" * 70)

# 测试1: 检查脚本文件
print("\n[1/4] 检查脚本文件...")
script_path = PROJECT_ROOT / "ai_xiaohongshu_homepage.py"
if script_path.exists():
    print(f"✅ 脚本文件存在: {script_path}")
else:
    print(f"❌ 脚本文件不存在: {script_path}")
    sys.exit(1)

# 测试2: 检查脚本语法
print("\n[2/4] 检查脚本语法...")
try:
    import ast
    with open(script_path, 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print("✅ 脚本语法正确")
except SyntaxError as e:
    print(f"❌ 脚本语法错误: {e}")
    sys.exit(1)

# 测试3: 检查Cookie配置
print("\n[3/4] 检查Cookie配置...")
cookie_file = PROJECT_ROOT / "config" / "cookies.txt"
if cookie_file.exists():
    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookie_content = f.read()

    # 检查是否包含小红书Cookie
    if 'xhs_uid' in cookie_content or 'a1=' in cookie_content:
        print("✅ Cookie文件包含小红书Cookie")
    else:
        print("⚠️  Cookie文件存在但未找到小红书Cookie")
        print("💡 请确保cookies.txt包含小红书的Cookie (xhs_uid, a1等)")
else:
    print("⚠️  Cookie文件不存在")
    print("💡 请先在浏览器中登录小红书，然后导出Cookie")

# 测试4: 检查输出目录
print("\n[4/4] 检查输出目录...")
output_dir = PROJECT_ROOT / "output" / "xiaohongshu_homepage"
if output_dir.exists():
    print(f"✅ 输出目录存在: {output_dir}")
else:
    print(f"⚠️  输出目录不存在，将自动创建: {output_dir}")

print("\n" + "=" * 70)
print("  测试完成")
print("=" * 70)

print("\n📝 下一步:")
print("\n1️⃣  确保小红书Cookie已配置（config/cookies.txt）")
print("   如果没有Cookie，请:")
print("   a. 在浏览器中登录小红书")
print("   b. 按F12打开开发者工具")
print("   c. 找到Cookie并复制到config/cookies.txt")
print("\n2️⃣  运行小红书首页刷取:")
print("   python ai_xiaohongshu_homepage.py")
print("\n3️⃣  或在Bot中使用:")
print("   /scrape_xiaohongshu 3 50")
print("\n💡 首次运行时，浏览器窗口会打开，你可以:")
print("   • 手动登录小红书（如果Cookie无效）")
print("   • 查看采集过程")
print("   • 等待自动完成")
