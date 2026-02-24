#!/usr/bin/env python3
"""
AI自动刷B站首页并总结

一键完成：
1. 刷新B站首页推荐（自定义次数）
2. 采集视频信息并导出CSV
3. 批量提取内置字幕
4. AI生成分析报告（推送趋势+详细分类）

使用示例:
    # 默认配置（刷新3次，最多50个视频）
    python ai_bilibili_homepage.py

    # 仅采集，生成CSV
    python ai_bilibili_homepage.py --mode scrape

    # 采集+提取字幕
    python ai_bilibili_homepage.py --mode scrape+subtitle

    # 完整流程（采集+字幕+AI）
    python ai_bilibili_homepage.py --mode full --model flash-lite

    # 自定义刷新次数和视频数
    python ai_bilibili_homepage.py --refresh-count 5 --max-videos 100 --mode full

    # 从已有CSV开始提取字幕
    python ai_bilibili_homepage.py --csv homepage_videos_2025-02-23.csv --mode scrape+subtitle

    # 仅对已有字幕生成AI摘要
    python ai_bilibili_homepage.py --csv homepage_videos_2025-02-23.csv --mode summary-only
"""

import argparse
import asyncio
import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

# Windows编码修复 - 始终启用UTF-8输出
if sys.platform == 'win32':
    try:
        import io
        # 无论是否在TTY中都强制使用UTF-8
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (ValueError, AttributeError):
        pass

from playwright.async_api import async_playwright
import httpx
from bs4 import BeautifulSoup
import time
import os

# 延迟导入 Gemini API（仅在需要时导入）
_gemini_available = False
try:
    from google import genai
    _gemini_available = True
except ImportError:
    try:
        import google.generativeai as genai
        _gemini_available = True
    except ImportError:
        pass

# 延迟导入 bilibili_api（仅在需要时导入）
_bilibili_api_available = False
try:
    from bilibili_api import video, Credential
    import aiohttp
    _bilibili_api_available = True
except ImportError:
    pass


# ==================== 路径配置 ====================
PROJECT_DIR = Path(__file__).parent.parent  # 获取根目录
MEDIA_CRAWLER_DIR = PROJECT_DIR / "MediaCrawler"
SUBTITLE_OUTPUT = MEDIA_CRAWLER_DIR / "bilibili_subtitles"


# ==================== Cookie 读取 ====================
def read_bilibili_cookie():
    """从 config/cookies.txt 读取 Bilibili Cookie"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    if not cookie_file.exists():
        print("Cookie文件不存在")
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


# ==================== 获取关注列表 ====================
async def get_following_list(cookie_str: str) -> set:
    """
    获取用户的关注列表（UP主UID集合）

    Returns:
        set: 已关注UP主的UID集合
    """
    following_uids = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
        "Cookie": cookie_str,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 首先获取用户自己的UID
            nav_url = "https://api.bilibili.com/x/web-interface/nav"
            nav_response = await client.get(nav_url, headers=headers)

            # 调试：显示响应状态
            print(f"  导航API响应状态: {nav_response.status_code}")

            if nav_response.status_code != 200:
                print(f"⚠️  导航API请求失败，状态码: {nav_response.status_code}")
                return following_uids

            try:
                nav_data = nav_response.json()
            except Exception as e:
                print(f"⚠️  API响应解析失败: {e}")
                return following_uids

            if nav_data.get("code") != 0:
                print(f"⚠️  API返回错误: code={nav_data.get('code')}, message={nav_data.get('message', '未知错误')}")
                return following_uids

            user_mid = nav_data.get("data", {}).get("mid")
            if not user_mid:
                print("⚠️  未登录或无法获取用户ID，跳过关注列表获取")
                return following_uids

            print(f"🔍 获取关注列表 (用户ID: {user_mid})...")

            # 获取关注列表（分页获取）
            page = 1
            page_size = 50  # 每页50个

            while page <= 10:  # 最多获取10页（500个关注）
                follow_url = f"https://api.bilibili.com/x/relation/followings?vmid={user_mid}&pn={page}&ps={page_size}&order=desc"

                response = await client.get(follow_url, headers=headers)

                if response.status_code != 200:
                    print(f"  第{page}页请求失败，状态码: {response.status_code}")
                    break

                data = response.json()

                if data.get("code") == 0:
                    followings = data.get("data", {}).get("list", [])

                    if not followings:
                        print(f"  第{page}页: 没有更多关注")
                        break

                    for item in followings:
                        mid = item.get("mid")
                        if mid:
                            # 确保 UID 是字符串类型
                            following_uids.add(str(mid))

                    print(f"  第{page}页: 已获取 {len(following_uids)} 个关注")

                    # 检查是否还有更多
                    total = data.get("data", {}).get("total", 0)
                    if len(following_uids) >= total:
                        break

                    page += 1
                else:
                    print(f"  获取关注列表第{page}页失败: code={data.get('code')}, message={data.get('message')}")
                    break

            print(f"✅ 关注列表获取完成，共 {len(following_uids)} 个已关注UP主")

            # 调试：显示前5个关注的 UID
            if len(following_uids) > 0:
                sample_list = list(following_uids)[:5]
                print(f"  示例UID: {', '.join(sample_list)}")

    except Exception as e:
        print(f"⚠️  获取关注列表失败: {e}")

    return following_uids


# ==================== 登录验证 ====================
async def test_login(cookie_str):
    """测试 Cookie 是否有效"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
        "Cookie": cookie_str
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.bilibili.com/x/web-interface/nav",
                headers=headers
            )
            data = response.json()

            if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                user_data = data.get("data", {})
                return True, user_data.get('uname', ''), user_data.get('mid', '')
            else:
                return False, '', ''
    except Exception as e:
        print(f"登录测试失败: {e}")
        return False, '', ''


