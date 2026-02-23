#!/usr/bin/env python3
"""
快速测试小红书首页刷取功能
"""

import sys
import asyncio
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent

print("\n" + "=" * 70)
print("  小红书首页刷取功能测试")
print("=" * 70)

# 测试1: 检查脚本文件
print("\n[1/4] 检查脚本文件...")
script_path = PROJECT_ROOT / "workflows" / "ai_xiaohongshu_homepage.py"
if script_path.exists():
    print(f"✅ 脚本文件存在: {script_path.name}")
else:
    print(f"❌ 脚本文件不存在: {script_path.name}")
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
    print(f"✅ Cookie文件存在: {cookie_file.name}")

    # 检查小红书Cookie
    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if '[xiaohongshu]' in content:
        print("   ✅ 找到 [xiaohongshu] 配置段")

        # 提取关键Cookie值
        import re
        a1_match = re.search(r'a1=([^\n]+)', content)
        if a1_match:
            a1_value = a1_match.group(1).strip()
            if a1_value and a1_value != '你的a1值':
                print(f"   ✅ a1 Cookie已配置: {a1_value[:20]}...{a1_value[-10:]}")
            else:
                print("   ⚠️  a1 Cookie未配置")
        else:
            print("   ⚠️  未找到 a1 Cookie")

        web_session_match = re.search(r'web_session=([^\n]+)', content)
        if web_session_match:
            web_session_value = web_session_match.group(1).strip()
            if web_session_value and web_session_value != '你的web_session':
                print(f"   ✅ web_session Cookie已配置")
            else:
                print("   ⚠️  web_session Cookie未配置")

        webId_match = re.search(r'webId=([^\n]+)', content)
        if webId_match:
            webId_value = webId_match.group(1).strip()
            if webId_value and webId_value != '你的webId':
                print(f"   ✅ webId Cookie已配置")
            else:
                print("   ⚠️  webId Cookie未配置")
    else:
        print("   ⚠️  未找到 [xiaohongshu] 配置段")
else:
    print(f"❌ Cookie文件不存在: {cookie_file.name}")

# 测试4: 检查输出目录
print("\n[4/4] 检查输出目录...")
output_dir = PROJECT_ROOT / "output" / "xiaohongshu_homepage"
if output_dir.exists():
    print(f"✅ 输出目录存在: {output_dir}")
else:
    print(f"📁 输出目录不存在，将自动创建: {output_dir}")

# 总结
print("\n" + "=" * 70)
print("  测试总结")
print("=" * 70)

print("\n✅ 所有关键文件和配置检查完成！")
print("\n📝 下一步:")
print("   1. 运行完整测试（小规模）:")
print("      python ai_xiaohongshu_homepage.py --refresh-count 1 --max-notes 10")
print()
print("   2. 或通过Bot测试:")
print("      /scrape_xiaohongshu 1 10")
print()
print("   3. 或启动Bot:")
print("      python bot/video_summary_bot.py")
print()

print("=" * 70)
print("\n💡 提示:")
print("   - 首次运行会自动登录（如果Cookie有效）")
print("   - 推荐首次使用小规模测试（1次刷新，10个笔记）")
print("   - 确保网络连接正常")
print("   - 如遇到登录问题，请在浏览器窗口中手动登录")
print()

# 询问是否运行快速测试
response = input("\n是否运行快速测试（1次刷新，10个笔记）？[y/N]: ").strip().lower()

if response == 'y':
    print("\n" + "=" * 70)
    print("  开始快速测试...")
    print("=" * 70)
    print()

    import subprocess
    cmd = [
        sys.executable,
        str(script_path),
        "--mode", "full",
        "--refresh-count", "1",
        "--max-notes", "10"
    ]

    print(f"执行命令: {' '.join(cmd)}")
    print()

    try:
        subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 测试失败，返回码: {e.returncode}")
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
else:
    print("\n跳过快速测试。")
