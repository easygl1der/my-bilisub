#!/usr/bin/env python3
"""
小红书作者信息提取工具

功能：从小红书笔记链接提取作者信息
- 用户昵称
- 用户 ID
- 用户主页链接

使用方法：
    python extract_xhs_author.py "小红书笔记链接"

示例：
    python extract_xhs_author.py "https://www.xiaohongshu.com/explore/66fad51c00000001b0224b8?xsec_token=ABCD1234"
"""

import sys
import re
import json
import requests
import time
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_user_info_from_html(html: str) -> dict:
    """
    从 HTML 页面中提取用户信息

    Args:
        html: 小红书页面 HTML 内容

    Returns:
        包含用户信息的字典
    """
    user_info = {
        'nickname': None,
        'user_id': None,
        'user_homepage': None
    }

    try:
        # 查找 __INITIAL_STATE__ JSON 数据
        start_idx = html.find('window.__INITIAL_STATE__=')
        if start_idx == -1:
            print("⚠️  未找到 __INITIAL_STATE__，尝试备用方法...")
            return extract_user_info_fallback(html)

        start_idx += len('window.__INITIAL_STATE__=')
        end_idx = html.find('</script>', start_idx)
        json_str = html[start_idx:end_idx]

        try:
            data = json.loads(json_str)
            print("✅ JSON 解析成功")

            # 方法 1: 从 user.user 路径获取
            user = data.get('user', {}).get('user', {})
            if user and user.get('nickname'):
                user_info['nickname'] = user.get('nickname')
                user_info['user_id'] = user.get('user_id') or user.get('userId') or user.get('webId')
                user_info['user_homepage'] = f"https://www.xiaohongshu.com/user/profile/{user_info['user_id']}"
                print(f"   ✅ 从 user.user 路径提取")
                return user_info

            # 方法 2: 从 user.userPageInfo 路径获取
            if user_info['nickname'] is None:
                user_page_info = data.get('user', {}).get('userPageInfo', {})
                if user_page_info and user_page_info.get('user'):
                    user = user_page_info.get('user', {})
                    if user and user.get('nickname'):
                        user_info['nickname'] = user.get('nickname')
                        user_info['user_id'] = user.get('user_id') or user.get('userId') or user.get('webId')
                        user_info['user_homepage'] = f"https://www.xiaohongshu.com/user/profile/{user_info['user_id']}"
                        print(f"   ✅ 从 user.userPageInfo 路径提取")
                        return user_info

            # 方法 3: 从 note.noteDetail 路径获取
            if user_info['nickname'] is None:
                note = data.get('note', {})
                note_detail = note.get('noteDetail', {})
                if note_detail and note_detail.get('user'):
                    user = note_detail.get('user', {})
                    if user and user.get('nickname'):
                        user_info['nickname'] = user.get('nickname')
                        user_info['user_id'] = user.get('user_id') or user.get('userId') or user.get('webId')
                        user_info['user_homepage'] = f"https://www.xiaohongshu.com/user/profile/{user_info['user_id']}"
                        print(f"   ✅ 从 note.noteDetail.user 路径提取")
                        return user_info

        except json.JSONDecodeError:
            print("⚠️  JSON 解析失败，使用备用方法")
            return extract_user_info_fallback(html)

    except Exception as e:
        print(f"❌ 提取失败: {e}")
        return {'nickname': None, 'user_id': None, 'user_homepage': None}


def extract_user_info_fallback(html: str) -> dict:
    """
    备用方法：从 HTML 中直接搜索用户名

    Args:
        html: 小红书页面 HTML 内容

    Returns:
        包含用户信息的字典
    """
    user_info = {
        'nickname': "小红书用户",
        'user_id': None,
        'user_homepage': None
    }

    # 搜索用户名的正则表达式模式
    user_patterns = [
        r'"user":\{[^}]*"nickname":"([^"]+)"',  # user 对象内的 nickname
        r'"nickname":"([^"]+)"',  # 任何 nickname
        r'"nickName":"([^"]+)"',
        r'"name":"([^"]+)"',
    ]

    for pattern in user_patterns:
        match = re.search(pattern, html)
        if match:
            try:
                # 处理 Unicode 转义
                nickname = match.group(1)
                try:
                    nickname = nickname.encode('raw_unicode_escape').decode('unicode_escape')
                except:
                    try:
                        nickname = nickname.encode('latin1').decode('utf-8')
                    except:
                        pass

                # 过滤一些明显不是用户名的值
                if nickname and len(nickname) > 1 and len(nickname) < 30:
                    if nickname not in ['分享', '推荐', '关注', '粉丝', '笔记', '点赞']:
                        user_info['nickname'] = nickname
                        print(f"   ✅ 从 HTML 提取用户名: {nickname}")
                        break
            except:
                pass

    return user_info