# ==================== 视频卡片解析 ====================
def parse_video_cards(page_content, following_uids: set = None):
    """
    从页面内容解析视频卡片

    Args:
        page_content: 页面HTML内容
        following_uids: 已关注UP主的UID集合（用于标记）
    """
    soup = BeautifulSoup(page_content, 'html.parser')

    videos = []
    # 查找视频卡片
    video_cards = soup.select('.bili-video-card')

    for card in video_cards:
        # 获取BV号
        video_link = card.select_one('a[href*="/video/BV"]')
        if not video_link:
            continue

        href = video_link.get('href', '')
        if 'BV' in href:
            bvid = href.split('BV')[1].split('?')[0].split('/')[0]
            bvid = 'BV' + bvid
        else:
            continue

        # 获取标题
        title_elem = card.select_one('.bili-video-card__info--tit')
        if not title_elem:
            title_elem = card.select_one('a[href*="/video/BV"]')

        if title_elem:
            title = title_elem.get('title', '') or title_elem.get_text(strip=True)
        else:
            title = ""

        # 获取UP主信息
        uploader_elem = card.select_one('.bili-video-card__info--author')
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""

        # 获取UP主链接
        uploader_link = card.select_one('a[href*="space.bilibili.com"]')
        uploader_url = ""
        uploader_uid = ""
        is_following = False
        if uploader_link:
            uploader_url = uploader_link.get('href', '')
            if uploader_url.startswith('//'):
                uploader_url = 'https:' + uploader_url

            # 提取UID
            if "space.bilibili.com/" in uploader_url:
                uid_part = uploader_url.split("space.bilibili.com/")[-1].split("?")[0].split("/")[0]
                uploader_uid = uid_part

                # 检查是否已关注
                if following_uids and uploader_uid in following_uids:
                    is_following = True

        video_info = {
            "bvid": bvid,
            "title": title,
            "uploader": uploader,
            "uploader_url": uploader_url,
            "uploader_uid": uploader_uid,
            "video_url": f"https://www.bilibili.com/video/{bvid}",
            "is_following": is_following,  # TODO: 关注标注功能待完善
        }
        videos.append(video_info)

    return videos


# ==================== 步骤1: 采集首页推荐 ====================
async def scrape_homepage_recommend(
    cookie_str: str,
    refresh_count: int = 3,
    max_videos: int = 50
) -> List[Dict]:
    """
    采集B站首页推荐视频

    Args:
        cookie_str: B站Cookie
        refresh_count: 刷新次数
        max_videos: 最大视频数

    Returns:
        视频列表，每个视频包含bvid、title、uploader、uploader_url、uploader_uid、video_url、refresh_batch、is_following
    """
    print("\n" + "=" * 70)
    print("📋 步骤 1/3: 采集首页推荐")
    print("=" * 70)

    # 测试登录
    print("🔍 测试登录状态...")
    is_logged_in, username, user_id = await test_login(cookie_str)

    if is_logged_in:
        print(f"✅ 登录成功！")
        if username:
            print(f"   用户名: {username}")
        if user_id:
            print(f"   用户ID: {user_id}")
    else:
        print("⚠️ 登录失败：Cookie可能已过期，继续尝试采集...")

    # 获取关注列表
    following_uids = await get_following_list(cookie_str)

    print()

    # 启动浏览器
    print("启动浏览器...")

    all_videos = []
    refresh_times = []  # 记录每次刷新的时间戳

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # 设置 Cookie
        cookies_list = []
        for cookie_pair in cookie_str.split(';'):
            if '=' in cookie_pair:
                name, value = cookie_pair.strip().split('=', 1)
                cookies_list.append({
                    'name': name,
                    'value': value,
                    'domain': '.bilibili.com',
                    'path': '/'
                })

        await context.add_cookies(cookies_list)

        page = await context.new_page()

        # 采集首页推荐
        for i in range(refresh_count):
            batch_num = i + 1
            print(f"第 {batch_num}/{refresh_count} 次刷新...")

            # 记录时间戳
            batch_time = datetime.now()
            refresh_times.append(batch_time)

            await page.goto("https://www.bilibili.com")
            # 优化：使用智能等待，等待关键元素加载完成
            await page.wait_for_selector('.bili-video-card', timeout=15000)
            await page.wait_for_load_state('networkidle', timeout=10000)
            await asyncio.sleep(1)  # 短暂缓冲

            # 获取页面内容
            content = await page.content()

            # 解析视频（传入关注列表）
            videos = parse_video_cards(content, following_uids)

            # 添加刷新批次信息
            for video in videos:
                video['refresh_batch'] = batch_num
                video['refresh_time'] = batch_time.strftime('%Y-%m-%d %H:%M:%S')

            # 去重（按BV号）
            seen_bvids = {v['bvid'] for v in all_videos}
            new_videos = [v for v in videos if v['bvid'] not in seen_bvids]
            new_count = len(new_videos)

            print(f"  找到 {len(videos)} 个视频（新增 {new_count} 个）")

            # 添加到总列表
            all_videos.extend(new_videos)

            if len(all_videos) >= max_videos:
                print(f"  已达到最大视频数限制 ({max_videos})，停止刷新")
                break

            # 滚动页面触发加载（为下一次刷新做准备）
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # 优化：智能滚动检测
            await page.wait_for_function("document.body.scrollHeight > 0", timeout=5000)

        await browser.close()

    print()
    print(f"✅ 采集完成！")
    print(f"   总视频数: {len(all_videos)} 个")
    print(f"   刷新批次: {len(refresh_times)} 次")

    return all_videos


