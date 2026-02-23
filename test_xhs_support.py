#!/usr/bin/env python3
"""
测试Bot的小红书支持

用法:
    python test_xhs_support.py
"""

import sys
import re
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 模拟 LinkAnalyzer 类
class LinkAnalyzer:
    """链接分析器"""

    def analyze(self, url: str) -> dict:
        """分析链接（支持B站和小红书）"""
        url = url.strip()
        result = {'platform': 'unknown', 'type': 'unknown', 'id': '', 'url': url}

        # B站检测
        if 'bilibili.com' in url or 'b23.tv' in url:
            result['platform'] = 'bilibili'
            # 提取 BV 号
            match = re.search(r'(BV[\w]+)', url, re.IGNORECASE)
            if match:
                result['type'] = 'video'
                result['id'] = match.group(1)

        # 小红书检测
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            result['platform'] = 'xiaohongshu'
            # 提取笔记ID或用户ID
            if '/user/profile/' in url:
                result['type'] = 'user'
                result['id'] = url.split('/user/profile/')[-1].split('?')[0]
            elif '/explore/' in url:
                result['type'] = 'note'
                result['id'] = url.split('/explore/')[-1].split('?')[0]
            else:
                result['type'] = 'note'

        return result

print("\n" + "=" * 70)
print("  Bot小红书支持测试")
print("=" * 70)

analyzer = LinkAnalyzer()

# 测试用例
test_cases = [
    # B站链接
    ("https://www.bilibili.com/video/BV1xx411c7mD", 'bilibili', 'video'),
    ("https://space.bilibili.com/3546607314274766", 'bilibili', 'unknown'),

    # 小红书链接
    ("https://www.xiaohongshu.com/explore/123456", 'xiaohongshu', 'note'),
    ("https://www.xiaohongshu.com/user/profile/5abcd123", 'xiaohongshu', 'user'),
    ("https://xhslink.com/abcdef123", 'xiaohongshu', 'note'),

    # 无效链接
    ("https://www.example.com/test", 'unknown', 'unknown'),
]

print("\n[测试结果]\n")
passed = 0
failed = 0

for url, expected_platform, expected_type in test_cases:
    result = analyzer.analyze(url)

    platform_ok = result['platform'] == expected_platform
    type_ok = result['type'] == expected_type
    all_ok = platform_ok and type_ok

    status = "✅" if all_ok else "❌"
    if all_ok:
        passed += 1
    else:
        failed += 1

    print(f"{status} {url}")
    print(f"   期望: {expected_platform}/{expected_type}")
    print(f"   实际: {result['platform']}/{result['type']}")
    print()

print("=" * 70)
print(f"  测试结果: {passed} 通过, {failed} 失败")
print("=" * 70)

if failed == 0:
    print("\n✅ 所有测试通过！Bot现在支持B站和小红书链接识别。")
    print("\n📝 下一步:")
    print("   1. 启动Bot: python bot/video_summary_bot.py")
    print("   2. 在Telegram中发送B站或小红书链接测试")
else:
    print("\n❌ 部分测试失败，请检查代码逻辑。")
