#!/usr/bin/env python3
"""
从CSV文件批量下载视频

功能：
1. 读取 xhs_videos_output 目录下的CSV文件
2. 自动识别小红书/B站链接
3. 下载视频到以作者命名的文件夹
4. 文件名使用视频标题
5. 显示下载进度和耗时

使用示例:
    # 下载单个CSV文件
    python download_videos_from_csv.py -csv "MediaCrawler/xhs_videos_output/杨雨坤-Yukun.csv"

    # 下载目录下所有CSV
    python download_videos_from_csv.py -dir "MediaCrawler/xhs_videos_output"

    # 只下载指定类型的视频
    python download_videos_from_csv.py -csv "xxx.csv" --type video
"""

import os
import sys
import csv
import re
import time
import threading
import argparse
import shutil
from pathlib import Path
from datetime import datetime

import yt_dlp
import requests
from bs4 import BeautifulSoup

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== B站 Cookie 配置 ====================
# 从 fetch_bilibili_videos.py 复制的 B 站 Cookie
BILI_COOKIE = "buvid3=ED836AB2-1A1F-83B3-C368-EC717E8514CC52442infoc; b_nut=1768880952; lang=zh-Hans; theme-tip-show=SHOWED; buvid4=E6C199FE-5C98-198C-D77F-9B183C96AC6657438-026012011-zxmN2%2Bh1P%2F0eoan1hmmTzg%3D%3D; buvid_fp=bdde8cc73192655bb657c6b1b634831a; rpdid=|(Jl|J~JlJu)0J'u~Y)))u|Rl; theme-avatar-tip-show=SHOWED; DedeUserID=352314171; DedeUserID__ckMd5=8753aa0a6f5400e0; CURRENT_QUALITY=80; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzEzNTA4OTgsImlhdCI6MTc3MTA5MTYzOCwicGx0IjotMX0.7NGUxpL_Kpz6MIafuGccDUrwQ0MYWTJIdZbcWzRFbK0; bili_ticket_expires=1771350838; SESSDATA=340e7534%2C1786643702%2C8ff5f%2A22CjBmNdSHwh1cJexOwoyFWM5LODSzCLixmDSo8umHTW2VrYyVmwwZMAH0xptDSCSuoaoSVnJ1UF9Lc0pockFlLTlKMEYteUdfNFhSbUxYTDlZak1sMHd1MHlpRTJKUzg3WGpYbVpNbEFNNlZyczJuMUZObW5mOVgtWjJQZnJ0TFhHY1NnbnA1c1lRIIEC; bili_jct=00bda0ae20a58226c7ab7c0198f889e8; bmg_af_switch=1; bmg_src_def_domain=i2.hdslb.com; sid=8khlk9a0; bp_t_offset_352314171=1169997504301760512; CURRENT_FNVAL=2000; home_feed_column=4; brows"

# ==================== YouTube Cookie 配置 ====================
# YouTube 下载可能需要 cookies.txt 文件来避免 403 错误
# 可以使用浏览器扩展 "Get cookies.txt LOCALLY" 导出 YouTube cookies
# 保存为 cookies_youtube.txt 放在当前目录下
YOUTUBE_COOKIE_FILE = "cookies_youtube.txt"
YOUTUBE_COOKIE_FILE_ALT = "youtube_cookies.txt"  # 备用文件名

# Chrome cookies 路径（Windows）
CHROME_COOKIE_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cookies"),
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"),
]

# Edge cookies 路径（Windows）
EDGE_COOKIE_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cookies"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"),
]


def get_browser_cookies_youtube() -> str:
    """
    尝试从浏览器获取 YouTube 的 cookies

    Returns:
        cookies 字符串，失败返回 None
    """
    try:
        import sqlite3
        import tempfile
        from shutil import copy2

        # 查找浏览器 cookie 文件
        cookie_paths = EDGE_COOKIE_PATHS + CHROME_COOKIE_PATHS
        cookie_file = None

        for path in cookie_paths:
            if os.path.exists(path):
                cookie_file = path
                break

        if not cookie_file:
            return None

        # 复制 cookie 文件（因为浏览器可能正在使用）
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp_path = tmp.name

        try:
            copy2(cookie_file, tmp_path)
        except Exception:
            return None

        # 读取 cookies
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # 查询 YouTube cookies
        cursor.execute("""
            SELECT name, value
            FROM cookies
            WHERE host_key LIKE '%.youtube.com'
            OR host_key = '.youtube.com'
        """)

        cookies = {}
        for name, value in cursor.fetchall():
            if name in ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID', 'LOGIN_INFO', 'PREF', 'VISITOR_INFO1_LIVE']:
                cookies[name] = value

        conn.close()
        os.unlink(tmp_path)

        # 检查关键 cookie 是否存在
        if 'SID' not in cookies or 'HSID' not in cookies:
            return None

        # 转换为 cookie 字符串
        cookie_str = '; '.join([f"{name}={value}" for name, value in cookies.items()])
        return cookie_str

    except Exception as e:
        return None