def extract_author_from_url(url: str) -> dict:
    """
    从小红书笔记链接提取作者信息

    Args:
        url: 小红书笔记链接（需要包含 xsec_token）

    Returns:
        包含作者信息的字典
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    print(f"📡 正在请求笔记页面...")
    print(f"   URL: {url[:80]}...")

    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            return {'nickname': None, 'user_id': None, 'user_homepage': None}

        print(f"   状态码: {response.status_code}")
        print(f"   最终URL: {response.url[:80]}...")

        # 检查是否被重定向到404
        if '/404?' in response.url or '你访问的页面不见了' in response.text:
            print(f"❌ 页面无法访问（反爬虫保护）")
            print(f"   原因：")
            print(f"   1. 链接缺少 xsec_token 参数")
            print(f"   2. 链接已过期或失效")
            print(f"   3. 需要登录才能查看")
            return {'nickname': None, 'user_id': None, 'user_homepage': None}

        html = response.text
        print(f"✅ 页面获取成功 (长度: {len(html)})")

        # 提取作者信息
        user_info = extract_user_info_from_html(html)

        # 尝试从 URL 中提取用户ID（备用）
        if not user_info['user_id']:
            url_match = re.search(r'/user/profile/([a-f0-9]+)', response.url)
            if url_match:
                user_info['user_id'] = url_match.group(1)
                user_info['user_homepage'] = response.url.split('/user/profile/')[0]
                print(f"   ✅ 从 URL 提取用户ID: {user_info['user_id']}")

        return user_info

    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        return {'nickname': None, 'user_id': None, 'user_homepage': None}
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求错误: {e}")
        return {'nickname': None, 'user_id': None, 'user_homepage': None}
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        return {'nickname': None, 'user_id': None, 'user_homepage': None}


def format_user_info(user_info: dict, url: str) -> str:
    """
    格式化输出作者信息

    Args:
        user_info: 用户信息字典
        url: 原始链接

    Returns:
        格式化的字符串
    """
    output = []
    output.append("=" * 60)
    output.append("👤 小红书作者信息提取")
    output.append("=" * 60)
    output.append("")

    output.append(f"📋 笔记链接:")
    output.append(f"   {url}")
    output.append("")

    output.append(f"👤 作者信息:")
    if user_info['nickname']:
        output.append(f"   昵称: {user_info['nickname']}")
    if user_info['user_id']:
        output.append(f"   用户ID: {user_info['user_id']}")
    if user_info['user_homepage']:
        output.append(f"   用户主页: {user_info['user_homepage']}")

    output.append("")

    output.append("=" * 60)
    output.append("📝 使用方法:")
    output.append("   1. 将此作者信息复制到 content.txt 文件中")
    output.append("   2. 或使用分析工具的 URL 模式自动保存")
    output.append("")

    output.append("💾 输出到文件:")
    output_filename = f"xhs_author_info_{user_info['nickname'] or 'unknown'}_{int(time.time())}.txt"
    output_file_path = Path(output_filename)

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# 小红书作者信息\n\n")
            f.write(f"笔记链接: {url}\n\n")
            f.write(f"## 作者信息\n\n")
            if user_info['nickname']:
                f.write(f"昵称: {user_info['nickname']}\n")
            if user_info['user_id']:
                f.write(f"用户ID: {user_info['user_id']}\n")
            if user_info['user_homepage']:
                f.write(f"用户主页: {user_info['user_homepage']}\n")
            f.write(f"\n---\n")
            f.write(f"提取时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"✅ 信息已保存: {output_file_path.absolute()}")
        return '\n'.join(output)
    except Exception as e:
        return f"❌ 保存文件失败: {e}\n"


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python extract_xhs_author.py \"小红书笔记链接\"")
        print("\n注意：")
        print("1. 链接必须包含 xsec_token 参数")
        print("2. 可以从小红书 APP 的分享功能复制完整链接")
        print("\n示例:")
        print("  python extract_xhs_author.py \"https://www.xiaohongshu.com/explore/66fad51c00000001b0224b8?xsec_token=ABCD1234\"")
        sys.exit(1)

    url = sys.argv[1]
    result = extract_author_from_url(url)

    print(format_user_info(result, url))


if __name__ == "__main__":
    main()
