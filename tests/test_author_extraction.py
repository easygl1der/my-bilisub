#!/usr/bin/env python3
"""
测试作者信息提取和文件夹生成
"""

import sys
import re
import json
import requests
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_xhs_note_info(url: str) -> dict:
    """
    从小红书笔记链接提取信息（集成作者提取功能）
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    print(f"📡 正在请求笔记页面...")
    print(f"   URL: {url[:80]}...")

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            return None

        html = response.text
        print(f"✅ 页面获取成功 (长度: {len(html)})")

        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', html)
        title = title_match.group(1) if title_match else "未知标题"
        title = re.sub(r'\s*-\s*小红书.*$', '', title)

        # 提取文案
        desc = ""
        desc_patterns = [
            r'"desc":"([^"]+)"',
            r'"title":"([^"]+)"',
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html)
            if desc_match:
                desc = desc_match.group(1)
                if desc:
                    break

        # 提取图片 URL 和用户名
        image_urls = []
        username = "小红书用户"  # 默认值

        # 查找 __INITIAL_STATE__
        start_idx = html.find('window.__INITIAL_STATE__=')
        if start_idx == -1:
            print(f"⚠️  未找到 __INITIAL_STATE__，使用备用方法...")
            username = "小红书用户"
        else:
            start_idx += len('window.__INITIAL_STATE__=')
            end_idx = html.find('</script>', start_idx)
            json_str = html[start_idx:end_idx]

            try:
                data = json.loads(json_str)

                # 提取用户名 - 使用多个路径尝试
                username = "小红书用户"
                user = data.get('user', {}).get('user', {})
                if not user or not user.get('nickname'):
                    user = data.get('user', {}).get('userPageInfo', {}).get('user', {})
                if not user or not user.get('nickname'):
                    note = data.get('note', {})
                    note_detail = note.get('noteDetail', {})
                    user = note_detail.get('user', {})

                # 获取 nickname
                if user and user.get('nickname'):
                    username = user.get('nickname')
                elif user:
                    username = (user.get('name') or user.get('nickName') or user.get('username') or "小红书用户")

                print(f"   ✅ 从 JSON 提取用户名: {username}")

                # 提取图片 URL
                note = data.get('note', {})
                note_detail = note.get('noteDetail', {})
                image_list = note_detail.get('imageList', [])

                if image_list:
                    for img_obj in image_list:
                        if isinstance(img_obj, dict):
                            url = (img_obj.get('urlDefault') or img_obj.get('url_default') or img_obj.get('url'))
                            if url:
                                image_urls.append(url)

            except json.JSONDecodeError:
                print(f"⚠️  JSON 解析失败，使用备用方法提取用户名和图片...")

                # 备用方法：从 HTML 中直接搜索用户名
                user_patterns = [
                    r'"user":\{[^}]*"nickname":"([^"]+)"',
                    r'"nickname":"([^"]+)"',
                    r'"nickName":"([^"]+)"',
                    r'"name":"([^"]+)"',
                ]

                for pattern in user_patterns:
                    match = re.search(pattern, html)
                    if match:
                        try:
                            nickname = match.group(1)
                            try:
                                nickname = nickname.encode('raw_unicode_escape').decode('unicode_escape')
                            except:
                                try:
                                    nickname = nickname.encode('latin1').decode('utf-8')
                                except:
                                    pass

                            if nickname and len(nickname) > 1 and len(nickname) < 30:
                                if nickname not in ['分享', '推荐', '关注', '粉丝', '笔记', '点赞']:
                                    username = nickname
                                    print(f"   ✅ 从 HTML 提取用户名: {username}")
                                    break
                        except:
                            pass

                # 备用方法：直接搜索图片 URL
                start = json_str.find('"imageList"')
                if start >= 0:
                    bracket_start = json_str.find('[', start)
                    if bracket_start >= 0:
                        depth = 0
                        i = bracket_start
                        while i < len(json_str):
                            if json_str[i] == '[':
                                depth += 1
                            elif json_str[i] == ']':
                                depth -= 1
                                if depth == 0:
                                    bracket_end = i
                                    break
                            i += 1

                        list_content = json_str[bracket_start+1:bracket_end]
                        url_pattern = r'"urlDefault":"([^"]+)"'
                        for match in re.finditer(url_pattern, list_content):
                            url = match.group(1)
                            if url:
                                image_urls.append(url)

        # 去重并清理 URL
        seen = set()
        unique_urls = []
        for url in image_urls:
            url = url.split('?')[0]
            try:
                url = url.encode('utf-8').decode('unicode_escape')
            except:
                pass
            url = url.replace(r'\/', '/')
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            elif not url.startswith('https://'):
                continue
            if url not in seen and 'xhscdn' in url:
                seen.add(url)
                unique_urls.append(url)

        # 提取用户主页链接
        user_homepage = ''
        if start_idx != -1:
            try:
                data = json.loads(json_str)
                user = data.get('user', {}).get('user', {})
                if not user or not user.get('user_id'):
                    user = data.get('user', {}).get('userPageInfo', {}).get('user', {})
                if not user or not user.get('user_id'):
                    note = data.get('note', {})
                    note_detail = note.get('noteDetail', {})
                    user = note_detail.get('user', {})

                if user:
                    user_id = (user.get('user_id') or user.get('userId') or user.get('webId'))
                    if user_id:
                        user_homepage = f"https://www.xiaohongshu.com/user/profile/{user_id}"
            except:
                pass

        result = {
            'title': title,
            'desc': desc,
            'image_urls': unique_urls,
            'note_url': response.url,
            'user_homepage': user_homepage,
            'username': username,
        }

        print(f"✅ 成功提取笔记信息")
        print(f"   标题: {title[:50]}...")
        print(f"   作者: {username}")
        print(f"   图片: {len(unique_urls)} 张")
        print(f"   链接: {response.url[:80]}...")

        return result

    except Exception as e:
        print(f"❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_folder_creation(note_info: dict, output_dir: str = "test_output"):
    """测试文件夹创建"""
    print(f"\n📁 测试文件夹创建...")

    # 使用提取的用户名
    username = note_info.get('username', '小红书用户')

    # 创建目录结构: xhs_images/用户名/笔记标题/
    safe_user = re.sub(r'[<>:"/\\|?*]', '_', username)[:30]
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', note_info['title'])[:50]
    note_path = Path(output_dir) / safe_user / safe_title

    print(f"   原始用户名: {username}")
    print(f"   安全用户名: {safe_user}")
    print(f"   原始标题: {note_info['title'][:50]}...")
    print(f"   安全标题: {safe_title}")
    print(f"   目标路径: {note_path}")

    note_path.mkdir(parents=True, exist_ok=True)

    # 保存 content.txt
    content_file = note_path / "content.txt"
    with open(content_file, 'w', encoding='utf-8') as f:
        f.write(f"标题: {note_info['title']}\n")
        if note_info['note_url']:
            f.write(f"链接: {note_info['note_url']}\n")
        if note_info['user_homepage']:
            f.write(f"用户主页: {note_info['user_homepage']}\n")
        f.write(f"\n文案:\n{note_info['desc']}\n")

    print(f"✅ 文件夹创建成功: {note_path.absolute()}")
    return note_path


if __name__ == "__main__":
    print("=" * 70)
    print("测试作者信息提取和文件夹生成")
    print("=" * 70)

    # 测试 URL
    test_url = "https://www.xiaohongshu.com/user/profile/5b3ac81e11be107c7a5b7505/693403a7000000001b0254fd?xsec_token=ABS7B2HIyDprbTuCY1a8jezgQmFjdpeJGzBUjbxE1Cc9g=&xsec_source=pc_user"

    # 提取信息
    note_info = extract_xhs_note_info(test_url)

    if note_info:
        # 测试文件夹创建
        folder_path = test_folder_creation(note_info)

        print("\n" + "=" * 70)
        print("测试完成！")
        print(f"文件夹路径: {folder_path}")
        print("=" * 70)
    else:
        print("\n❌ 测试失败：无法提取笔记信息")
