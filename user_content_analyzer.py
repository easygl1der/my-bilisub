#!/usr/bin/env python3
"""
用户视频内容分析工具 v2

功能：
1. 获取用户的所有视频链接（支持 B站 和 YouTube）
2. 批量提取视频字幕（SRT 格式）
3. 使用 Gemini API 分析每个视频的内容
4. 生成详细的分析报告

使用示例:
    # B站用户 - 获取所有视频
    python user_content_analyzer.py --user "https://space.bilibili.com/28554995" --all

    # 只下载字幕，不分析
    python user_content_analyzer.py --user "URL" --no-analysis
"""

import os
import sys
import asyncio
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ============================================================================
# 配置区
# ============================================================================

# Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = "flash-lite"

# 输出目录
OUTPUT_DIR = Path("user_analysis_output")

# 并发设置
MAX_CONCURRENT_DOWNLOADS = 3
MAX_CONCURRENT_ANALYSIS = 5

# ============================================================================
# B站 API 部分
# ============================================================================

try:
    from bilibili_api import video, Credential, user
    BILIBILI_API_AVAILABLE = True
except ImportError:
    BILIBILI_API_AVAILABLE = False

BILIBILI_COOKIE_FILE = Path(__file__).parent / "config" / "cookies_bilibili_api.txt"


# 全局 credential（初始化一次）
_bilibili_credential = None


def extract_user_id_from_url(user_url: str) -> Optional[str]:
    """从 URL 中提取用户 ID"""
    # 匹配 space.bilibili.com/数字
    match = re.search(r'space\.bilibili\.com\/(\d+)', user_url)
    if match:
        return match.group(1)
    return None