# ==================== 进度条 ====================

class ProgressHook:
    """yt-dlp下载进度钩子"""

    def __init__(self):
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = 0
        self.eta = 0
        self.filename = ""
        self.status = ""
        self._last_update = 0

    def __call__(self, d):
        if d['status'] == 'downloading':
            self.downloaded_bytes = d.get('downloaded_bytes', 0)
            self.total_bytes = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            self.speed = d.get('speed', 0)
            self.eta = d.get('eta', 0)
            self.filename = d.get('filename', '')
            self.status = 'downloading'

            # 限制更新频率（每0.5秒）
            now = time.time()
            if now - self._last_update > 0.5:
                self._print_progress()
                self._last_update = now

        elif d['status'] == 'finished':
            self.status = 'finished'
            print(f"\r   └─ 下载完成，正在处理...{' ' * 40}")

    def _print_progress(self):
        if self.total_bytes and self.total_bytes > 0:
            percent = self.downloaded_bytes / self.total_bytes * 100
            bar_length = 25
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)

            # 速度显示
            speed = self.speed or 0
            if speed > 0:
                if speed >= 1024 * 1024:
                    speed_str = f"{speed / 1024 / 1024:.1f}MB/s"
                elif speed >= 1024:
                    speed_str = f"{speed / 1024:.1f}KB/s"
                else:
                    speed_str = f"{speed:.0f}B/s"
            else:
                speed_str = "--"

            # ETA显示
            eta = self.eta if self.eta and self.eta > 0 else 0
            if eta > 0:
                eta_str = f"{eta:.0f}s"
            else:
                eta_str = "--"

            # 已下载大小
            downloaded_mb = self.downloaded_bytes / 1024 / 1024
            total_mb = self.total_bytes / 1024 / 1024

            print(f"\r   └─ [{bar}] {percent:5.1f}% | {downloaded_mb:.1f}/{total_mb:.1f}MB | {speed_str} | ETA: {eta_str}{' ' * 10}", end='', flush=True)


# ==================== 工具函数 ====================

