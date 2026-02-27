#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Video Real-time Monitoring Tool
Supports Bilibili and Xiaohongshu user video monitoring

Usage:
    python user_monitor.py --add "USER_URL" --interval 10
    python user_monitor.py --list
    python user_monitor.py --check
    python user_monitor.py --monitor
    python user_monitor.py --remove "USER_URL"
"""

import sys
import io
import argparse
import csv
import os
import re
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Set UTF-8 output for Windows
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

# Add project path - use parent directory (biliSub root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Note: Bilibili API is now implemented directly in get_bilibili_videos()

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass


# ==================== Configuration ====================

BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / "monitored_users.csv"
VIDEOS_FILE = BASE_DIR / "videos_history.csv"

DEFAULT_INTERVAL = 10  # Default check interval (minutes)


# ==================== Helper Functions ====================

def ensure_files_exist():
    """Ensure CSV files exist"""
    if not USERS_FILE.exists():
        with open(USERS_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['platform', 'user_url', 'username', 'user_id', 'check_interval_minutes', 'enabled'])

    if not VIDEOS_FILE.exists():
        with open(VIDEOS_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['platform', 'video_id', 'title', 'url', 'published_at', 'found_at', 'notified'])


def detect_platform(url: str) -> Optional[str]:
    """Detect platform from URL"""
    url_lower = url.lower()
    if 'bilibili.com' in url_lower or 'b23.tv' in url_lower:
        return 'bilibili'
    elif 'xiaohongshu.com' in url_lower or 'xhslink.com' in url_lower:
        return 'xiaohongshu'
    return None


def extract_bilibili_uid(url: str) -> Optional[str]:
    """Extract UID from Bilibili URL"""
    match = re.search(r'space\.bilibili\.com/(\d+)', url)
    if match:
        return match.group(1)
    return None


def extract_xhs_user_id(url: str) -> Optional[str]:
    """Extract user ID from Xiaohongshu URL"""
    match = re.search(r'/user/profile/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return None


def resolve_short_link(url: str) -> str:
    """Resolve short link"""
    if not HAS_REQUESTS:
        return url

    if 'b23.tv' in url:
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10,
                               headers={'User-Agent': 'Mozilla/5.0'})
            return resp.url
        except:
            return url
    return url


def normalize_user_url(url: str) -> tuple:
    """Normalize user URL, return (platform, user_url, user_id)"""
    url = url.strip()
    original_url = url

    # Resolve short link
    url = resolve_short_link(url)

    # Detect platform
    platform = detect_platform(url)
    if not platform:
        return None, None, None

    user_id = None
    if platform == 'bilibili':
        user_id = extract_bilibili_uid(url)
    elif platform == 'xiaohongshu':
        user_id = extract_xhs_user_id(url)
        if user_id:
            url = f"https://www.xiaohongshu.com/user/profile/{user_id}"

    if not user_id:
        return platform, None, None

    return platform, url, user_id


# ==================== User Management ====================

def load_users() -> List[Dict]:
    """Load monitored users list"""
    ensure_files_exist()
    users = []
    with open(USERS_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row)
    return users


def save_users(users: List[Dict]):
    """Save monitored users list"""
    with open(USERS_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['platform', 'user_url', 'username', 'user_id', 'check_interval_minutes', 'enabled'])
        writer.writeheader()
        writer.writerows(users)


def add_user(url: str, username: str = None, interval: int = DEFAULT_INTERVAL) -> bool:
    """Add monitored user"""
    platform, user_url, user_id = normalize_user_url(url)
    if not platform or not user_id:
        print(f"ERROR: Cannot recognize user URL: {url}")
        return False

    # Check if already exists
    users = load_users()
    for user in users:
        if user['user_id'] == user_id and user['platform'] == platform:
            print(f"WARNING: User already exists: [{platform}] {username or user_id}")
            return False

    # Get username if not provided
    if not username:
        if platform == 'bilibili' and HAS_BILIBILI_API:
            info = BilibiliAPI.get_user_info(user_id)
            if info:
                username = info.get('name', user_id)
        else:
            username = user_id

    # Add user
    users.append({
        'platform': platform,
        'user_url': user_url,
        'username': username,
        'user_id': user_id,
        'check_interval_minutes': str(interval),
        'enabled': '1'
    })

    save_users(users)
    print(f"SUCCESS: Added user [{platform}] {username} (UID: {user_id}, interval: {interval}min)")
    return True


def remove_user(url: str) -> bool:
    """Remove monitored user"""
    platform, user_url, user_id = normalize_user_url(url)
    if not user_id:
        print(f"ERROR: Cannot recognize user URL: {url}")
        return False

    users = load_users()
    original_count = len(users)
    users = [u for u in users if not (u['user_id'] == user_id and u['platform'] == platform)]

    if len(users) == original_count:
        print(f"WARNING: User not found: {user_id}")
        return False

    save_users(users)
    print(f"SUCCESS: Removed user: {user_id}")
    return True


def list_users():
    """List all monitored users"""
    users = load_users()
    if not users:
        print("No monitored users")
        return

    print(f"\nMonitored Users ({len(users)}):\n")
    print(f"{'Platform':<12} {'Username':<20} {'UserID':<15} {'Interval':<8} {'Status'}")
    print("-" * 70)

    for u in users:
        platform = u['platform']
        username = u['username']
        user_id = u['user_id']
        interval = u.get('check_interval_minutes', '10')
        enabled = "Enabled" if u.get('enabled', '1') == '1' else "Disabled"
        print(f"{platform:<12} {username:<20} {user_id:<15} {interval:<8} {enabled}")


# ==================== Bilibili API (Simplified) ====================

def get_bilibili_videos(user_id: str, limit: int = 10) -> List[Dict]:
    """Get Bilibili user videos using direct API calls"""
    import xml.etree.ElementTree as ET

    videos = []

    # Method 1: RSS
    rss_urls = [
        f"https://rsshub.app/bilibili/user/video/{user_id}",
        f"https://rss.yochat.cn/bilibili/user/video/{user_id}",
    ]

    for rss_url in rss_urls:
        try:
            resp = requests.get(rss_url, timeout=15)
            if resp.status_code != 200:
                continue

            if b"cost considerations" in resp.content or b"restrict access" in resp.content:
                continue

            root = ET.fromstring(resp.content)

            for item in root.findall('.//item'):
                if len(videos) >= limit:
                    break

                title = item.find('title')
                title_text = title.text if title is not None else ""

                link = item.find('link')
                link_text = link.text if link is not None else ""

                bvid_match = re.search(r'/video/(BV[\w]+)', link_text)
                if not bvid_match:
                    continue
                bvid = bvid_match.group(1)

                pub_date = item.find('pubDate')
                published = pub_date.text if pub_date is not None else ""

                videos.append({
                    "platform": "bilibili",
                    "video_id": bvid,
                    "title": title_text,
                    "url": link_text,
                    "published_at": published,
                })

            if videos:
                break
        except Exception:
            continue

    # Method 2: Direct API if RSS fails
    if not videos:
        print("   -> Trying direct Bilibili API...")
        try:
            url = "https://api.bilibili.com/x/space/arc/search"
            params = {
                "mid": user_id,
                "ps": limit,
                "pn": 1,
                "order": "pubdate"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com"
            }

            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                print(f"   -> API response code: {data.get('code')}")
                if data.get("code") == 0:
                    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
                    print(f"   -> Found {len(vlist)} videos in API response")

                    for v in vlist[:limit]:
                        videos.append({
                            "platform": "bilibili",
                            "video_id": v.get("bvid"),
                            "title": v.get("title"),
                            "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
                            "published_at": datetime.fromtimestamp(v.get("created")).isoformat() if v.get("created") else None,
                        })
                else:
                    print(f"   -> API message: {data.get('message', 'N/A')}")
        except Exception as e:
            print(f"   -> API error: {e}")

    return videos


def get_xiaohongshu_videos(user_url: str, limit: int = 10) -> List[Dict]:
    """Get Xiaohongshu user notes (simplified version)"""
    print(f"   -> Fetching Xiaohongshu notes...")

    # Check for login state
    cookie_file = Path(__file__).parent.parent / "MediaCrawler" / "xhs_cookies.json"
    if not cookie_file.exists():
        print(f"   -> WARNING: No Xiaohongshu login state found")
        return []

    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies_data = json.load(f)
            cookies = cookies_data.get('cookies', [])
            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
    except Exception as e:
        print(f"   -> WARNING: Failed to read login state: {e}")
        return []

    # Extract user ID
    user_id = extract_xhs_user_id(user_url)
    if not user_id:
        return []

    # Call Xiaohongshu API
    api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/user/notes"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie_str,
        "Content-Type": "application/json",
        "Origin": "https://www.xiaohongshu.com",
        "Referer": "https://www.xiaohongshu.com/"
    }

    payload = {
        "user_id": user_id,
        "cursor": "",
        "limit": limit,
        "sort": "time"
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"   -> WARNING: API request failed: HTTP {resp.status_code}")
            return []

        data = resp.json()
        if data.get('code') != 0:
            print(f"   -> WARNING: API error: {data.get('message', 'Unknown error')}")
            return []

        notes = data.get('data', {}).get('notes', [])
        videos = []

        for note in notes:
            note_id = note.get('note_id', '')
            title = note.get('title', 'No title')
            note_type = note.get('type', 'video')

            published_at = note.get('time', '')
            if not published_at:
                published_at = note.get('create_time', '')

            # Build note URL
            xsec_token = note.get('xsec_token', '')
            if xsec_token:
                note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"
            else:
                note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

            videos.append({
                'platform': 'xiaohongshu',
                'video_id': note_id,
                'title': title,
                'url': note_url,
                'published_at': published_at,
                'type': note_type
            })

        return videos

    except Exception as e:
        print(f"   -> ERROR: Fetch failed: {e}")
        return []


def get_user_videos(platform: str, user_url: str, user_id: str, limit: int = 10) -> List[Dict]:
    """Get user videos"""
    if platform == 'bilibili':
        return get_bilibili_videos(user_id, limit)
    elif platform == 'xiaohongshu':
        return get_xiaohongshu_videos(user_url, limit)
    return []


# ==================== Video History ====================

def load_video_history() -> Dict[tuple, Dict]:
    """Load video history, return { (platform, video_id): record }"""
    ensure_files_exist()
    history = {}

    if not VIDEOS_FILE.exists():
        return history

    with open(VIDEOS_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['platform'], row['video_id'])
            history[key] = row

    return history


def save_video_to_history(video: Dict):
    """Save video to history"""
    ensure_files_exist()

    with open(VIDEOS_FILE, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            video.get('platform', ''),
            video.get('video_id', ''),
            video.get('title', '').replace('\n', ' ').replace('\r', ''),
            video.get('url', ''),
            video.get('published_at', ''),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '0'
        ])


def check_and_save_videos(platform: str, videos: List[Dict], tolerance_minutes: int = 15) -> List[Dict]:
    """
    Check and save new videos
    Only return videos published within tolerance_minutes
    """
    history = load_video_history()
    new_videos = []

    now = datetime.now()

    for video in videos:
        video_id = video.get('video_id', '')
        if not video_id:
            continue

        key = (platform, video_id)

        # Check if already exists
        if key in history:
            continue

        # Parse published time
        published_at_str = video.get('published_at', '')
        if not published_at_str:
            published_at = now
        else:
            try:
                if 'T' in published_at_str:
                    published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                    if published_at.tzinfo:
                        published_at = published_at.replace(tzinfo=None) - timedelta(hours=8)
                else:
                    published_at = datetime.strptime(published_at_str[:19], '%Y-%m-%d %H:%M:%S')
            except:
                published_at = now

        # Check if published within tolerance
        minutes_diff = (now - published_at).total_seconds() / 60

        if minutes_diff <= tolerance_minutes:
            save_video_to_history(video)
            new_videos.append({
                **video,
                'published_at_parsed': published_at.strftime('%Y-%m-%d %H:%M:%S'),
                'minutes_ago': int(minutes_diff)
            })

    return new_videos


# ==================== Check Logic ====================

def check_user(user: Dict) -> List[Dict]:
    """Check single user's new videos"""
    platform = user['platform']
    user_url = user['user_url']
    user_id = user['user_id']
    username = user['username']
    interval = int(user.get('check_interval_minutes', DEFAULT_INTERVAL))

    print(f"\n{'='*60}")
    print(f"Checking: [{platform.upper()}] {username}")
    print(f"{'='*60}")

    # Get videos
    videos = get_user_videos(platform, user_url, user_id, limit=10)

    if not videos:
        print(f"   -> No videos found")
        return []

    print(f"   -> Got {len(videos)} videos")

    # Check new videos
    tolerance = interval + 5
    new_videos = check_and_save_videos(platform, videos, tolerance_minutes=tolerance)

    if new_videos:
        print(f"   -> Found {len(new_videos)} new video(s)! (published within {tolerance}min)")
        for v in new_videos:
            title = v.get('title', 'No title')[:40]
            minutes = v.get('minutes_ago', 0)
            print(f"      - {title}... ({minutes}min ago)")
            print(f"        {v.get('url', '')}")
    else:
        print(f"   -> No new videos")

    return new_videos