# ==================== CSV 导出 ====================
def export_to_csv(videos: List[Dict], output_path: Path):
    """
    将视频列表导出为CSV文件

    Args:
        videos: 视频列表
        output_path: 输出文件路径
    """
    if not videos:
        print("⚠️ 没有视频数据可导出")
        return False

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # CSV字段
    fieldnames = [
        '序号',
        'BV号',
        '标题',
        'UP主',
        'UP主_UID',
        'UP主主页',
        '视频链接',
        '字幕状态',
        '刷新批次',
        '刷新时间',
        '是否关注'
    ]

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, video in enumerate(videos, 1):
            writer.writerow({
                '序号': i,
                'BV号': video.get('bvid', ''),
                '标题': video.get('title', ''),
                'UP主': video.get('uploader', ''),
                'UP主_UID': video.get('uploader_uid', ''),
                'UP主主页': video.get('uploader_url', ''),
                '视频链接': video.get('video_url', ''),
                '字幕状态': '待提取',
                '刷新批次': video.get('refresh_batch', ''),
                '刷新时间': video.get('refresh_time', ''),
                '是否关注': '是' if video.get('is_following', False) else '否'
            })

    print(f"   已保存: {output_path}")
    return True


# ==================== JSON 导出 ====================
def export_to_json(videos: List[Dict], output_path: Path):
    """
    将视频列表导出为JSON文件（用于调试和AI分析）

    Args:
        videos: 视频列表
        output_path: 输出文件路径
    """
    if not videos:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    print(f"   已保存: {output_path}")
    return True


# ==================== 步骤2: 字幕提取 ====================
def load_cookies_for_bilibili_api() -> dict:
    """从 config/cookies.txt 加载 cookies（用于 bilibili_api）"""
    cookie_file = PROJECT_DIR / "config" / "cookies.txt"
    cookies = {}

    if not cookie_file.exists():
        return cookies

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 [bilibili] 部分
    in_bilibili_section = False
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

    return cookies


def get_credential():
    """获取 bilibili_api 认证凭据"""
    cookies = load_cookies_for_bilibili_api()
    sessdata = cookies.get("SESSDATA", "")
    bili_jct = cookies.get("bili_jct", "")
    buvid3 = cookies.get("buvid3", "")

    if not sessdata:
        return None

    return Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3
    )


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def fetch_subtitle_srt(bvid: str, title: str, output_dir: Path) -> dict:
    """
    获取单个视频的 SRT 字幕（仅内置字幕）

    返回:
        {
            'success': bool,
            'srt_path': str or None,
            'error': str or None
        }
    """
    result = {'success': False, 'srt_path': None, 'error': None}

    if not _bilibili_api_available:
        result['error'] = 'bilibili_api 未安装'
        return result

    try:
        credential = get_credential()
        v = video.Video(bvid=bvid, credential=credential)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取视频信息
        info = await v.get_info()
        cid = info["cid"]

        # 获取字幕列表
        player_info = await v.get_player_info(cid=cid)
        subtitles = player_info.get("subtitle", {}).get("subtitles", [])

        if not subtitles:
            result['error'] = '无字幕'
            return result

        # 下载第一条字幕（通常是中文）
        sub = subtitles[0]
        url = "https:" + sub["subtitle_url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)

        # 清理文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
        srt_path = output_dir / f"{bvid}_{safe_title}.srt"

        # 保存 SRT
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, item in enumerate(data.get("body", []), 1):
                start_time = format_srt_time(item['from'])
                end_time = format_srt_time(item['to'])
                f.write(f"{i}\n{start_time} --> {end_time}\n{item['content']}\n\n")

        result['success'] = True
        result['srt_path'] = str(srt_path)

    except Exception as e:
        result['error'] = str(e)

    return result


def read_csv_videos(csv_path: Path) -> List[Dict]:
    """读取 CSV 文件，返回视频列表"""
    videos = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            videos.append(row)

    return videos


def write_csv_status(csv_path: Path, videos: List[Dict]):
    """写回 CSV 文件，更新字幕状态"""
    if not videos:
        return

    # 读取原始CSV的fieldnames，确保只写入原始字段
    original_fieldnames = []
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            original_fieldnames = reader.fieldnames or []

    # 如果没有原始字段名，使用第一个video的字段（但排除'字幕路径'）
    if not original_fieldnames:
        original_fieldnames = [k for k in videos[0].keys() if k != '字幕路径']

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=original_fieldnames)
        writer.writeheader()

        # 只写入原始字段中存在的值
        for video in videos:
            row = {k: video.get(k, '') for k in original_fieldnames}
            writer.writerow(row)