def sanitize_filename(name: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符"""
    # 移除或替换非法字符
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)

    # 移除控制字符
    name = ''.join(char for char in name if ord(char) >= 32)

    # 去除首尾空格和点
    name = name.strip('. ')

    # 限制长度
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]  # 尝试在空格处截断

    return name or "untitled"


def detect_platform(url: str) -> str:
    """检测视频平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    else:
        return 'unknown'


def detect_bilibili_type(url: str) -> str:
    """
    检测B站链接的类型

    Args:
        url: B站链接

    Returns:
        'video' (视频) 或 'normal' (图文/专栏)
    """
    url_lower = url.lower()

    # b23.tv 短链接默认为视频
    if 'b23.tv' in url_lower:
        return 'video'

    # B站图文/专栏URL特征（优先检查）
    article_patterns = [
        '/read/',       # 专栏 https://www.bilibili.com/read/...
        '/opus/',       # 动态投稿 https://www.bilibili.com/opus/...
        'article',      # 包含article关键字
    ]

    # 检查是否为图文/专栏
    for pattern in article_patterns:
        if pattern in url_lower:
            return 'normal'

    # B站视频URL特征
    video_patterns = [
        '/video/',      # 普通视频 https://www.bilibili.com/video/BV...
        '/av',          # av号 https://www.bilibili.com/av...
        'bilibili.com/bvid',  # BV号
        '/bangumi/',    # 番剧
        '/medialist/',  # 播放列表
    ]

    # 检查是否为视频
    for pattern in video_patterns:
        if pattern in url_lower:
            return 'video'

    # 如果URL包含 bilibili.com 但不匹配上述模式，默认为视频
    if 'bilibili.com' in url_lower:
        return 'video'

    # 未知情况默认为视频
    return 'video'


def get_author_name_from_csv(csv_path: str) -> str:
    """从CSV文件名提取作者名"""
    filename = Path(csv_path).stem
    # 移除可能的时间戳后缀
    if re.search(r'_\d{8}', filename):
        filename = re.sub(r'_\d{8}.*', '', filename)
    return filename


def parse_csv(csv_path: str, filter_type: str = None) -> list:
    """
    解析CSV文件，提取视频信息

    Args:
        csv_path: CSV文件路径
        filter_type: 筛选类型 (video/normal)，None表示全部

    Returns:
        list: 视频信息列表 [{index, title, url, type, ...}, ...]
    """
    videos = []

    print(f"\n📖 读取CSV文件: {Path(csv_path).name}")

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # 检查列名
            if not reader.fieldnames:
                print("❌ CSV文件为空或格式错误")
                return videos

            for row in reader:
                url = row.get('链接', '') or row.get('url', '')
                title = row.get('标题', '') or row.get('title', '')
                note_type = row.get('类型', '') or row.get('type', '')
                index = row.get('序号', '') or row.get('index', '')

                # 跳过空URL
                if not url or not url.startswith('http'):
                    continue

                # 如果类型为空，自动检测
                if not note_type:
                    platform = detect_platform(url)
                    if platform == 'bilibili':
                        note_type = detect_bilibili_type(url)
                    elif platform == 'xiaohongshu':
                        # 小红书暂时默认为视频，下载时再判断
                        note_type = 'video'
                    else:
                        note_type = 'video'  # 未知平台默认为视频

                # 类型筛选
                if filter_type and filter_type.lower() != note_type.lower():
                    continue

                videos.append({
                    'index': index,
                    'title': title or f"视频_{index}",
                    'url': url,
                    'type': note_type,
                    'row': row
                })

        print(f"✅ 找到 {len(videos)} 个视频链接")

    except Exception as e:
        print(f"❌ 读取CSV失败: {e}")

    return videos


def show_video_list(videos: list, show_count: int = 10):
    """
    显示待下载视频列表

    Args:
        videos: 视频列表
        show_count: 每页显示数量
    """
    print("\n" + "=" * 80)
    print("📋 待下载视频列表")
    print("=" * 80)

    # 统计类型
    video_count = sum(1 for v in videos if v.get('type', '').lower() == 'video')
    normal_count = sum(1 for v in videos if v.get('type', '').lower() == 'normal')
    unknown_count = len(videos) - video_count - normal_count

    for i, video in enumerate(videos, 1):
        platform = detect_platform(video['url'])
        platform_icon = {'xiaohongshu': '📕', 'bilibili': '📺', 'youtube': '▶️', 'unknown': '📄'}.get(platform, '📄')

        # 类型图标
        note_type = video.get('type', '').lower()
        if note_type == 'normal':
            type_icon = '📷'
            type_text = '图文'
        elif note_type == 'video':
            type_icon = '🎬'
            type_text = '视频'
        else:
            type_icon = '❓'
            type_text = video['type'] or '未知'

        # 序号 | 平台 | 类型 | 标题
        print(f"{i:3}. [{platform_icon}] [{type_icon}] {video['title'][:45]}... | {type_text}")

    print("=" * 80)
    print(f"总计: {len(videos)} | 🎬视频: {video_count} | 📷图文: {normal_count} | ❓未知: {unknown_count}")
    print("=" * 80)


# ==================== 下载核心 ====================

def download_images_from_note(url: str, title: str, output_dir: Path, platform: str) -> dict:
    """
    下载小红书/B站图文内容中的图片

    Args:
        url: 图文链接
        title: 标题
        output_dir: 输出目录
        platform: 平台名称

    Returns:
        dict: 下载结果 {success, files, count, error}
    """
    import json
    import re

    result = {
        'success': False,
        'files': [],
        'count': 0,
        'error': None
    }

    safe_title = sanitize_filename(title)
    note_dir = output_dir / safe_title
    note_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/' if platform == 'xiaohongshu' else 'https://www.bilibili.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    unique_images = []

    try:
        # ============ 方法1: 小红书专用 - 直接解析页面获取图片 ============
        if platform == 'xiaohongshu':
            print(f"   └─ 📡 解析小红书页面获取图片...")

            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

                html = response.text

                # 检查是否被重定向到404
                if '/404?' in response.url or '你访问的页面不见了' in html:
                    print(f"   └─ ⚠️  页面无法访问（反爬虫保护或链接失效）")
                    # 继续尝试其他方法

                # 改进版：使用括号匹配法完整提取 imageList
                start_idx = html.find('window.__INITIAL_STATE__=')
                if start_idx >= 0:
                    start_idx += len('window.__INITIAL_STATE__=')
                    end_idx = html.find('</script>', start_idx)
                    json_str = html[start_idx:end_idx]

                    # 查找 imageList 数组 - 使用计数器匹配完整的数组
                    list_start = json_str.find('"imageList"')
                    if list_start >= 0:
                        bracket_start = json_str.find('[', list_start)
                        if bracket_start >= 0:
                            # 手动匹配对应的 ]
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

                            # 只提取 urlDefault（默认/原图），跳过其他变体
                            url_pattern = r'"urlDefault":"([^"]+)"'
                            for match in re.finditer(url_pattern, list_content):
                                img_url = match.group(1)
                                if img_url:
                                    # 解码 Unicode 转义
                                    try:
                                        img_url = img_url.encode('utf-8').decode('unicode_escape')
                                    except:
                                        pass
                                    # 确保 https 协议
                                    if img_url.startswith('http://'):
                                        img_url = 'https://' + img_url[7:]
                                    if 'xhscdn' in img_url:
                                        unique_images.append(img_url)

                # 备用：如果上面失败，尝试 JSON 解析
                if not unique_images:
                    initial_state_pattern = r'window\.__INITIAL_STATE__\s*=\s*({.+?});'
                    match = re.search(initial_state_pattern, html)
                    if match:
                        try:
                            initial_state = json.loads(match.group(1))
                            image_list = initial_state.get('note', {}).get('noteDetail', {}).get('imageList', [])
                            if isinstance(image_list, list):
                                for img_obj in image_list:
                                    if isinstance(img_obj, dict):
                                        img_url = img_obj.get('urlDefault') or img_obj.get('url')
                                        if img_url:
                                            unique_images.append(img_url)
                        except json.JSONDecodeError:
                            pass

                # 备用2: 从整个 HTML 中搜索 sns-webpic 图片URL
                if not unique_images:
                    all_urls = re.findall(r'(https://sns-webpic[^\"\s\'<>]+)', html)
                    unique_urls = list(set(all_urls))
                    if unique_urls:
                        unique_images.extend(unique_urls[:10])

            except Exception as e:
                print(f"   └─ ⚠️  小红书页面解析失败: {str(e)[:40]}")

        # ============ 方法2: 使用 yt-dlp 提取图片信息 ============
        if not unique_images:
            print(f"   └─ 📡 使用yt-dlp获取图片信息...")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'independent',
                'http_headers': headers,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if info:
                        # thumbnails 字段
                        if 'thumbnails' in info and info['thumbnails']:
                            seen_urls = set()
                            for thumb in info['thumbnails']:
                                img_url = thumb.get('url') or thumb.get('data', {}).get('url')
                                if img_url and img_url not in seen_urls:
                                    seen_urls.add(img_url)
                                    unique_images.append(img_url)

                        # pictures 字段
                        elif 'pictures' in info and info['pictures']:
                            for pic in info['pictures']:
                                img_url = pic.get('url') or pic.get('data', {}).get('url_default')
                                if img_url:
                                    unique_images.append(img_url)

                        # images 字段
                        elif 'images' in info and isinstance(info['images'], list):
                            unique_images.extend(info['images'])

            except Exception as e:
                print(f"   └─ ⚠️  yt-dlp提取失败: {str(e)[:40]}")

        # ============ 方法3: 通用页面解析 ============
        if not unique_images:
            print(f"   └─ 📷 尝试通用页面解析...")

            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 从 meta 标签获取
                meta_og_image = soup.find('meta', property='og:image')
                if meta_og_image:
                    img_url = meta_og_image.get('content')
                    if img_url:
                        unique_images.append(img_url)

                # 从 twitter:image 获取
                meta_twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                if meta_twitter_image:
                    img_url = meta_twitter_image.get('content')
                    if img_url:
                        unique_images.append(img_url)

            except Exception as e:
                print(f"   └─ ⚠️  通用解析失败: {str(e)[:40]}")

        if not unique_images:
            result['error'] = "未找到图片"
            return result

        # 清理和去重图片URL
        seen = set()
        cleaned_images = []
        for img in unique_images:
            if img and isinstance(img, str) and img.startswith('http') and img not in seen:
                # 转换为高质量URL
                if 'xhscdn.com' in img or 'xhslink' in img:
                    # 移除尺寸限制参数获取原图
                    img = img.split('?')[0]
                cleaned_images.append(img)
                seen.add(img)

        unique_images = cleaned_images

        if not unique_images:
            result['error'] = "图片URL为空"
            return result

        print(f"   └─ 📷 找到 {len(unique_images)} 张图片，开始下载...")

        # ============ 下载图片 ============
        downloaded_files = []
        for i, img_url in enumerate(unique_images, 1):
            try:
                img_response = requests.get(img_url, headers=headers, timeout=30)
                img_response.raise_for_status()

                # 确定文件扩展名
                ext = '.jpg'
                content_type = img_response.headers.get('Content-Type', '')
                if 'png' in content_type:
                    ext = '.png'
                elif 'webp' in content_type:
                    ext = '.webp'
                elif 'jpeg' in content_type:
                    ext = '.jpg'

                img_filename = f"{safe_title}_{i:02d}{ext}"
                img_path = note_dir / img_filename

                with open(img_path, 'wb') as f:
                    f.write(img_response.content)

                downloaded_files.append(str(img_path))
                print(f"   └─ [{i}/{len(unique_images)}] ✅ {img_filename}")

            except Exception as e:
                print(f"   └─ [{i}/{len(unique_images)}] ❌ 下载失败: {str(e)[:40]}")

        if downloaded_files:
            result['success'] = True
            result['files'] = downloaded_files
            result['count'] = len(downloaded_files)
        else:
            result['error'] = "所有图片下载失败"

    except Exception as e:
        result['error'] = f"获取图文失败: {str(e)}"

    return result


def download_video(video_info: dict, index: int, total: int, output_dir: Path, headers: dict = None) -> dict:
    """
    下载单个视频或图文

    Args:
        video_info: 视频信息字典
        index: 当前索引
        total: 总数
        output_dir: 输出目录
        headers: 自定义请求头

    Returns:
        dict: 下载结果
    """
    url = video_info['url']
    title = video_info['title']
    note_type = video_info.get('type', 'video').lower()
    platform = detect_platform(url)

    # 判断是否为图文类型
    is_normal = note_type == 'normal'

    result = {
        'url': url,
        'title': title,
        'platform': platform,
        'type': note_type,
        'success': False,
        'error': None,
        'output_file': None,
        'elapsed': 0,
        'is_normal': is_normal
    }

    # 清理标题作为文件名
    safe_title = sanitize_filename(title)

    # ============ 图文类型处理 ============
    if is_normal:
        note_dir = output_dir / safe_title

        # 检查是否已存在
        if note_dir.exists():
            img_count = len(list(note_dir.glob('*.*')))
            # 如果文件夹存在但图片数为0，删除空文件夹重新下载
            if img_count == 0:
                print(f"\n[{index}/{total}] 📕 {title[:50]}... | [图文]")
                print(f"   └─ ⚠️  文件夹为空，重新下载...")
                shutil.rmtree(note_dir, ignore_errors=True)
            else:
                result['success'] = True
                result['output_file'] = str(note_dir)
                result['skip_reason'] = f'已存在({img_count}张图)'
                result['elapsed'] = 0
                result['count'] = img_count
                result['skip_is_normal'] = True  # 标记跳过的是图文
                result['skip_count'] = img_count

                print(f"\n[{index}/{total}] 📕 {title[:50]}... | [图文]")
                print(f"   └─ ⏭️  已存在 ({img_count}张图片)")
                return result

        # 下载图文
        print(f"\n[{index}/{total}] 📕 {title[:50]}... | [图文]")
        print(f"   └─ 平台: {platform}")

        start_time = time.time()
        img_result = download_images_from_note(url, title, output_dir, platform)
        result['elapsed'] = time.time() - start_time

        if img_result['success']:
            result['success'] = True
            result['output_file'] = str(output_dir / safe_title)
            result['count'] = img_result['count']
            print(f"\r   └─ ✅ 完成! 下载了 {img_result['count']} 张图片 | {result['elapsed']:.1f}秒{' ' * 20}")
        else:
            result['error'] = img_result.get('error', '未知错误')
            print(f"\r   └─ ❌ {result['error'][:60]}{' ' * 20}")

        return result

    # ============ 视频类型处理 ============
    output_file = output_dir / f"{safe_title}.mp4"

    # 检查是否已存在
    if output_file.exists():
        file_size = output_file.stat().st_size / 1024 / 1024
        result['success'] = True
        result['output_file'] = str(output_file)
        result['skip_reason'] = '已存在'
        result['elapsed'] = 0

        print(f"\n[{index}/{total}] {title[:50]}...")
        print(f"   └─ ⏭️  已存在 ({file_size:.1f}MB)")
        return result

    # 下载信息
    print(f"\n[{index}/{total}] {title[:50]}...")
    print(f"   └─ 平台: {platform} | 类型: 🎬视频")

    try:
        # 基础配置
        progress_hook = ProgressHook()

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(output_dir / f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'concurrentfragments': 4,  # 流式下载
        }

        # 小红书特殊处理：需要Referer和Cookie
        if platform == 'xiaohongshu':
            ydl_opts.update({
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.xiaohongshu.com/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
            })

        # B站特殊处理
        elif platform == 'bilibili':
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
            }
            # 添加 Cookie
            if BILI_COOKIE:
                headers['Cookie'] = BILI_COOKIE
            ydl_opts.update({
                'http_headers': headers
            })

        # YouTube特殊处理（使用最佳质量）
        elif platform == 'youtube':
            # YouTube 下载需要特殊处理，因为可能被 403 阻止
            ydl_opts.update({
                'format': 'bestvideo+bestaudio/best',  # 简化格式选择
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                # SSL/网络相关选项
                'nocheckcertificate': True,  # 绕过SSL证书问题
                'extractor_retries': 2,  # 减少重试次数以便更快失败
                'fragment_retries': 3,
                'retries': 3,
                'file_access_retries': 2,
                'socket_timeout': 30,
                # 使用外部下载器（如果有 aria2）
                # 'external_downloader': 'aria2c',
                # 'external_downloader_args': ['-x', '16', '-k', '1M'],
                # 禁用调用主页
                'no_call_home': True,
                'break_on_reject': False,  # 遇到被阻止的格式继续尝试其他格式
            })

            # 检查是否设置了代理
            import os
            if os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'):
                proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
                ydl_opts['proxy'] = proxy
                print(f"   └─ 🌐 使用代理: {proxy}")

            # 检查是否有 YouTube cookies 文件
            cookie_content = None
            cookie_file = Path(YOUTUBE_COOKIE_FILE)
            cookie_file_alt = Path(YOUTUBE_COOKIE_FILE_ALT)

            if cookie_file.exists():
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookie_content = f.read().strip()
                print(f"   └─ 🍪 使用 Cookie 文件: {YOUTUBE_COOKIE_FILE}")
            elif cookie_file_alt.exists():
                with open(cookie_file_alt, 'r', encoding='utf-8') as f:
                    cookie_content = f.read().strip()
                print(f"   └─ 🍪 使用 Cookie 文件: {YOUTUBE_COOKIE_FILE_ALT}")

            if cookie_content:
                # 添加 cookies 到请求头
                ydl_opts['http_headers']['Cookie'] = cookie_content
                ydl_opts['cookiefile'] = str(cookie_file if cookie_file.exists() else cookie_file_alt)
            else:
                # 尝试从浏览器获取 cookies
                browser_cookies = get_browser_cookies_youtube()
                if browser_cookies:
                    ydl_opts['http_headers']['Cookie'] = browser_cookies
                    print(f"   └─ 🍪 使用浏览器 Cookies")
                else:
                    print(f"   └─ ⚠️  未找到 Cookies，可能遇到 403 错误")

        # 自定义headers优先
        if headers:
            if 'http_headers' not in ydl_opts:
                ydl_opts['http_headers'] = {}
            ydl_opts['http_headers'].update(headers)

        # 执行下载
        start_time = time.time()

        # 调试信息
        if platform == 'youtube':
            print(f"   └─ 开始连接 YouTube...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # 获取实际下载的文件
            downloaded_file = Path(ydl.prepare_filename(info))
            if downloaded_file.exists():
                result['success'] = True
                result['output_file'] = str(downloaded_file)
            else:
                # 可能文件名有变化，尝试找最新文件
                files = list(output_dir.glob(f"{safe_title}.*"))
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    # 确保是最近5分钟内创建的
                    if time.time() - latest.stat().st_mtime < 300:
                        result['success'] = True
                        result['output_file'] = str(latest)

        elapsed = time.time() - start_time
        result['elapsed'] = elapsed

        if result['success']:
            file_size = Path(result['output_file']).stat().st_size / 1024 / 1024
            avg_speed = file_size / elapsed if elapsed > 0 else 0
            print(f"\r   └─ ✅ 完成! {elapsed:.1f}秒 | {file_size:.1f}MB | 平均 {avg_speed:.1f}MB/s{' ' * 20}")
        else:
            print(f"\r   └─ ❌ 下载失败: 文件未找到{' ' * 30}")

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)

        # YouTube 403 错误处理
        if platform == 'youtube' and ('403' in error_msg or 'Forbidden' in error_msg):
            print(f"\r   └─ ❌ YouTube 下载被阻止 (403 Forbidden){' ' * 20}")
            print(f"   └─ 💡 解决方法:")
            print(f"      1. 使用浏览器扩展 'Get cookies.txt LOCALLY' 导出 YouTube cookies")
            print(f"      2. 将 cookies 保存为 {YOUTUBE_COOKIE_FILE} 放在当前目录")
            print(f"      3. 或使用代理: set HTTPS_PROXY=http://127.0.0.1:7890")
            result['error'] = f"YouTube 403: 需要使用 cookies 或代理"
            result['elapsed'] = time.time() - start_time
            print(f"\r   └─ ❌ {result['error'][:60]}{' ' * 20}")
            return result

        # 检查是否是因为没有视频格式（可能是图文）
        if 'No video formats found' in error_msg or 'No media found' in error_msg:
            print(f"\r   └─ ⚠️  无视频格式，尝试作为图文处理...{' ' * 20}")
            # 尝试作为图文下载
            start_img = time.time()
            img_result = download_images_from_note(url, title, output_dir, platform)
            result['elapsed'] = time.time() - start_time

            if img_result['success']:
                result['success'] = True
                result['output_file'] = str(output_dir / safe_title)
                result['count'] = img_result['count']
                result['is_normal'] = True  # 标记为图文
                print(f"\r   └─ ✅ 图文下载成功! {img_result['count']}张图片 | {result['elapsed']:.1f}秒{' ' * 20}")
            else:
                result['error'] = f"视频和图文均失败: {img_result.get('error', '未知错误')[:60]}"
                result['elapsed'] = time.time() - start_time
                print(f"\r   └─ ❌ {result['error'][:60]}{' ' * 20}")
        else:
            result['error'] = f"下载错误: {error_msg[:80]}"
            result['elapsed'] = time.time() - start_time
            print(f"\r   └─ ❌ {result['error'][:60]}{' ' * 20}")
    except Exception as e:
        result['error'] = f"错误: {str(e)[:80]}"
        result['elapsed'] = time.time() - start_time
        print(f"\r   └─ ❌ {result['error'][:60]}{' ' * 20}")

    return result


