#!/usr/bin/env python3
"""
链接识别器测试版本（不依赖 Telegram）

直接在命令行测试链接识别功能
"""

import sys
import re
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class LinkAnalyzer:
    """链接分析器"""

    def __init__(self):
        self.patterns = {
            'bilibili': {
                'video': r'bilibili\.com/video/(BV[\w]+|av[\d]+)',
                'user': r'bilibili\.com/(space/|u/)?(\d+)',
                'user2': r'space\.bilibili\.com/(\d+)',
            },
            'xiaohongshu': {
                'note': r'xiaohongshu\.com/explore/([a-f0-9]+)',
                'user': r'xiaohongshu\.com/user/profile/([a-f0-9]+)',
            },
            'youtube': {
                'video': r'(youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
                'channel': r'youtube\.com/(channel/[\w-]+|c/[\w-]+|user/[\w-]+|@[\w-]+)',
            }
        }

    def analyze(self, url: str) -> dict:
        """分析链接，返回平台和类型"""
        url = url.strip()
        result = {
            'platform': 'unknown',
            'type': 'unknown',
            'id': '',
            'original_url': url
        }

        # B站
        if 'bilibili.com' in url or 'b23.tv' in url:
            result['platform'] = 'bilibili'
            video_match = re.search(self.patterns['bilibili']['video'], url)
            if video_match:
                result['type'] = 'video'
                result['id'] = video_match.group(1)
            else:
                user_match = re.search(self.patterns['bilibili']['user2'], url)
                if not user_match:
                    user_match = re.search(self.patterns['bilibili']['user'], url)
                if user_match:
                    result['type'] = 'user'
                    result['id'] = user_match.group(1)

        # 小红书
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            result['platform'] = 'xiaohongshu'
            note_match = re.search(self.patterns['xiaohongshu']['note'], url)
            if note_match:
                result['type'] = 'note'
                result['id'] = note_match.group(1)
            else:
                user_match = re.search(self.patterns['xiaohongshu']['user'], url)
                if user_match:
                    result['type'] = 'user'
                    result['id'] = user_match.group(1)

        # YouTube
        elif 'youtube.com' in url or 'youtu.be' in url:
            result['platform'] = 'youtube'
            video_match = re.search(self.patterns['youtube']['video'], url)
            if video_match:
                result['type'] = 'video'
                result['id'] = video_match.group(2)
            else:
                channel_match = re.search(self.patterns['youtube']['channel'], url)
                if channel_match:
                    result['type'] = 'channel'
                    result['id'] = channel_match.group(0)

        return result

    def format_result(self, result: dict) -> str:
        """格式化分析结果"""
        platform_emoji = {
            'bilibili': 'B站',
            'xiaohongshu': '小红书',
            'youtube': 'YouTube',
            'unknown': '未知'
        }

        type_text = {
            'video': '视频链接',
            'note': '笔记链接',
            'user': '用户主页',
            'channel': '频道主页',
            'unknown': '未知类型'
        }

        platform_name = platform_emoji.get(result['platform'], '未知')
        type_name = type_text.get(result['type'], '未知类型')

        lines = [
            "=" * 50,
            f"识别结果",
            "=" * 50,
            f"平台: {platform_name}",
            f"类型: {type_name}",
        ]

        if result['id']:
            lines.append(f"ID: {result['id']}")

        lines.append(f"原始链接: {result['original_url'][:60]}...")
        lines.append("=" * 50)

        return "\n".join(lines)


def main():
    """主函数 - 交互式测试"""
    print("\n" + "=" * 50)
    print("链接识别器测试")
    print("=" * 50)
    print("\n支持的平台:")
    print("  - B站 (视频/用户)")
    print("  - 小红书 (笔记/用户)")
    print("  - YouTube (视频/频道)")
    print("\n输入链接进行测试，输入 'q' 退出\n")

    analyzer = LinkAnalyzer()

    # 内置测试
    print("[运行内置测试...]")
    test_urls = [
        'https://www.bilibili.com/video/BV1xx411c7mD',
        'https://space.bilibili.com/123456',
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ',
        'https://www.youtube.com/@username',
        'https://xiaohongshu.com/explore/12345678abcd',
    ]

    all_passed = True
    for url in test_urls:
        result = analyzer.analyze(url)
        if result['platform'] == 'unknown':
            all_passed = False
            print(f"  ❌ 识别失败: {url}")
        else:
            print(f"  ✅ {result['platform']:10} {result['type']:10} - {url[:40]}")

    print(f"\n测试结果: {'全部通过' if all_passed else '部分失败'}")
    print("\n" + "-" * 50)

    # 交互式测试
    print("提示: 直接粘贴链接后按回车，输入 'q' 退出\n")

    while True:
        try:
            import sys
            # 刷新输出缓冲区
            sys.stdout.flush()

            user_input = input("请输入链接 (或 'q' 退出): ").strip()

            if not user_input:
                continue

            if user_input.lower() == 'q':
                print("\n再见!")
                break

            # 提取链接
            url_match = re.search(r'https?://[^\s]+', user_input)
            if not url_match:
                print("❌ 没有检测到有效的链接\n")
                continue

            url = url_match.group(0)
            result = analyzer.analyze(url)

            print("\n" + analyzer.format_result(result) + "\n")

        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except EOFError:
            print("\n\n检测到输入结束，退出程序")
            break
        except Exception as e:
            print(f"❌ 错误: {e}\n")


if __name__ == "__main__":
    main()
