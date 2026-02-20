#!/usr/bin/env python3
"""
统一 Cookie 管理器

所有程序通过这个模块读取 Cookie，只需要在 config/cookies.txt 中更新一次即可。

使用方法:
    from cookie_manager import get_cookie

    # 获取小红书 cookie（字符串格式，用于请求头）
    xhs_cookie = get_cookie('xiaohongshu')

    # 获取小红书 cookie（字典格式）
    xhs_dict = get_cookie_dict('xiaohongshu')

    # 获取单个 cookie 值
    a1 = get_cookie_value('xiaohongshu', 'a1')
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# 配置文件路径（从 bot/ 目录需要回到父目录的 config/）
COOKIE_FILE = Path(__file__).parent.parent / "config" / "cookies.txt"


class CookieManager:
    """Cookie 管理器"""

    def __init__(self, cookie_file: Path = None):
        self.cookie_file = cookie_file or COOKIE_FILE
        self._cookies = {}
        self._load_cookies()

    def _load_cookies(self):
        """从配置文件加载 cookies"""
        if not self.cookie_file.exists():
            print(f"⚠️ Cookie 配置文件不存在: {self.cookie_file}")
            print(f"   请创建此文件并添加 Cookie")
            return

        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析配置文件
            current_section = None
            for line in content.split('\n'):
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue

                # 检测节 [section]
                section_match = re.match(r'\[([^\]]+)\]', line)
                if section_match:
                    current_section = section_match.group(1)
                    self._cookies[current_section] = {}
                    continue

                # 解析 key=value
                if '=' in line and current_section:
                    key, value = line.split('=', 1)
                    self._cookies[current_section][key.strip()] = value.strip()

        except Exception as e:
            print(f"⚠️ 读取 Cookie 配置文件失败: {e}")

    def get_cookie(self, platform: str, format_type: str = 'dict') -> Optional[str]:
        """
        获取指定平台的 Cookie

        Args:
            platform: 平台名称 (xiaohongshu, bilibili, youtube)
            format_type: 返回格式
                - 'dict': 字典格式
                - 'string': 字符串格式 (key1=value1; key2=value2)
                - 'header': 请求头格式

        Returns:
            Cookie 字符串或字典
        """
        if platform not in self._cookies:
            print(f"⚠️ 未找到平台 '{platform}' 的 Cookie 配置")
            print(f"   请在 {self.cookie_file} 中添加 [{platform}] 配置")
            return None

        cookies = self._cookies[platform]

        # 检查是否有 full 格式的 cookie
        full_key = f"{platform}_full"
        if full_key in cookies and format_type in ('string', 'header'):
            return cookies[full_key]

        # 手动构建 cookie 字符串
        if format_type in ('string', 'header'):
            return '; '.join([f"{k}={v}" for k, v in cookies.items() if not k.endswith('_full')])

        return cookies

    def get_cookie_dict(self, platform: str) -> Dict[str, str]:
        """获取 Cookie 字典"""
        result = self.get_cookie(platform, 'dict')
        return result if result else {}

    def get_cookie_value(self, platform: str, key: str) -> Optional[str]:
        """获取单个 Cookie 值"""
        cookies = self.get_cookie_dict(platform)
        return cookies.get(key)

    def is_valid(self, platform: str) -> bool:
        """检查 Cookie 是否有效（是否已配置）"""
        if platform not in self._cookies:
            return False

        cookies = self._cookies[platform]
        if not cookies:
            return False

        # 检查是否有有效的 cookie 值
        for key, value in cookies.items():
            if value and value.strip():
                return True

        return False

    def check_and_warn(self, platform: str) -> bool:
        """检查 Cookie 并在无效时警告"""
        if not self.is_valid(platform):
            print(f"\n{'='*60}")
            print(f"⚠️  {platform.upper()} Cookie 未配置或已过期！")
            print(f"{'='*60}")
            print(f"请按以下步骤更新 Cookie：")
            print(f"1. 打开 config/cookies.txt 文件")
            print(f"2. 找到 [{platform}] 部分")
            print(f"3. 更新对应的 Cookie 值")
            print(f"4. 保存文件后重试")
            print(f"{'='*60}\n")
            return False
        return True

    def reload(self):
        """重新加载 Cookie"""
        self._cookies = {}
        self._load_cookies()


# 全局实例
_manager = None


def get_manager() -> CookieManager:
    """获取 Cookie 管理器实例"""
    global _manager
    if _manager is None:
        _manager = CookieManager()
    return _manager


def get_cookie(platform: str, format_type: str = 'string') -> Optional[str]:
    """
    获取指定平台的 Cookie（便捷函数）

    Args:
        platform: 平台名称 (xiaohongshu, bilibili, youtube)
        format_type: 返回格式 (dict, string, header)

    Returns:
        Cookie 字符串或字典
    """
    manager = get_manager()
    return manager.get_cookie(platform, format_type)


def get_cookie_dict(platform: str) -> Dict[str, str]:
    """获取 Cookie 字典（便捷函数）"""
    manager = get_manager()
    return manager.get_cookie_dict(platform)


def get_cookie_value(platform: str, key: str) -> Optional[str]:
    """获取单个 Cookie 值（便捷函数）"""
    manager = get_manager()
    return manager.get_cookie_value(platform, key)


def check_cookie(platform: str) -> bool:
    """检查 Cookie 是否有效（便捷函数）"""
    manager = get_manager()
    return manager.check_and_warn(platform)


def reload_cookies():
    """重新加载 Cookie（便捷函数）"""
    manager = get_manager()
    manager.reload()


# 测试代码
if __name__ == "__main__":
    print("="*60)
    print("🧪 Cookie 管理器测试")
    print("="*60)

    manager = CookieManager()

    # 测试小红书
    print("\n📱 小红书 Cookie:")
    xhs_cookie = manager.get_cookie('xiaohongshu', 'string')
    if xhs_cookie:
        print(f"✅ 已加载 (长度: {len(xhs_cookie)} 字符)")
        print(f"   内容: {xhs_cookie[:50]}...")
    else:
        print("❌ 未配置")

    # 测试单个值
    a1 = manager.get_cookie_value('xiaohongshu', 'a1')
    if a1:
        print(f"   a1: {a1[:20]}...")

    # 检查有效性
    print("\n🔍 Cookie 状态检查:")
    for platform in ['xiaohongshu', 'bilibili', 'youtube']:
        status = "✅ 有效" if manager.is_valid(platform) else "❌ 未配置"
        print(f"   {platform}: {status}")

    print("\n" + "="*60)
    print("✅ 测试完成！")
    print(f"💡 提示: 所有 Cookie 都在 {COOKIE_FILE} 中统一管理")
    print("="*60)