def batch_download(videos: list, author_name: str, output_base_dir: str = "downloaded_videos") -> list:
    """
    批量下载视频

    Args:
        videos: 视频信息列表
        author_name: 作者名称（用于创建文件夹）
        output_base_dir: 基础输出目录

    Returns:
        list: 下载结果列表
    """
    if not videos:
        print("❌ 没有视频可下载")
        return []

    # 创建作者目录
    author_dir = Path(output_base_dir) / sanitize_filename(author_name)
    author_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 输出目录: {author_dir}")

    results = []
    success_count = 0
    skip_count = 0
    fail_count = 0
    total_elapsed = 0
    total_images = 0
    total_videos = 0

    start_total = time.time()

    for i, video in enumerate(videos, 1):
        result = download_video(video, i, len(videos), author_dir)
        results.append(result)

        total_elapsed += result['elapsed']

        if result['success']:
            if 'skip_reason' in result:
                skip_count += 1
                # 跳过的图文也要统计
                if result.get('skip_is_normal'):
                    total_images += result.get('skip_count', 0)
                else:
                    total_videos += 1
            else:
                success_count += 1
                # 统计图文/视频数量
                if result.get('is_normal'):
                    total_images += result.get('count', 0)
                else:
                    total_videos += 1
        else:
            fail_count += 1

        # 避免请求过快
        if i < len(videos):
            time.sleep(1)

    total_time = time.time() - start_total

    # 打印统计
    print("\n" + "=" * 80)
    print("📊 下载完成统计")
    print("=" * 80)
    print(f"   总计: {len(videos)} | 成功: {success_count} | 跳过: {skip_count} | 失败: {fail_count}")

    # 详细统计
    if total_images > 0 or total_videos > 0:
        print(f"   🎬 视频: {total_videos} 个 | 📷 图文: {total_images} 张图片")

    if success_count > 0:
        avg_time = total_elapsed / success_count if success_count > 0 else 0
        print(f"   总耗时: {total_time:.1f}秒 | 平均每个: {avg_time:.1f}秒")

    print("=" * 80)

    return results