def get_bilibili_user_info_public(user_id: str) -> Optional[Dict]:
    """从用户页面 HTML 中提取用户信息"""
    try:
        url = f"https://space.bilibili.com/{user_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            html = response.text

            # 方法1: 尝试从 HTML 中提取用户名 (多种可能的模式)
            patterns = [
                r'"name":"([^"]+)"',  # JSON 格式
                r'<title[^>]*>([^<]+?)的个人空间',  # title 标签
                r'<meta property="og:title" content="([^"]+)"',  # og:title
                r'class="[^"]*user-name[^"]*"[^>]*>([^<]+)',  # 用户名 class
                r'data-user-name="([^"]+)"',  # data 属性
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    name = match.group(1).strip()
                    # 转义 Unicode 字符
                    name = name.encode('utf-8').decode('unicode_escape')
                    # 去掉可能的反斜杠
                    name = name.replace('\\', '')
                    if name and name != 'null':
                        return {
                            'name': name[:50],
                            'url': url,
                            'description': '',
                            'uid': user_id,
                        }

    except Exception as e:
        print(f"  从页面获取用户信息失败: {e}")

    return None


def get_credential():
    """获取 B站 认证凭据（单例模式）"""
    global _bilibili_credential
    if _bilibili_credential is None:
        _bilibili_credential = load_bilibili_cookies()
    return _bilibili_credential


async def get_bilibili_user_info_api(user_url: str) -> Optional[Dict]:
    """使用 bilibili-api 获取用户信息"""
    if not BILIBILI_API_AVAILABLE:
        return None

    user_id = extract_user_id_from_url(user_url)
    if not user_id:
        return None

    try:
        credential = get_credential()
        if not credential:
            return None

        from bilibili_api import user as bili_user
        u = bili_user.User(int(user_id), credential=credential)
        info = await u.get_user_info()

        return {
            'name': info.get('name', 'Unknown'),
            'url': user_url,
            'description': info.get('sign', '')[:500],
            'uid': user_id,
            'face': info.get('face', ''),
            'level': info.get('level', 0),
        }
    except Exception as e:
        print(f"  API 获取用户信息失败: {e}")
        return None


def load_bilibili_cookies():
    """加载 B站 Cookie"""
    cookies = {}
    if BILIBILI_COOKIE_FILE.exists():
        with open(BILIBILI_COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        name = parts[5].strip()
                        value = parts[6].strip()
                        cookies[name] = value

    sessdata = cookies.get("SESSDATA", "")
    bili_jct = cookies.get("bili_jct", "")
    buvid3 = cookies.get("buvid3", "")

    if not sessdata:
        print("警告: 未找到 SESSDATA")

    return Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3
    ) if sessdata else None


def get_bilibili_user_videos_ytdlp(user_url: str, fetch_full_info: bool = False) -> Tuple[List[Dict], Dict]:
    """使用 yt-dlp 获取 B站用户视频和详细信息

    Args:
        user_url: B站用户页面 URL
        fetch_full_info: 是否获取每个视频的完整信息（较慢）
    """
    if not YT_DLP_AVAILABLE:
        raise ImportError("需要安装 yt-dlp")

    # 首先获取用户ID
    user_id = extract_user_id_from_url(user_url)
    if not user_id:
        return [], {}

    user_info = {'name': f'User_{user_id}', 'url': user_url}

    # 第一步：获取视频列表 (使用 extract_flat)
    ydl_opts_flat = {
        'quiet': True,
        'extract_flat': True,
        'cookiefile': str(BILIBILI_COOKIE_FILE) if BILIBILI_COOKIE_FILE.exists() else None,
        'playlistend': 1000,
    }

    video_ids = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(user_url, download=False)

            # 尝试获取用户名
            uploader = info.get('uploader') or info.get('channel') or info.get('title')
            if uploader and uploader != 'Unknown':
                user_info['name'] = uploader

            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        video_ids.append(entry.get('id') or entry.get('bvid'))
            else:
                video_ids.append(info.get('id') or info.get('bvid'))
    except Exception as e:
        print(f"  获取视频列表失败: {e}")
        return [], user_info

    print(f"  找到 {len(video_ids)} 个视频 ID")

    # 第二步：获取每个视频的详细信息（如果需要）
    if fetch_full_info:
        print(f"  正在获取视频详细信息...")
        videos = []
        ydl_opts_full = {
            'quiet': True,
            'cookiefile': str(BILIBILI_COOKIE_FILE) if BILIBILI_COOKIE_FILE.exists() else None,
        }

        for i, bvid in enumerate(video_ids):
            if not bvid:
                continue
            video_url = f"https://www.bilibili.com/video/{bvid}"
            try:
                with yt_dlp.YoutubeDL(ydl_opts_full) as ydl:
                    vinfo = ydl.extract_info(video_url, download=False)
                    videos.append({
                        'bvid': bvid,
                        'title': (vinfo.get('title') or 'Unknown').strip()[:100],
                        'url': video_url,
                        'duration': vinfo.get('duration') or 0,
                        'view_count': vinfo.get('view_count') or 0,
                        'upload_date': vinfo.get('upload_date', ''),
                        'duration_string': vinfo.get('duration_string', '') or format_duration(vinfo.get('duration', 0)),
                    })
                if (i + 1) % 10 == 0:
                    print(f"    进度: {i + 1}/{len(video_ids)}")
            except Exception as e:
                # 如果单个视频获取失败，使用基本信息
                videos.append({
                    'bvid': bvid,
                    'title': f"Video_{bvid}",
                    'url': video_url,
                    'duration': 0,
                    'view_count': 0,
                })
    else:
        # 不获取详细信息，使用基本信息
        videos = []
        for bvid in video_ids:
            if bvid:
                videos.append({
                    'bvid': bvid,
                    'title': f"Video_{bvid}",
                    'url': f"https://www.bilibili.com/video/{bvid}",
                    'duration': 0,
                    'view_count': 0,
                })

    return videos, user_info


async def get_bilibili_subtitle(bvid: str, credential, output_dir: Path) -> Optional[Path]:
    """获取 B站视频字幕"""
    try:
        from bilibili_api import video as bili_video
    except ImportError:
        return None

    v = bili_video.Video(bvid=bvid, credential=credential)

    try:
        info = await v.get_info()
        title = info.get('title', 'unknown').strip()
        # 获取统计信息
        stat = info.get('stat', {})
        view_count = stat.get('view', 0)
        cid = info['cid']
    except Exception as e:
        return None

    # 清理文件名
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:80]

    try:
        player_info = await v.get_player_info(cid=cid)
        subtitles = player_info.get("subtitle", {}).get("subtitles", [])

        if not subtitles:
            return None

        # 下载第一条字幕
        subtitle_data = subtitles[0]

        import aiohttp
        url = "https:" + subtitle_data["subtitle_url"]
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)

        # 保存为 SRT
        srt_path = output_dir / f"{safe_title}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, item in enumerate(data.get("body", []), 1):
                start = format_srt_time(item['from'])
                end = format_srt_time(item['to'])
                f.write(f"{i}\n{start} --> {end}\n{item['content']}\n\n")

        # 返回带统计信息的结果
        return {
            'path': srt_path,
            'title': title,
            'view_count': view_count,
            'subtitle_count': len(data.get("body", [])),
        }

    except Exception:
        return None


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_duration(seconds: int) -> str:
    """将秒数转换为可读时长"""
    if not seconds:
        return "未知"
    seconds = int(seconds)  # 确保是整数
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_view_count(count: int) -> str:
    """格式化播放量"""
    if not count:
        return "0"
    if count >= 10000:
        return f"{count / 10000:.1f}万"
    return str(count)