def check_all_users() -> List[Dict]:
    """Check all monitored users"""
    users = load_users()
    users = [u for u in users if u.get('enabled', '1') == '1']

    if not users:
        print("No enabled users to monitor")
        return []

    print(f"\n{'='*70}")
    print(f"Starting check for new videos...")
    print(f"   Users: {len(users)}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    all_new_videos = []
    for user in users:
        new_videos = check_user(user)
        all_new_videos.extend(new_videos)

    print(f"\n{'='*70}")
    print(f"Check complete: Found {len(all_new_videos)} new video(s)")
    print(f"{'='*70}")

    return all_new_videos


def monitor_loop(interval: int = None):
    """Continuous monitoring loop"""
    users = load_users()
    users = [u for u in users if u.get('enabled', '1') == '1']

    if not users:
        print("No enabled users to monitor, please add users first")
        return

    if interval is None:
        interval = int(users[0].get('check_interval_minutes', DEFAULT_INTERVAL))

    print(f"\n{'='*70}")
    print(f"Starting monitoring loop")
    print(f"   Check interval: {interval} minutes")
    print(f"   Users: {len(users)}")
    print(f"{'='*70}\n")

    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"\n[Round {iteration}] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            new_videos = check_all_users()

            if new_videos:
                print(f"\n=== New Video Notification ===")
                for v in new_videos:
                    print(f"   [{v.get('platform', '')}] {v.get('title', '')[:50]}")
                    print(f"   URL: {v.get('url', '')}")

            # Wait for next round
            next_check = datetime.now() + timedelta(minutes=interval)
            print(f"\nNext check: {next_check.strftime('%H:%M:%S')}")
            print(f"Waiting... (Press Ctrl+C to stop)")

            time.sleep(interval * 60)

    except KeyboardInterrupt:
        print(f"\n\nStopped by user")


# ==================== Main Program ====================

def main():
    parser = argparse.ArgumentParser(
        description='User Video Real-time Monitoring Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python user_monitor.py --add "https://space.bilibili.com/123456" --interval 10
  python user_monitor.py --add "https://www.xiaohongshu.com/user/profile/xxx"
  python user_monitor.py --list
  python user_monitor.py --check
  python user_monitor.py --monitor
  python user_monitor.py --remove "https://space.bilibili.com/123456"
        """
    )

    parser.add_argument('--add', metavar='URL', help='Add monitored user')
    parser.add_argument('--remove', metavar='URL', help='Remove monitored user')
    parser.add_argument('--list', action='store_true', help='List all monitored users')
    parser.add_argument('--check', action='store_true', help='Check all users immediately')
    parser.add_argument('--monitor', action='store_true', help='Start continuous monitoring mode')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL,
                       help=f'Check interval in minutes (default: {DEFAULT_INTERVAL})')
    parser.add_argument('--username', type=str, help='Custom username (optional)')

    args = parser.parse_args()

    # Ensure CSV files exist
    ensure_files_exist()

    # Execute operations
    if args.add:
        add_user(args.add, args.username, args.interval)

    elif args.remove:
        remove_user(args.remove)

    elif args.list:
        list_users()

    elif args.check:
        check_all_users()

    elif args.monitor:
        monitor_loop()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
