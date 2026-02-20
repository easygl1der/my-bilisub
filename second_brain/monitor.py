#!/usr/bin/env python3
"""
视频监控模块 - 实时检测UP主发布的新视频

支持平台：
- B站 (bilibili)
- 小红书 (xiaohongshu)
- YouTube (youtube)
"""

import asyncio
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional, AsyncGenerator
from pathlib import Path
import re
import html
import urllib3
import os
import json

# 禁用 SSL 警告（仅用于开发环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ==================== 平台API ====================

class BilibiliAPI:
    """B站API"""

    BASE_URL = "https://api.bilibili.com"

    @classmethod
    def _load_cookies(cls) -> Dict[str, str]:
        """从文件加载B站 cookies"""
        cookie_files = [
            "cookies_bilibili.txt",
            "config/cookies_bilibili.txt",
            ".cookies/bilibili.txt",
        ]

        cookies = {}
        for cookie_file in cookie_files:
            cookie_path = Path(cookie_file)
            if cookie_path.exists():
                try:
                    content = cookie_path.read_text(encoding='utf-8')
                    # 支持 Netscape 格式和简单格式
                    for line in content.strip().split('\n'):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            cookies[key.strip()] = value.strip()
                    if cookies:
                        print(f"   └─ 🍪 已加载 {len(cookies)} 个 cookies")
                    break
                except Exception as e:
                    pass
        return cookies

    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """获取请求头（包含 cookies）"""
        cookies = cls._load_cookies()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com",
            "Accept": "application/json",
        }
        if cookies:
            headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        return headers

    @classmethod
    def get_user_info(cls, uid: str) -> Optional[Dict]:
        """获取用户信息"""
        url = f"{cls.BASE_URL}/x/space/acc/info"
        params = {"mid": uid}
        headers = cls._get_headers()
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10, verify=True)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    info = data["data"]
                    return {
                        "uid": uid,
                        "name": info.get("name"),
                        "avatar": info.get("face"),
                        "fans": info.get("follower"),
                        "sign": info.get("sign"),
                    }
        except requests.exceptions.SSLError:
            print(f"   └─ ⚠️ SSL错误，尝试忽略验证...")
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        info = data["data"]
                        return {
                            "uid": uid,
                            "name": info.get("name"),
                            "avatar": info.get("face"),
                            "fans": info.get("follower"),
                            "sign": info.get("sign"),
                        }
            except Exception as e:
                print(f"   └─ ❌ 获取B站用户信息失败: {e}")
        except Exception as e:
            print(f"   └─ ❌ 获取B站用户信息失败: {e}")
        return None

    @classmethod
    def get_user_videos(cls, uid: str, limit: int = 30) -> List[Dict]:
        """获取用户视频列表（多方法尝试）"""
        videos = []

        # 方法1: 优先使用RSS（更稳定，无限流问题）
        print(f"   └─ 📡 尝试RSS方式...")
        videos = cls.get_space_videos(uid, limit)

        # 方法2: 如果RSS失败，尝试B站API
        if not videos:
            print(f"   └─ 🔄 RSS失败，尝试API备用方式...")
            page = 1
            page_size = min(30, limit)
            headers = cls._get_headers()

            try:
                while len(videos) < limit:
                    url = f"{cls.BASE_URL}/x/space/arc/search"
                    params = {
                        "mid": uid,
                        "ps": page_size,
                        "pn": page,
                        "order": "pubdate"
                    }

                    resp = requests.get(url, params=params, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("code") == 0:
                            list_data = data.get("data", {}).get("list", {})
                            vlist = list_data.get("vlist", {})

                            # vlist 可能是字典，处理这种情况
                            if isinstance(vlist, dict):
                                vlist = list_data.get("arc", {}).get("list", {})

                            if not vlist:
                                break

                            for v in vlist:
                                if len(videos) >= limit:
                                    break

                                videos.append({
                                    "platform": "bilibili",
                                    "video_id": v.get("bvid"),
                                    "title": v.get("title"),
                                    "description": v.get("description"),
                                    "duration": v.get("length"),
                                    "published_at": datetime.fromtimestamp(v.get("created")).isoformat() if v.get("created") else None,
                                    "thumbnail": v.get("pic"),
                                    "view_count": v.get("play"),
                                    "danmaku_count": v.get("video_review"),
                                    "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
                                })

                            # 检查是否还有更多
                            if not vlist or len(vlist) < page_size:
                                break

                            page += 1
                        else:
                            print(f"   └─ ⚠️ API返回错误: {data.get('message', '未知错误')}")
                            break
                    else:
                        print(f"   └─ ⚠️ API请求失败: HTTP {resp.status_code}")
                        break
            except requests.exceptions.SSLError:
                print(f"   └─ ⚠️ SSL错误")
            except Exception as e:
                print(f"   └─ ⚠️ API方式失败: {e}")

        # 方法3: 如果API也失败，尝试HTML解析
        if not videos:
            print(f"   └─ 🌐 API失败，尝试HTML页面解析...")
            videos = cls.get_videos_from_html(uid, limit)

        return videos

    @classmethod
    def get_space_videos(cls, uid: str, limit: int = 30) -> List[Dict]:
        """通过RSS获取空间视频（备用方法，不依赖feedparser）"""
        # 尝试多个 RSS 源
        rss_urls = [
            f"https://rsshub.app/bilibili/user/video/{uid}",
            f"https://rss.yochat.cn/bilibili/user/video/{uid}",
        ]

        for rss_url in rss_urls:
            try:
                resp = requests.get(rss_url, timeout=15)
                if resp.status_code != 200:
                    continue

                # 检查是否是 RSSHub 的限制消息
                if b"cost considerations" in resp.content or b"restrict access" in resp.content:
                    continue

                root = ET.fromstring(resp.content)
                # RSS 2.0 format
                videos = []

                for item in root.findall('.//item'):
                    if len(videos) >= limit:
                        break

                    # 获取标题
                    title = item.find('title')
                    title_text = title.text if title is not None else ""

                    # 获取链接
                    link = item.find('link')
                    link_text = link.text if link is not None else ""

                    # 提取bvid
                    bvid_match = re.search(r'/video/(BV[\w]+)', link_text)
                    if not bvid_match:
                        continue
                    bvid = bvid_match.group(1)

                    # 获取发布时间
                    pub_date = item.find('pubDate')
                    published = pub_date.text if pub_date is not None else ""

                    # 获取描述
                    desc = item.find('description')
                    description = desc.text if desc is not None else ""

                    videos.append({
                        "platform": "bilibili",
                        "video_id": bvid,
                        "title": title_text,
                        "description": description,
                        "published_at": published,
                        "url": link_text,
                    })

                if videos:
                    return videos

            except Exception as e:
                continue

        return []

    @classmethod
    def get_videos_from_html(cls, uid: str, limit: int = 30) -> List[Dict]:
        """通过解析B站空间页面获取视频（最后的备用方法）"""
        space_url = f"https://space.bilibili.com/{uid}/video"
        headers = cls._get_headers()
        videos = []

        try:
            resp = requests.get(space_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []

            # 使用正则表达式从 HTML 中提取视频数据
            # B站页面通常包含一个 __INITIAL_STATE__ 对象
            pattern = r'window\.__INITIAL_STATE__\s*=\s*({.*?});'
            match = re.search(pattern, resp.text)

            if match:
                data_str = match.group(1)
                try:
                    data = json.loads(data_str)

                    # 尝试从不同路径获取视频列表
                    video_list = None
                    if 'videoUserDetail' in data:
                        video_list = data['videoUserDetail'].get('list', {}).get('list', {}).get('vlist', [])
                    elif 'space' in data:
                        video_list = data['space'].get('videoList', [])

                    if video_list and isinstance(video_list, list):
                        for v in video_list[:limit]:
                            bvid = v.get('bvid') or v.get('aid')
                            if not bvid:
                                continue

                            videos.append({
                                "platform": "bilibili",
                                "video_id": bvid,
                                "title": v.get('title', ''),
                                "description": v.get('description', ''),
                                "duration": v.get('length', ''),
                                "published_at": datetime.fromtimestamp(v.get('created', 0)).isoformat() if v.get('created') else None,
                                "thumbnail": v.get('pic', ''),
                                "view_count": v.get('play', 0),
                                "danmaku_count": v.get('video_review', 0),
                                "url": f"https://www.bilibili.com/video/{bvid}",
                            })

                except json.JSONDecodeError:
                    pass

            # 如果 __INITIAL_STATE__ 方法失败，尝试用 BeautifulSoup
            if not videos and HAS_BS4:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # 查找视频卡片元素
                video_cards = soup.find_all('a', href=re.compile(r'/video/BV'))
                for card in video_cards[:limit]:
                    href = card.get('href', '')
                    bvid_match = re.search(r'BV[\w]+', href)
                    if bvid_match:
                        bvid = bvid_match.group(0)
                        title_elem = card.find('span', class_='video-title') or card.find('title')
                        title = title_elem.get('title', '') if title_elem and hasattr(title_elem, 'get') else card.get_text(strip=True)

                        videos.append({
                            "platform": "bilibili",
                            "video_id": bvid,
                            "title": title,
                            "url": f"https://www.bilibili.com/video/{bvid}",
                        })

        except Exception as e:
            print(f"   └─ ⚠️ HTML解析失败: {e}")

        return videos


class XiaohongshuAPI:
    """小红书API"""

    @classmethod
    def get_user_videos(cls, uid: str, limit: int = 30) -> List[Dict]:
        """获取用户视频列表（通过爬虫或API）"""
        # 小红书需要特殊的API或爬虫方式
        # 这里使用简化的实现，实际需要使用 MediaCrawler 中的方法
        print(f"   └─ ⚠️ 小红书API暂未完整实现，请使用 MediaCrawler")
        return []

    @classmethod
    def get_user_info(cls, uid: str) -> Optional[Dict]:
        """获取用户信息"""
        # 需要通过爬虫获取
        return None


class YouTubeAPI:
    """YouTube API"""

    RSS_BASE = "https://www.youtube.com/feeds/videos.xml"

    @classmethod
    def _parse_rss_regex(cls, content: str, limit: int) -> List[Dict]:
        """使用正则表达式解析RSS（当xml.etree不可用时）"""
        videos = []

        try:
            # 提取所有 <entry> 标签的内容
            entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL)

            for entry_content in entries[:limit]:
                # 提取视频ID
                video_id_match = re.search(r'<videoId>([^<]+)</videoId>', entry_content)
                video_id = video_id_match.group(1) if video_id_match else ""

                # 提取标题
                title_match = re.search(r'<title>([^<]+)</title>', entry_content)
                title = title_match.group(1) if title_match else ""
                title = html.unescape(title) if title else ""

                # 提取链接
                link_match = re.search(r'<link[^>]+href="([^"]+)"', entry_content)
                url = link_match.group(1) if link_match else ""

                # 提取发布时间
                published_match = re.search(r'<published>([^<]+)</published>', entry_content)
                published = published_match.group(1) if published_match else ""

                # 提取描述
                desc_match = re.search(r'<media:description>([^<]*)</media:description>', entry_content)
                description = desc_match.group(1) if desc_match else ""
                if description:
                    description = html.unescape(description)

                # 提取缩略图
                thumbnail_match = re.search(r'<yt:thumbnail url="([^"]+)"', entry_content)
                thumbnail = thumbnail_match.group(1) if thumbnail_match else ""

                if video_id:
                    videos.append({
                        "platform": "youtube",
                        "video_id": video_id,
                        "title": title,
                        "description": description,
                        "published_at": published,
                        "thumbnail": thumbnail,
                        "url": url,
                    })
        except Exception as e:
            pass

        return videos

    @classmethod
    def _parse_rss(cls, rss_url: str, limit: int = 30) -> List[Dict]:
        """解析RSS（优先使用xml.etree，失败则用正则）"""
        try:
            resp = requests.get(rss_url, timeout=15)
            if resp.status_code != 200:
                return []

            content = resp.text

            # 先尝试使用 xml.etree
            try:
                root = ET.fromstring(resp.content)
                # YouTube使用Atom格式
                ns = {'atom': 'http://www.w3.org/2005/Atom',
                      'yt': 'http://www.youtube.com/xml/schemas/2015',
                      'media': 'http://search.yahoo.com/mrss/'}

                videos = []
                for entry in root.findall('atom:entry', ns):
                    if len(videos) >= limit:
                        break

                    # 获取视频ID
                    video_id = entry.find('atom:id', ns).text.split(':')[-1] if entry.find('atom:id', ns) is not None else ""

                    # 获取标题
                    title_elem = entry.find('atom:title', ns)
                    title = title_elem.text if title_elem is not None else ""

                    # 获取链接
                    link_elem = entry.find('atom:link', ns)
                    url = link_elem.get('href') if link_elem is not None else ""

                    # 获取发布时间
                    published_elem = entry.find('atom:published', ns)
                    published = published_elem.text if published_elem is not None else ""

                    # 获取描述
                    content_elem = entry.find('atom:content', ns)
                    description = content_elem.text if content_elem is not None else ""
                    if description:
                        description = html.unescape(description)

                    # 获取缩略图
                    thumbnail_elem = entry.find('atom:group/atom:thumbnail', ns)
                    thumbnail = thumbnail_elem.get('url') if thumbnail_elem is not None else ""

                    videos.append({
                        "platform": "youtube",
                        "video_id": video_id,
                        "title": title,
                        "description": description,
                        "published_at": published,
                        "thumbnail": thumbnail,
                        "url": url,
                    })

                return videos
            except (ImportError, Exception) as e:
                # xml.etree 失败，使用正则表达式解析
                print(f"   └─ ⚠️ XML解析失败，使用正则解析...")
                return cls._parse_rss_regex(content, limit)

        except Exception as e:
            print(f"   └─ ❌ 解析RSS失败: {e}")
            return []

    @classmethod
    def get_channel_videos(cls, channel_id: str, limit: int = 30) -> List[Dict]:
        """获取频道视频列表（通过RSS，无需API Key）"""
        rss_url = f"{cls.RSS_BASE}?channel_id={channel_id}"
        return cls._parse_rss(rss_url, limit)

    @classmethod
    def get_user_videos(cls, username: str, limit: int = 30) -> List[Dict]:
        """获取用户视频列表"""
        rss_url = f"{cls.RSS_BASE}?user={username}"
        return cls._parse_rss(rss_url, limit)


# ==================== 视频监控器 ====================

class VideoMonitor:
    """视频监控器 - 检测新视频"""

    def __init__(self, database):
        self.db = database
        self.platform_apis = {
            "bilibili": BilibiliAPI,
            "xiaohongshu": XiaohongshuAPI,
            "youtube": YouTubeAPI,
        }

    def check_creator(self, creator: Dict) -> List[Dict]:
        """
        检查单个博主的新视频

        Args:
            creator: 博主信息 dict

        Returns:
            新视频列表
        """
        platform = creator["platform"]
        uid = creator["uid"]
        creator_id = creator.get("db_id")

        print(f"\n{'='*60}")
        print(f"📺 检查: [{platform.upper()}] {creator['name']}")
        print(f"{'='*60}")

        api_class = self.platform_apis.get(platform)
        if not api_class:
            print(f"   └─ ❌ 不支持的平台: {platform}")
            return []

        # 获取视频列表
        max_videos = 50  # 每次最多获取50个
        videos = api_class.get_user_videos(uid, limit=max_videos)

        if not videos:
            print(f"   └─ 📭 未找到视频")
            return []

        # 过滤新视频
        new_videos = []
        for video in videos:
            video_id = video.get("video_id", "")
            if not video_id:
                continue

            if not self.db.video_exists(video_id, platform):
                # 保存到数据库
                video_id_in_db = self.db.add_video(
                    creator_id=creator_id,
                    platform=platform,
                    video_id=video_id,
                    title=video.get("title", ""),
                    description=video.get("description", ""),
                    duration=int(video.get("duration", 0)) if video.get("duration", "").isdigit() else None,
                    published_at=video.get("published_at"),
                    thumbnail_url=video.get("thumbnail"),
                    video_url=video.get("url"),
                    view_count=int(video.get("view_count", 0) or 0),
                    danmaku_count=int(video.get("danmaku_count", 0) or 0)
                )

                new_videos.append({
                    **video,
                    "db_id": video_id_in_db
                })

        # 记录日志
        self.db.log(platform, "check", len(videos), f"发现 {len(new_videos)} 个新视频")

        if new_videos:
            print(f"   └─ ✅ 发现 {len(new_videos)} 个新视频！")
            for v in new_videos:
                print(f"      - {v.get('title', '未知标题')[:40]}... ({v.get('published_at', '')[:10]})")
        else:
            print(f"   └─ ✅ 暂无新视频")

        return new_videos

    def check_all_creators(self, creators: List[Dict]) -> List[Dict]:
        """
        检查所有博主的新视频

        Args:
            creators: 博主列表

        Returns:
            所有新视频列表
        """
        all_new_videos = []

        for creator in creators:
            # 如果没有db_id，先尝试获取
            if not creator.get("db_id"):
                existing = self.db.get_creator(creator["platform"], creator["uid"])
                if existing:
                    creator["db_id"] = existing["id"]
                else:
                    # 添加新博主到数据库
                    api_class = self.platform_apis.get(creator["platform"])
                    if api_class and hasattr(api_class, "get_user_info"):
                        info = api_class.get_user_info(creator["uid"])
                        if info:
                            creator["db_id"] = self.db.add_creator(
                                platform=creator["platform"],
                                uid=creator["uid"],
                                name=info.get("name", creator.get("name", "")),
                                category=creator.get("category", ""),
                                avatar_url=info.get("avatar"),
                                fans_count=info.get("fans", 0)
                            )
                        else:
                            creator["db_id"] = self.db.add_creator(
                                platform=creator["platform"],
                                uid=creator["uid"],
                                name=creator.get("name", ""),
                                category=creator.get("category", "")
                            )

            new_videos = self.check_creator(creator)
            all_new_videos.extend(new_videos)

        return all_new_videos

    def run_once(self, creators: List[Dict]) -> Dict[str, int]:
        """
        运行一次检查

        Returns:
            统计信息
        """
        print(f"\n{'='*70}")
        print(f"🔍 开始检查新视频...")
        print(f"   博主数量: {len(creators)}")
        print(f"   检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        start_time = time.time()
        new_videos = self.check_all_creators(creators)
        elapsed = time.time() - start_time

        stats = {
            "total_creators": len(creators),
            "new_videos": len(new_videos),
            "elapsed_time": elapsed,
        }

        print(f"\n{'='*70}")
        print(f"📊 检查完成")
        print(f"{'='*70}")
        print(f"   检查博主: {stats['total_creators']} 个")
        print(f"   新增视频: {stats['new_videos']} 个")
        print(f"   耗时: {stats['elapsed_time']:.1f} 秒")

        return stats

    def run_loop(self, creators: List[Dict], interval: int = 300,
                 callback=None, max_iterations: int = None):
        """
        持续监控循环

        Args:
            creators: 博主列表
            interval: 检查间隔（秒）
            callback: 发现新视频时的回调函数
            max_iterations: 最大迭代次数（None=无限）
        """
        iteration = 0

        print(f"\n{'='*70}")
        print(f"🔄 启动监控循环")
        print(f"   检查间隔: {interval} 秒 ({interval//60} 分钟)")
        print(f"   博主数量: {len(creators)}")
        print(f"{'='*70}\n")

        try:
            while True:
                iteration += 1
                print(f"\n📍 第 {iteration} 轮检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # 检查新视频
                new_videos = self.check_all_creators(creators)

                # 调用回调
                if callback and new_videos:
                    try:
                        callback(new_videos)
                    except Exception as e:
                        print(f"   └─ ❌ 回调执行失败: {e}")

                # 检查是否退出
                if max_iterations and iteration >= max_iterations:
                    print(f"\n✅ 达到最大迭代次数 ({max_iterations})，退出监控")
                    break

                # 等待下一轮
                next_check = datetime.now() + timedelta(seconds=interval)
                print(f"\n⏰ 下次检查: {next_check.strftime('%H:%M:%S')}")
                print(f"   等待中... (按 Ctrl+C 停止)")

                time.sleep(interval)

        except KeyboardInterrupt:
            print(f"\n\n⚠️ 用户中断，停止监控")
        except Exception as e:
            print(f"\n\n❌ 监控出错: {e}")
            raise


# ==================== 命令行工具 ====================

def add_creator_command(db, platform: str, uid: str, name: str, category: str = ""):
    """添加博主命令"""
    # 检查是否已存在
    existing = db.get_creator(platform, uid)
    if existing:
        print(f"⚠️ 博主已存在: [{platform}] {name}")
        return

    # 添加到数据库
    creator_id = db.add_creator(platform, uid, name, category)
    print(f"✅ 添加博主: [{platform}] {name} (ID: {creator_id})")


def list_creators_command(db):
    """列出博主命令"""
    creators = db.get_creators()

    if not creators:
        print("📭 暂无博主")
        return

    print(f"\n📺 博主列表 ({len(creators)} 个):\n")
    print(f"{'平台':<12} {'UID':<20} {'名称':<20} {'分类':<10} {'状态'}")
    print("-" * 80)

    for c in creators:
        status = "✅ 启用" if c["enabled"] else "❌ 禁用"
        print(f"{c['platform']:<12} {c['uid']:<20} {c['name']:<20} {c.get('category', '') or 'N/A':<10} {status}")


def check_once_command(db, config):
    """单次检查命令"""
    creators = db.get_creators(enabled_only=True)

    if not creators:
        print("❌ 没有启用的博主，请先添加博主")
        return

    monitor = VideoMonitor(db)
    monitor.run_once(creators)


def monitor_command(db, config):
    """持续监控命令"""
    creators = db.get_creators(enabled_only=True)

    if not creators:
        print("❌ 没有启用的博主，请先添加博主")
        return

    interval = config.get("monitor.check_interval", 300)

    # 发现新视频时的回调
    def on_new_videos(videos):
        print(f"\n🔔 新视频通知: {len(videos)} 个")
        # 这里可以添加推送通知逻辑

    monitor = VideoMonitor(db)
    monitor.run_loop(creators, interval=interval, callback=on_new_videos)