# ============================================================================
# YouTube 部分
# ============================================================================

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


# ============================================================================
# Gemini 分析部分
# ============================================================================

try:
    import google.generativeai as genai
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    GEMINI_AVAILABLE = True
except ImportError:
    try:
        from google import genai
        GEMINI_AVAILABLE = True
    except ImportError:
        GEMINI_AVAILABLE = False


# 默认提示词
ANALYSIS_PROMPTS = {
    'brief': """请用中文简洁总结这个视频字幕的核心内容（200字以内）。""",

    'summary': """请用中文详细总结这个视频字幕的主要内容，包括：
1. 视频的主题和核心观点
2. 主要讨论的问题或话题
3. 关键信息和亮点""",

    'knowledge': """你是一个专业的视频内容分析师，擅长将视频内容转化为结构化的知识库笔记。请详细分析这个视频的字幕内容，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出：

## 📋 视频基本信息
- **核心主题**: [一句话概括]
- **内容类型**: [教育课程/知识科普/新闻评论/产品测评/Vlog/其他]

## 📖 视频大意（100-200字）
[用精炼的书面语言概括视频核心内容]

## 🎯 核心观点
1. [观点1]
   - 论述内容: [详细说明]
   - 支持论据: [数据、案例、逻辑推理]

2. [观点2]
   - 论述内容: [详细说明]
   - 支持论据: [数据、案例、逻辑推理]

## 💎 金句/好词好句提取
- "金句内容"
- "金句内容"

## 📝 总结
[总结评价，值得学习的地方]"""
}


def analyze_subtitle_with_gemini(srt_path: Path, mode: str = "knowledge", model: str = "flash-lite") -> Optional[str]:
    """使用 Gemini 分析字幕文件"""
    if not GEMINI_AVAILABLE:
        return None

    if not GEMINI_API_KEY:
        return None

    genai.configure(api_key=GEMINI_API_KEY)

    # 读取字幕内容
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    # 如果字幕太长，分段处理
    if len(srt_content) > 100000:
        srt_content = srt_content[:100000] + "\n\n...(字幕过长，已截断)"

    prompt = ANALYSIS_PROMPTS.get(mode, ANALYSIS_PROMPTS['summary'])
    full_prompt = f"""以下是视频的字幕内容（SRT格式）：

```
{srt_content}
```

{prompt}

请直接输出分析结果，不要重复字幕内容。"""

    model_names = {
        'flash-lite': 'models/gemini-2.5-flash-lite',
        'flash': 'models/gemini-2.5-flash',
        'pro': 'models/gemini-2.5-pro',
    }

    try:
        gemini_model = genai.GenerativeModel(model_names.get(model, model_names['flash-lite']))
        response = gemini_model.generate_content(full_prompt)
        return response.text
    except Exception:
        return None


