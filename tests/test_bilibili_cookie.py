#!/usr/bin/env python3
"""
测试B站Cookie是否有效
"""

import sys
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

import httpx

# 读取Cookie
def read_bilibili_cookie():
    cookie_file = Path(__file__).parent / "config" / "cookies.txt"
    if not cookie_file.exists():
        print("❌ Cookie文件不存在")
        return ""

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 [bilibili] 部分
    in_bilibili_section = False
    cookies = {}
    for line in content.split('\n'):
        line = line.strip()
        if line == '[bilibili]':
            in_bilibili_section = True
            continue
        elif line.startswith('['):
            in_bilibili_section = False
            continue
        elif in_bilibili_section and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            cookies[key.strip()] = value.strip()

    # 优先使用 bilibili_full
    if 'bilibili_full' in cookies:
        return cookies['bilibili_full']

    # 否则构建Cookie字符串
    return '; '.join([f"{k}={v}" for k, v in cookies.items() if not k.endswith('_full')])

async def test_cookie():
    cookie_str = read_bilibili_cookie()

    if not cookie_str:
        print("❌ Cookie为空")
        return

    print(f"🍪 Cookie长度: {len(cookie_str)} 字符")
    print(f"   前50字符: {cookie_str[:50]}...")
    print()

    # 测试API调用
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
        "Cookie": cookie_str
    }

    print("🔍 测试登录状态...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.bilibili.com/x/web-interface/nav",
                headers=headers
            )

            data = response.json()

            if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                print("✅ Cookie有效！登录状态：已登录")
                user_data = data.get("data", {})
                if user_data.get("uname"):
                    print(f"   用户名: {user_data.get('uname')}")
                if user_data.get("mid"):
                    print(f"   用户ID: {user_data.get('mid')}")
            else:
                print("❌ Cookie无效或已过期")
                print(f"   API返回: {data}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cookie())