async def extract_subtitles_from_csv(
    csv_path: Path,
    subtitle_dir: Path,
    limit: int = None,
    max_concurrent: int = 5
):
    """
    从CSV文件批量提取字幕（并发优化版）

    Args:
        csv_path: CSV文件路径
        subtitle_dir: 字幕输出目录
        limit: 限制处理视频数量
        max_concurrent: 最大并发数（默认5）
    """
    print("\n" + "=" * 70)
    print("📝 步骤 2/3: 批量提取字幕（内置字幕优先）")
    print("=" * 70)

    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    print(f"📄 CSV文件: {csv_path}")
    videos = read_csv_videos(csv_path)

    if not videos:
        print("❌ CSV文件为空")
        return False

    if limit:
        videos = videos[:limit]
        print(f"🔢 限制数量: {limit}")

    print(f"📊 找到 {len(videos)} 个视频")
    print(f"⚡ 并发数: {max_concurrent}")
    print()

    # 创建字幕输出目录
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 字幕保存目录: {subtitle_dir}")
    print()

    # 统计
    success_count = 0
    no_subtitle_count = 0
    fail_count = 0
    skipped_count = 0

    # 总计时
    total_start_time = time.time()

    # 过滤需要处理的视频
    pending_tasks = []
    for i, video_data in enumerate(videos):
        bvid = video_data.get('BV号', '')

        if not bvid:
            no_subtitle_count += 1
            continue

        # 检查是否已处理
        current_status = video_data.get('字幕状态', '').strip()
        if current_status in ['已提取', '无字幕']:
            skipped_count += 1
            continue

        # 添加待处理任务
        pending_tasks.append((i, video_data))

    print(f"📋 待处理视频: {len(pending_tasks)} 个（已跳过 {skipped_count} 个）")
    print()

    # 使用信号量控制并发
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_video(index: int, video_data: dict):
        """处理单个视频的包装函数（带并发控制）"""
        async with semaphore:
            bvid = video_data.get('BV号', '')
            title = video_data.get('标题', '未命名')

            print(f"[{len(pending_tasks) - pending_tasks.count(None)}/{len(pending_tasks)}] {title[:40]}...", end='\r')

            # 获取字幕
            result = await fetch_subtitle_srt(bvid, title, subtitle_dir)

            if result['success']:
                print(f"  ✅ [{title[:30]}]")
                video_data['字幕状态'] = '已提取'
                video_data['字幕路径'] = result['srt_path']
                return 'success'
            elif result['error'] == '无字幕':
                print(f"  ⚠️  [{title[:30]}] - 无字幕")
                video_data['字幕状态'] = '无字幕'
                return 'no_subtitle'
            else:
                print(f"  ❌ [{title[:30]}] - {result['error'][:30]}")
                video_data['字幕状态'] = '提取失败'
                return 'fail'

    # 并发执行所有任务
    tasks = [process_video(i, video_data) for i, video_data in pending_tasks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计结果
    for result in results:
        if isinstance(result, Exception):
            fail_count += 1
        elif result == 'success':
            success_count += 1
        elif result == 'no_subtitle':
            no_subtitle_count += 1
        elif result == 'fail':
            fail_count += 1

    # 最终保存
    write_csv_status(csv_path, videos)

    # 总耗时
    total_elapsed = time.time() - total_start_time
    speed = len(pending_tasks) / total_elapsed if total_elapsed > 0 else 0

    print()
    print("=" * 70)
    print("✅ 字幕提取完成！")
    print(f"   成功: {success_count} 个")
    print(f"   无字幕: {no_subtitle_count} 个")
    print(f"   失败: {fail_count} 个")
    print(f"   跳过: {skipped_count} 个")
    print(f"   总耗时: {total_elapsed:.2f}秒")
    print(f"   速度: {speed:.2f} 个/秒")
    print("=" * 70)

    return success_count > 0


# ==================== 步骤3: AI分析报告生成 ====================
def get_gemini_api_key() -> str:
    """获取 Gemini API Key"""
    # 1. 环境变量
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # 2. 配置文件
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


class GeminiClient:
    """简化的 Gemini API 客户端"""

    def __init__(self, model: str = 'flash', api_key: str = None):
        self.api_key = api_key or get_gemini_api_key()
        # 直接使用传入的模型名称，不做拼接
        self.model_name = f"gemini-2.5-{model}" if model != 'flash' else 'gemini-2.5-flash'

        if not self.api_key:
            raise ValueError("未找到 Gemini API Key，请在 config_api.py 中配置或设置 GEMINI_API_KEY 环境变量")

        # 配置客户端
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.use_new_sdk = True
        except ImportError:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.use_new_sdk = False

    def generate_content(self, prompt: str, max_retries: int = 3) -> Dict:
        """生成内容（带重试机制）"""
        import time

        for attempt in range(max_retries):
            try:
                if self.use_new_sdk:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                    text = response.text
                else:
                    import google.generativeai as genai
                    model = genai.GenerativeModel(self.model_name)
                    response = model.generate_content(prompt)
                    text = response.text

                return {
                    'text': text.strip() if text else '',
                    'success': True
                }
            except Exception as e:
                error_msg = str(e)
                # 网络错误或临时性错误，可以重试
                is_retryable = any(keyword in error_msg.lower() for keyword in [
                    'server disconnected', 'network', 'timeout', 'connection',
                    'temporarily unavailable', 'rate limit', '500', '503'
                ])

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # 指数退避: 2, 4, 8秒
                    print(f"   ⚠️  API调用失败（第{attempt + 1}次尝试）: {error_msg[:100]}")
                    print(f"   🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    return {
                        'text': '',
                        'success': False,
                        'error': error_msg,
                        'retries': attempt + 1
                    }


def generate_fallback_analysis(videos: List[Dict], batch_stats: Dict) -> tuple:
    """生成基础统计分析（当AI API不可用时）"""

    # 第一部分：基础统计
    trend_lines = []
    trend_lines.append("## 刷新记录总览\n")
    trend_lines.append("| 批次 | 时间 | 新增视频数 | 累计视频数 |\n")
    trend_lines.append("|------|------|------------|------------|\n")

    cumulative = 0
    for batch_num in sorted(batch_stats.keys()):
        batch_videos = batch_stats[batch_num]
        count = len(batch_videos)
        cumulative += count
        # 获取第一个视频的时间
        time_str = batch_videos[0].get('刷新时间', '未知') if batch_videos else '未知'
        trend_lines.append(f"| {batch_num} | {time_str} | {count} | {cumulative} |\n")

    # 统计关注的UP主
    followed_count = sum(1 for v in videos if v.get('是否关注') == '是')
    trend_lines.append(f"\n**统计摘要**:\n")
    trend_lines.append(f"- 总视频数: {len(videos)}\n")
    trend_lines.append(f"- 刷新批次: {len(batch_stats)}\n")
    trend_lines.append(f"- 已关注UP主: {followed_count} 个 ({followed_count/len(videos)*100:.1f}%)\n")

    # UP主频率统计
    uploader_counts = {}
    for v in videos:
        uploader = v.get('UP主', '未知')
        uploader_counts[uploader] = uploader_counts.get(uploader, 0) + 1

    if uploader_counts:
        trend_lines.append(f"\n**UP主出现频率TOP5**:\n")
        for uploader, count in sorted(uploader_counts.items(), key=lambda x: -x[1])[:5]:
            trend_lines.append(f"- {uploader}: {count}个视频\n")

    trend_analysis = ''.join(trend_lines)

    # 第二部分：按批次列出视频
    detail_lines = []
    detail_lines.append("## 目录\n")
    detail_lines.append("| 批次 | 视频数量 | 页码 |\n")
    detail_lines.append("|------|----------|------|\n")

    for batch_num in sorted(batch_stats.keys()):
        count = len(batch_stats[batch_num])
        detail_lines.append(f"| {batch_num} | {count} | [跳转](#第{batch_num}次刷新) |\n")

    detail_lines.append("\n---\n\n")

    for batch_num in sorted(batch_stats.keys()):
        batch_videos = batch_stats[batch_num]
        detail_lines.append(f"## 第{batch_num}次刷新 ({len(batch_videos)}个视频)\n\n")

        for i, video in enumerate(batch_videos, 1):
            title = video.get('标题', '')
            bvid = video.get('BV号', '')
            uploader = video.get('UP主', '')
            uploader_uid = video.get('UP主_UID', '')
            uploader_url = video.get('UP主主页', '')
            video_url = video.get('视频链接', '')

            detail_lines.append(f"### {i}. {title}\n")
            detail_lines.append(f"- **BV号**: {bvid}\n")
            detail_lines.append(f"- **UP主**: {uploader} (UID: {uploader_uid})\n")
            detail_lines.append(f"- **UP主主页**: {uploader_url}\n")
            detail_lines.append(f"- **视频链接**: {video_url}\n")

            is_following = video.get('是否关注', '否')
            if is_following == '是':
                detail_lines.append(f"- **状态**: ✅ 已关注\n")

            detail_lines.append("\n")

    detail_analysis = ''.join(detail_lines)

    return trend_analysis, detail_analysis


def generate_ai_analysis_report(
    csv_path: Path,
    subtitle_dir: Path,
    model: str = 'flash-lite'
) -> bool:
    """
    生成AI分析报告（两部分结构）

    Args:
        csv_path: CSV文件路径
        subtitle_dir: 字幕目录路径
        model: Gemini模型名称

    Returns:
        bool: 是否成功
    """
    print("\n" + "=" * 70)
    print("🤖 步骤 3/3: 生成AI分析报告")
    print("=" * 70)

    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    # 读取视频数据
    videos = read_csv_videos(csv_path)
    if not videos:
        print("❌ CSV文件为空")
        return False

    print(f"📊 分析 {len(videos)} 个视频")
    print(f"🤖 模型: {model}")
    print()

    # 初始化 Gemini 客户端
    try:
        gemini_client = GeminiClient(model=model)
    except ValueError as e:
        print(f"❌ {e}")
        print()
        print("请配置 Gemini API Key:")
        print("1. 创建 config_api.py 文件")
        print("2. 添加内容: API_CONFIG = {'gemini': {'api_key': 'your_api_key'}}")
        print("   或设置环境变量: export GEMINI_API_KEY=your_api_key")
        return False

    # ==================== 第一部分：推送趋势分析 ====================
    print("📊 生成第一部分：推送趋势分析...")

    # 按刷新批次统计
    batch_stats = {}
    for video in videos:
        batch = video.get('刷新批次', '1')
        if batch not in batch_stats:
            batch_stats[batch] = []
        batch_stats[batch].append(video)

    # 构建推送趋势分析的 Prompt
    trend_prompt = f"""你是一个B站推荐算法分析专家。我有以下数据：

我刷新了B站首页 {len(batch_stats)} 次，每次刷新获取的视频信息如下：

"""

    for batch_num in sorted(batch_stats.keys()):
        batch_videos = batch_stats[batch_num]
        trend_prompt += f"\n第{batch_num}次刷新 ({len(batch_videos)}个视频):\n"
        for i, video in enumerate(batch_videos[:10], 1):  # 最多显示10个
            title = video.get('标题', '')[:50]
            uploader = video.get('UP主', '')
            trend_prompt += f"  {i}. {title} - UP主: {uploader}\n"
        if len(batch_videos) > 10:
            trend_prompt += f"  ... 还有 {len(batch_videos) - 10} 个视频\n"

    trend_prompt += """

请分析：
1. 每次刷新的视频主题分布和风格特点
2. 算法推送的趋势变化
3. 推测用户的兴趣偏好和算法的推荐逻辑

输出格式（使用Markdown）：
## 刷新记录总览
[用表格显示批次、视频数、主要主题]

## 各批次视频主题分布
[列出每个批次的主题分类]

## 算法推送趋势分析
[分析推送趋势和算法逻辑]
"""

    # 生成第一部分（带重试）
    print("   调用 Gemini API...")
    trend_result = gemini_client.generate_content(trend_prompt)

    if not trend_result['success']:
        retries = trend_result.get('retries', 1)
        print(f"❌ 推送趋势分析生成失败 (已重试{retries}次): {trend_result.get('error', 'Unknown error')[:150]}")
        print("   📊 使用基础统计分析...")
        # 生成基础统计作为第一部分
        trend_analysis, _ = generate_fallback_analysis(videos, batch_stats)
        trend_analysis = "## ⚠️ 注意：由于网络问题，AI分析暂时不可用，以下为基础统计分析\n\n" + trend_analysis
    else:
        trend_analysis = trend_result['text']
        print("✅ 推送趋势分析完成")
        # 显示预览
        if len(trend_analysis) > 200:
            print(f"   预览: {trend_analysis[:200]}...")

    # ==================== 并行生成两部分分析 ====================
    print()
    print("⚡ 并行生成两部分分析...")

    # 准备第二部分的prompt（在并行前构建）
    # 检查字幕文件
    subtitle_files = list(subtitle_dir.glob("*.srt")) if subtitle_dir.exists() else []
    has_subtitles = len(subtitle_files) > 0

    if has_subtitles:
        print(f"   找到 {len(subtitle_files)} 个字幕文件")
    else:
        print("   ⚠️  未找到字幕文件，将基于标题生成分析")

    # 构建详细分类分析的 Prompt
    detail_prompt = f"""你是一个视频内容分析专家。我有以下视频数据：

"""

    # 读取字幕内容（如果有）
    subtitle_contents = {}
    if has_subtitles:
        for srt_file in subtitle_files[:20]:  # 最多处理20个字幕
            bvid = srt_file.stem.split('_')[0]
            try:
                with open(srt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 只取前2000字符作为摘要
                    subtitle_contents[bvid] = content[:2000]
            except:
                pass

    # 按批次分组视频
    for batch_num in sorted(batch_stats.keys()):
        batch_videos = batch_stats[batch_num]
        detail_prompt += f"\n### 第{batch_num}次刷新 ({len(batch_videos)}个视频)\n\n"

        for video in batch_videos:
            bvid = video.get('BV号', '')
            title = video.get('标题', '')
            uploader = video.get('UP主', '')
            uploader_uid = video.get('UP主_UID', '')
            uploader_url = video.get('UP主主页', '')
            video_url = video.get('视频链接', '')

            detail_prompt += f"**{title}**\n"
            detail_prompt += f"- BV号: {bvid}\n"
            detail_prompt += f"- UP主: {uploader} (UID: {uploader_uid})\n"
            detail_prompt += f"- UP主主页: {uploader_url}\n"
            detail_prompt += f"- 视频链接: {video_url}\n"

            # 添加字幕摘要
            if bvid in subtitle_contents:
                detail_prompt += f"- 字幕摘要: {subtitle_contents[bvid][:500]}...\n"

            detail_prompt += "\n"

    detail_prompt += """

请按以下格式输出：

## 目录
| 序号 | 主题分类 | 视频数量 | 页码 |
|------|----------|----------|------|
| 1 | 主题名 | 数量 | [跳转](#主题名) |

---

## 主题名 (N个视频)

### 1. 视频标题
- **BV号**: BV1xxx
- **UP主**: 名称 (UID: xxx)
- **UP主主页**: https://space.bilibili.com/xxx
- **视频链接**: https://www.bilibili.com/video/BV1xxx
"""

    if has_subtitles:
        detail_prompt += "- **字幕摘要**: [基于字幕内容生成200-300字摘要]\n"

    detail_prompt += "- **推荐批次**: 第X次刷新\n"

    # 创建异步函数并行执行两次API调用
    async def generate_both_parts():
        """并行生成两部分分析"""
        import asyncio as _asyncio

        async def get_trend():
            return gemini_client.generate_content(trend_prompt)

        async def get_detail():
            return gemini_client.generate_content(detail_prompt)

        # 并行执行
        results = await _asyncio.gather(get_trend(), get_detail(), return_exceptions=True)
        return results

    # 执行并行调用
    print("   调用 Gemini API (并行处理趋势+详细分析)...")
    results = asyncio.run(generate_both_parts())
    trend_result = results[0] if not isinstance(results[0], Exception) else {'success': False, 'error': str(results[0])}
    detail_result = results[1] if not isinstance(results[1], Exception) else {'success': False, 'error': str(results[1])}

    # 处理趋势分析结果
    if not trend_result['success']:
        retries = trend_result.get('retries', 1)
        print(f"❌ 推送趋势分析生成失败 (已重试{retries}次): {trend_result.get('error', 'Unknown error')[:150]}")
        print("   📊 使用基础统计分析...")
        # 生成基础统计作为第一部分
        trend_analysis, _ = generate_fallback_analysis(videos, batch_stats)
        trend_analysis = "## ⚠️ 注意：由于网络问题，AI分析暂时不可用，以下为基础统计分析\n\n" + trend_analysis
    else:
        trend_analysis = trend_result['text']
        print("✅ 推送趋势分析完成")
        # 显示预览
        if len(trend_analysis) > 200:
            print(f"   预览: {trend_analysis[:200]}...")

    # 处理详细分析结果
    print()
    if not detail_result['success']:
        retries = detail_result.get('retries', 1)
        print(f"❌ 详细分类分析生成失败 (已重试{retries}次): {detail_result.get('error', 'Unknown error')[:150]}")
        print("   📊 使用基础统计分析...")
        # 生成基础列表作为第二部分
        _, detail_analysis = generate_fallback_analysis(videos, batch_stats)
        detail_analysis = "## ⚠️ 注意：由于网络问题，AI分析暂时不可用，以下为基础视频列表\n\n" + detail_analysis
    else:
        detail_analysis = detail_result['text']
        print("✅ 详细分类分析完成")
        # 显示预览
        if len(detail_analysis) > 200:
            print(f"   预览: {detail_analysis[:200]}...")

    # ==================== 保存报告 ====================
    date_str = datetime.now().strftime('%Y-%m-%d')
    report_path = SUBTITLE_OUTPUT / f"homepage_{date_str}_AI总结.md"

    report_content = f"""# B站首页推荐AI分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**采集视频数**: {len(videos)}
**刷新批次**: {len(batch_stats)}

---

"""

    report_content += trend_analysis
    report_content += "\n\n---\n\n"
    report_content += detail_analysis

    # 保存报告
    SUBTITLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print()
    print("=" * 70)
    print("✅ AI分析报告生成完成！")
    print(f"   报告路径: {report_path}")
    print("=" * 70)

    return True


# ==================== 主程序 ====================
def main():
    parser = argparse.ArgumentParser(
        description="AI自动刷B站首页并总结",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 默认配置（刷新3次，最多50个视频）
  python ai_bilibili_homepage.py

  # 仅采集，生成CSV
  python ai_bilibili_homepage.py --mode scrape

  # 采集+提取字幕
  python ai_bilibili_homepage.py --mode scrape+subtitle

  # 完整流程（采集+字幕+AI）
  python ai_bilibili_homepage.py --mode full --model flash-lite

  # 自定义刷新次数和视频数
  python ai_bilibili_homepage.py --refresh-count 5 --max-videos 100 --mode full

  # 从已有CSV开始提取字幕
  python ai_bilibili_homepage.py --csv homepage_videos_2025-02-23.csv --mode scrape+subtitle

  # 仅对已有字幕生成AI摘要
  python ai_bilibili_homepage.py --csv homepage_videos_2025-02-23.csv --mode summary-only
        """
    )

    parser.add_argument("--mode", "-m",
                        choices=['scrape', 'scrape+subtitle', 'full', 'summary-only'],
                        default='full',
                        help="处理模式：scrape(仅采集) | scrape+subtitle(采集+字幕) | full(完整流程) | summary-only(仅AI摘要)")
    parser.add_argument("--refresh-count", "-r", type=int, default=3,
                        help="刷新次数（默认：3）")
    parser.add_argument("--max-videos", "-n", type=int, default=50,
                        help="最大视频数（默认：50）")
    parser.add_argument("--csv", "-c",
                        help="使用已有的CSV文件（跳过采集步骤）")
    parser.add_argument("--model",
                        choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite',
                        help="Gemini模型（默认: flash-lite）")
    parser.add_argument("--jobs", "-j", type=int, default=3,
                        help="并发处理数（默认: 3）")

    args = parser.parse_args()

    # 生成文件名
    date_str = datetime.now().strftime('%Y-%m-%d')
    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = PROJECT_DIR / f"homepage_videos_{date_str}.csv"

    json_path = PROJECT_DIR / f"homepage_videos_{date_str}.json"

    print("\n" + "=" * 70)
    print("🤖 AI自动刷B站并总结")
    print("=" * 70)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(f"📋 配置:")
    print(f"   刷新次数: {args.refresh_count}")
    print(f"   最大视频数: {args.max_videos}")
    print(f"   处理模式: {args.mode}")
    if args.mode in ['full', 'summary-only']:
        print(f"   AI模型: {args.model}")
    print(f"   字幕策略: 内置字幕优先")

    # ==================== 步骤1: 采集首页推荐 ====================
    if args.mode != 'summary-only' and not args.csv:
        cookie_str = read_bilibili_cookie()

        if not cookie_str:
            print("\n❌ 无法读取Cookie，请检查 config/cookies.txt")
            return 1

        print(f"\n🍪 Cookie 长度: {len(cookie_str)} 字符")
        print()

        videos = asyncio.run(scrape_homepage_recommend(
            cookie_str,
            refresh_count=args.refresh_count,
            max_videos=args.max_videos
        ))

        if not videos:
            print("\n❌ 未采集到任何视频")
            return 1

        # 导出CSV和JSON
        print()
        print("💾 导出数据...")
        export_to_csv(videos, csv_path)
        export_to_json(videos, json_path)

    elif args.csv:
        print(f"\n📁 使用已有CSV: {csv_path}")
        if not csv_path.exists():
            print(f"❌ CSV文件不存在: {csv_path}")
            return 1
    else:
        print(f"\n📁 请提供CSV文件或运行采集模式")

    # ==================== 步骤2: 提取字幕 ====================
    if args.mode in ['scrape+subtitle', 'full']:
        if not _bilibili_api_available:
            print("\n" + "=" * 70)
            print("⚠️ 字幕提取功能需要 bilibili_api 模块")
            print("=" * 70)
            print("请运行以下命令安装：")
            print("  pip install bilibili-api")
            print()
            print("或者跳过字幕提取，使用仅采集模式：")
            print("  python ai_bilibili_homepage.py --mode scrape")
            print("=" * 70)
            return 1

        # 确定字幕输出目录
        date_str = datetime.now().strftime('%Y-%m-%d')
        if args.csv:
            # 从CSV文件名提取日期
            date_str = csv_path.stem.replace('homepage_videos_', '')
        subtitle_dir = SUBTITLE_OUTPUT / f"homepage_{date_str}"

        # 提取字幕
        success = asyncio.run(extract_subtitles_from_csv(csv_path, subtitle_dir))
        if not success:
            print("\n⚠️ 字幕提取失败，但继续尝试AI分析...")
    elif args.mode == 'summary-only':
        # 仅AI摘要模式，需要确定字幕目录
        date_str = csv_path.stem.replace('homepage_videos_', '')
        subtitle_dir = SUBTITLE_OUTPUT / f"homepage_{date_str}"
    else:
        # 仅采集模式，不提取字幕
        subtitle_dir = None

    # ==================== 步骤3: AI分析报告生成 ====================
    if args.mode == 'full':
        # 确定字幕目录
        date_str = datetime.now().strftime('%Y-%m-%d')
        if args.csv:
            date_str = csv_path.stem.replace('homepage_videos_', '')
        subtitle_dir = SUBTITLE_OUTPUT / f"homepage_{date_str}"

        # 生成AI分析报告
        generate_ai_analysis_report(csv_path, subtitle_dir, args.model)
    elif args.mode == 'summary-only':
        # 仅AI摘要模式
        date_str = csv_path.stem.replace('homepage_videos_', '')
        subtitle_dir = SUBTITLE_OUTPUT / f"homepage_{date_str}"
        generate_ai_analysis_report(csv_path, subtitle_dir, args.model)

    print()
    print("=" * 70)
    print("✅ 完成！")
    print("=" * 70)
    print(f"\n📁 输出文件:")
    if args.mode != 'summary-only' and not args.csv:
        print(f"  - CSV: {csv_path}")
        print(f"  - JSON: {json_path}")

    # 显示AI分析报告路径
    if args.mode == 'full':
        date_str = datetime.now().strftime('%Y-%m-%d')
        if args.csv:
            date_str = csv_path.stem.replace('homepage_videos_', '')
        report_path = SUBTITLE_OUTPUT / f"homepage_{date_str}_AI总结.md"
        print(f"  - AI分析报告: {report_path}")
    elif args.mode == 'summary-only':
        date_str = csv_path.stem.replace('homepage_videos_', '')
        report_path = SUBTITLE_OUTPUT / f"homepage_{date_str}_AI总结.md"
        print(f"  - AI分析报告: {report_path}")
    print()
    print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