# ============================================================================
# 主分析器
# ============================================================================

class UserContentAnalyzer:
    """用户内容分析器"""

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or OUTPUT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.print_lock = threading.Lock()
        self.start_time = None

    def get_user_folder_name(self, user_info: Dict) -> str:
        """生成用户文件夹名称"""
        name = user_info.get('name', 'Unknown')
        # 清理文件夹名称
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)[:50]
        return safe_name

    def setup_user_directory(self, user_info: Dict) -> Path:
        """设置用户专属目录"""
        folder_name = self.get_user_folder_name(user_info)
        user_dir = self.base_dir / folder_name
        user_dir.mkdir(exist_ok=True)

        subtitle_dir = user_dir / "subtitles"
        analysis_dir = user_dir / "analysis"
        subtitle_dir.mkdir(exist_ok=True)
        analysis_dir.mkdir(exist_ok=True)

        return user_dir, subtitle_dir, analysis_dir

    def get_videos_and_info(self, user_url: str, fetch_full_info: bool = False) -> Tuple[List[Dict], Dict]:
        """获取用户视频列表和信息

        Args:
            user_url: 用户页面 URL
            fetch_full_info: 是否获取每个视频的完整信息（标题、播放量等）
        """
        print(f"获取用户视频列表...")

        if 'bilibili.com' in user_url:
            # 优先使用公开 API 获取用户信息（不需要登录）
            user_id = extract_user_id_from_url(user_url)
            user_info = None

            if user_id:
                # 方法1: 使用公开 API（最可靠）
                user_info = get_bilibili_user_info_public(user_id)
                if user_info:
                    print(f"  用户名: {user_info.get('name')}")

            # 如果公开API失败，尝试 bilibili_api
            if not user_info and BILIBILI_API_AVAILABLE:
                try:
                    user_info = asyncio.run(get_bilibili_user_info_api(user_url))
                    if user_info:
                        print(f"  用户名: {user_info.get('name')}")
                except Exception as e:
                    print(f"  bilibili_api 获取失败: {e}")

            # 获取视频列表
            videos, ytdlp_user_info = get_bilibili_user_videos_ytdlp(user_url, fetch_full_info=fetch_full_info)

            # 如果所有方法都失败，使用 yt-dlp 的结果
            if not user_info:
                user_info = ytdlp_user_info
                print(f"  用户名: {user_info.get('name')}")

        elif 'youtube.com' in user_url or 'youtu.be' in user_url:
            # YouTube 支持
            ydl_opts = {'quiet': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(user_url, download=False)
                user_info = {'name': info.get('uploader', 'Unknown')}
                videos = []
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            videos.append({
                                'id': entry.get('id'),
                                'title': entry.get('title', 'Unknown'),
                                'url': entry.get('url'),
                                'duration': entry.get('duration'),
                                'view_count': entry.get('view_count'),
                            })
        else:
            raise ValueError(f"不支持的平台: {user_url}")

        print(f"  找到 {len(videos)} 个视频")
        return videos, user_info

    def download_subtitle(self, bvid: str, title: str, subtitle_dir: Path) -> Optional[Dict]:
        """下载单个视频字幕"""
        if not BILIBILI_API_AVAILABLE:
            return None

        credential = get_credential()
        if not credential:
            return None

        try:
            result = asyncio.run(get_bilibili_subtitle(bvid, credential, subtitle_dir))
            if result and isinstance(result, dict):
                return result
            elif result and isinstance(result, Path):
                return {'path': result, 'title': title}
        except Exception:
            pass
        return None

    def download_all_subtitles(self, videos: List[Dict], subtitle_dir: Path) -> List[Dict]:
        """批量下载所有字幕"""
        print(f"\n开始下载 {len(videos)} 个视频的字幕...")

        results = []
        failed = []

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
            futures = {}
            for i, video in enumerate(videos):
                bvid = video.get('bvid')
                title = video.get('title')
                if bvid:
                    future = executor.submit(self.download_subtitle, bvid, title, subtitle_dir)
                    futures[future] = video

            for future in as_completed(futures):
                result = future.result()
                video = futures[future]
                if result:
                    results.append({**video, **result})
                    print(f"  ✓ [{video.get('title', 'Unknown')[:30]}...]")
                else:
                    failed.append(video)
                    print(f"  ✗ [{video.get('title', 'Unknown')[:30]}...] 无字幕")

        print(f"\n字幕下载完成: {len(results)}/{len(videos)}")
        return results

    def analyze_subtitle(self, srt_path: Path, title: str, analysis_dir: Path, mode: str, model: str) -> Optional[str]:
        """分析单个字幕文件"""
        with self.print_lock:
            print(f"  分析: {title[:30]}...")

        result = analyze_subtitle_with_gemini(srt_path, mode, model)

        if result:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:80]
            output_path = analysis_dir / f"{safe_title}_analysis.md"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(result)

            with self.print_lock:
                print(f"    ✓ 分析完成")
            return str(output_path)

        return None

    def analyze_all_subtitles(self, subtitle_dir: Path, analysis_dir: Path, mode: str, model: str) -> List[Path]:
        """分析所有字幕文件"""
        srt_files = list(subtitle_dir.glob("*.srt"))
        if not srt_files:
            return []

        print(f"\n开始分析 {len(srt_files)} 个字幕文件...")

        results = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ANALYSIS) as executor:
            futures = {}
            for srt_path in srt_files:
                title = srt_path.stem
                future = executor.submit(self.analyze_subtitle, srt_path, title, analysis_dir, mode, model)
                futures[future] = srt_path

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(Path(result))

        print(f"\n分析完成: {len(results)}/{len(srt_files)}")
        return results

    def generate_summary_report(self, user_dir: Path, user_info: Dict, videos: List[Dict],
                               subtitle_results: List[Dict], analysis_results: List[Path],
                               elapsed_time: float) -> Path:
        """生成用户分析总结报告"""
        report_path = user_dir / "00_用户分析报告.md"

        # 计算统计信息
        total_videos = len(videos)
        total_subtitles = len(subtitle_results)
        total_views = sum(v.get('view_count', 0) for v in videos if v.get('view_count'))

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# {user_info.get('name', 'Unknown')} - 用户分析报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**用户链接**: {user_info.get('url', 'N/A')}\n\n")
            f.write("---\n\n")

            # 概览
            f.write("## 📊 概览统计\n\n")
            f.write(f"- **视频总数**: {total_videos} 个\n")
            f.write(f"- **有字幕视频**: {total_subtitles} 个\n")
            f.write(f"- **总播放量**: {format_view_count(total_views)} 次\n")
            f.write(f"- **爬取耗时**: {format_elapsed_time(elapsed_time)}\n")
            f.write(f"- **分析数量**: {len(analysis_results)} 个\n\n")

            # 视频列表
            f.write("## 📹 视频列表\n\n")

            # 按播放量排序 (确保 view_count 是有效数字)
            sorted_videos = sorted(videos, key=lambda x: (x.get('view_count') or 0), reverse=True)

            for i, video in enumerate(sorted_videos, 1):
                title = video.get('title', 'Unknown')
                url = video.get('url', '')
                views = format_view_count(video.get('view_count', 0))
                duration = video.get('duration_string', format_duration(video.get('duration', 0)))
                has_subtitle = any(s.get('bvid') == video.get('bvid') or s.get('title') == title for s in subtitle_results)

                f.write(f"### {i}. {title}\n\n")
                f.write(f"- **链接**: {url}\n")
                f.write(f"- **播放量**: {views}\n")
                f.write(f"- **时长**: {duration}\n")
                f.write(f"- **字幕**: {'✅ 有' if has_subtitle else '❌ 无'}\n")
                f.write("\n")

            # 内容分析汇总
            if analysis_results:
                f.write("## 📝 内容分析汇总\n\n")
                for analysis_path in sorted(analysis_results):
                    if analysis_path.exists():
                        title = analysis_path.stem.replace('_analysis', '')
                        f.write(f"### {title}\n\n")
                        with open(analysis_path, "r", encoding="utf-8") as af:
                            # 跳过标题和基本信息，只保留核心内容
                            lines = af.readlines()
                            in_content = False
                            content_lines = []
                            for line in lines:
                                if line.startswith("##"):
                                    in_content = True
                                if in_content:
                                    content_lines.append(line)
                            if content_lines:
                                f.write(''.join(content_lines))
                                f.write("\n\n")

        return report_path