def save_report(results: list, author_name: str, output_dir: str = "downloaded_videos"):
    """保存下载报告"""
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    # 使用固定的报告文件名，所有报告追加到同一个文件
    report_file = report_dir / f"{sanitize_filename(author_name)}_下载报告.txt"

    # 使用UTF-8 BOM编码，确保Windows记事本能正确显示中文
    # 追加模式，所有报告写入同一个文件
    with open(report_file, 'a', encoding='utf-8-sig') as f:
        f.write(f"视频/图文下载报告\n")
        f.write(f"{'='*60}\n")
        f.write(f"作者: {author_name}\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")

        success = sum(1 for r in results if r['success'] and 'skip_reason' not in r)
        skip = sum(1 for r in results if r['success'] and 'skip_reason' in r)
        fail = sum(1 for r in results if not r['success'])
        total_time = sum(r.get('elapsed', 0) for r in results)

        # 统计图文/视频
        total_images = sum(r.get('count', 0) for r in results if r.get('is_normal') and r['success'])
        total_videos = sum(1 for r in results if not r.get('is_normal') and r['success'] and 'skip_reason' not in r)

        f.write(f"总计: {len(results)} | 成功: {success} | 跳过: {skip} | 失败: {fail}\n")
        f.write(f"🎬 视频: {total_videos} 个 | 📷 图文: {total_images} 张图片\n")
        f.write(f"总耗时: {total_time:.1f}秒\n\n")
        f.write(f"{'='*60}\n\n")

        # 详细列表
        f.write(f"{'序号':<5} {'类型':<6} {'状态':<6} {'耗时':<10} {'标题'}\n")
        f.write(f"{'-'*70}\n")

        for i, r in enumerate(results, 1):
            if r['success']:
                if 'skip_reason' in r:
                    status = "跳过"
                else:
                    status = "成功"
            else:
                status = "失败"

            # 类型显示
            if r.get('is_normal'):
                type_str = "图文"
                if r['success'] and 'skip_reason' not in r:
                    status = f"成功({r.get('count', 0)}张)"
            else:
                type_str = "视频"

            elapsed_str = f"{r.get('elapsed', 0):.1f}s" if r.get('elapsed', 0) > 0 else "--"

            title = r['title'][:40]
            f.write(f"{i:<5} {type_str:<6} {status:<8} {elapsed_str:<10} {title}\n")

        f.write(f"\n{'='*60}\n\n")

        # 失败详情
        failed_results = [r for r in results if not r['success']]
        if failed_results:
            f.write(f"失败详情:\n\n")
            for r in failed_results:
                f.write(f"- {r['title']}\n")
                f.write(f"  链接: {r['url']}\n")
                f.write(f"  错误: {r.get('error', '未知错误')}\n\n")

    print(f"📄 报告已保存: {report_file.name}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="从CSV文件批量下载视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 下载单个CSV文件:
   python download_videos_from_csv.py -csv "MediaCrawler/xhs_videos_output/杨雨坤-Yukun.csv"

2. 下载目录下所有CSV:
   python download_videos_from_csv.py -dir "MediaCrawler/xhs_videos_output"

3. 只下载video类型:
   python download_videos_from_csv.py -csv "xxx.csv" --type video

4. 指定输出目录:
   python download_videos_from_csv.py -csv "xxx.csv" -o "my_videos"

5. 测试（只下载前3个）:
   python download_videos_from_csv.py -csv "xxx.csv" --limit 3
        """
    )

    parser.add_argument('-csv', '--csv-file', help='CSV文件路径')
    parser.add_argument('-dir', '--directory', help='CSV文件所在目录（处理所有CSV）')
    parser.add_argument('-o', '--output', default='downloaded_videos', help='输出目录（默认: downloaded_videos）')
    parser.add_argument('--type', choices=['video', 'normal'], help='筛选视频类型')
    parser.add_argument('--limit', type=int, help='限制下载数量（测试用）')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认直接开始下载')

    args = parser.parse_args()

    # 确定要处理的CSV文件
    csv_files = []

    if args.csv_file:
        csv_files.append(args.csv_file)
    elif args.directory:
        dir_path = Path(args.directory)
        if dir_path.is_dir():
            csv_files = list(dir_path.glob('*.csv'))
            # 排除报告文件
            csv_files = [f for f in csv_files if not f.name.startswith('_')]
        else:
            print(f"❌ 目录不存在: {args.directory}")
            return
    else:
        parser.print_help()
        return

    if not csv_files:
        print("❌ 未找到CSV文件")
        return

    print(f"📂 找到 {len(csv_files)} 个CSV文件")

    # 处理每个CSV文件
    all_results = {}

    for csv_file in csv_files:
        csv_file = Path(csv_file)
        author_name = get_author_name_from_csv(str(csv_file))

        print("\n" + "=" * 80)
        print(f"📝 处理作者: {author_name}")
        print(f"   文件: {csv_file.name}")
        print("=" * 80)

        # 解析CSV
        videos = parse_csv(str(csv_file), args.type)

        if not videos:
            print(f"⚠️  跳过: 没有视频")
            continue

        # 限制数量（测试用）
        if args.limit:
            videos = videos[:args.limit]
            print(f"⚠️  限制下载数量: {args.limit}")

        # 显示视频列表
        show_video_list(videos)

        # 确认下载
        if not args.yes:
            response = input("\n是否开始下载? (y/n): ").strip().lower()
            if response != 'y':
                print("⏭️  跳过此作者")
                continue

        # 批量下载
        results = batch_download(videos, author_name, args.output)
        all_results[author_name] = results

        # 保存报告
        save_report(results, author_name, args.output)

    # 总体统计
    if len(csv_files) > 1:
        print("\n" + "=" * 80)
        print("🎉 全部完成!")
        print("=" * 80)

        total_videos = sum(len(r) for r in all_results.values())
        total_success = sum(sum(1 for v in r if v['success'] and 'skip_reason' not in v) for r in all_results.values())
        total_skip = sum(sum(1 for v in r if v['success'] and 'skip_reason' in v) for r in all_results.values())
        total_fail = sum(sum(1 for v in r if not v['success']) for r in all_results.values())

        print(f"📊 总体统计:")
        print(f"   作者数: {len(all_results)}")
        print(f"   总视频: {total_videos}")
        print(f"   成功: {total_success} | 跳过: {total_skip} | 失败: {total_fail}")


if __name__ == "__main__":
    main()