def format_elapsed_time(seconds: float) -> str:
    """格式化耗时"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}分{secs}秒"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}小时{mins}分"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="用户视频内容分析工具 v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # B站用户 - 获取所有视频
  python user_content_analyzer.py --user "https://space.bilibili.com/28554995" --all

  # 只下载字幕，不分析
  python user_content_analyzer.py --user "URL" --no-analysis

  # 分析已有字幕目录
  python user_content_analyzer.py --dir "user_folder"
        """
    )

    parser.add_argument("--user", "-u", help="用户/频道链接")
    parser.add_argument("--dir", "-d", help="分析已有字幕目录")
    parser.add_argument("--mode", "-m", default="brief",
                       choices=["brief", "summary", "knowledge"],
                       help="分析模式 (默认: brief)")
    parser.add_argument("--model", default="flash-lite",
                       choices=["flash-lite", "flash", "pro"],
                       help="Gemini 模型 (默认: flash-lite)")
    parser.add_argument("--no-analysis", action="store_true",
                       help="只下载字幕，不进行分析")
    parser.add_argument("--all", action="store_true",
                       help="获取所有视频（不限制数量）")
    parser.add_argument("--full-info", action="store_true",
                       help="获取完整视频信息（标题、播放量等，较慢但更准确）")

    args = parser.parse_args()

    analyzer = UserContentAnalyzer()

    if args.user:
        # 分析用户
        analyzer.start_time = time.time()

        print("=" * 60)
        print("用户视频内容分析工具 v2")
        print("=" * 60)
        print(f"用户链接: {args.user}")
        print("=" * 60)

        # 获取视频列表
        videos, user_info = analyzer.get_videos_and_info(args.user, fetch_full_info=args.full_info)

        if not videos:
            print("未找到视频")
            return

        # 创建用户目录
        user_dir, subtitle_dir, analysis_dir = analyzer.setup_user_directory(user_info)
        print(f"输出目录: {user_dir}")

        # 下载字幕
        subtitle_results = analyzer.download_all_subtitles(videos, subtitle_dir)

        # 分析字幕
        analysis_results = []
        if not args.no_analysis and subtitle_results:
            analysis_results = analyzer.analyze_all_subtitles(subtitle_dir, analysis_dir, args.mode, args.model)

        # 生成报告
        elapsed_time = time.time() - analyzer.start_time
        report_path = analyzer.generate_summary_report(
            user_dir, user_info, videos, subtitle_results, analysis_results, elapsed_time
        )

        print("\n" + "=" * 60)
        print("✅ 任务完成!")
        print(f"📁 输出目录: {user_dir}")
        print(f"📄 报告文件: {report_path.name}")
        print("=" * 60)

    elif args.dir:
        # 分析已有目录
        dir_path = Path(args.dir)
        subtitle_dir = dir_path / "subtitles"
        analysis_dir = dir_path / "analysis"

        analyzer.analyze_all_subtitles(subtitle_dir, analysis_dir, args.mode, args.model)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
