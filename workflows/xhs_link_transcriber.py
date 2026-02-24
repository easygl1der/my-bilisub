#!/usr/bin/env python3
"""
小红书链接转录工具

功能：
1. 自动检测小红书笔记类型（视频/图文）
2. 视频笔记：下载视频 → Gemini分析 + Whisper字幕
3. 图文笔记：提取图片 → Gemini图文分析

使用示例:
    # 处理单个链接
    python xhs_link_transcriber.py --url "小红书链接"

    # 批量处理 CSV
    python xhs_link_transcriber.py --csv notes.csv

    # 仅 Gemini 分析（不生成 SRT）
    python xhs_link_transcriber.py --csv notes.csv --no-srt

    # 指定 Gemini 分析模式
    python xhs_link_transcriber.py --csv notes.csv --analysis-mode knowledge
"""

import os
import sys
import re
import json
import csv
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

import requests
from datetime import timedelta

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

# Gemini 模型配置
GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',
    'flash': 'gemini-2.5-flash',
    'pro': 'gemini-2.5-pro',
}

# 输出目录
DEFAULT_OUTPUT_DIR = "xhs_transcription_output"


# ==================== API 配置 ====================

def get_api_key() -> str:
    """
    获取 Gemini API Key

    优先级:
    1. 环境变量 GEMINI_API_KEY
    2. config_api.py 配置文件
    """
    # 1. 尝试从环境变量获取
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # 2. 尝试从 config_api.py 获取
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from config.config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


# ==================== 链接类型检测 ====================

def sanitize_filename(name: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    name = ''.join(char for char in name if ord(char) >= 32)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]
    return name or "untitled"


def detect_note_type(url: str) -> Tuple[Optional[str], str, str, List[str]]:
    """
    检测小红书笔记类型

    Args:
        url: 小红书笔记链接

    Returns:
        (类型, 标题, 描述, 媒体URL列表)
        类型: 'video' | 'normal' | None
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    print(f"   └─ 📡 检测笔记类型...")

    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

        if response.status_code != 200:
            print(f"   └─ ❌ 请求失败: {response.status_code}")
            return None, "", "", []

        if '/404?' in response.url or '你访问的页面不见了' in response.text:
            print(f"   └─ ❌ 页面无法访问（反爬虫保护或链接失效）")
            return None, "", "", []

        html = response.text

    except Exception as e:
        print(f"   └─ ❌ 请求失败: {e}")
        return None, "", "", []

    # 提取标题
    title = "小红书笔记"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
        try:
            title = title.encode('raw_unicode_escape').decode('unicode_escape')
        except:
            try:
                title = title.encode('latin1').decode('utf-8')
            except:
                pass

    # 提取描述
    desc = ""
    try:
        desc_patterns = [
            r'"desc":"([^"]+)"',
            r'"desc":\s*"([^"]+)"',
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html)
            if desc_match:
                try:
                    desc = desc_match.group(1).encode('raw_unicode_escape').decode('unicode_escape')
                except:
                    try:
                        desc = desc_match.group(1).encode('latin1').decode('utf-8')
                    except:
                        desc = desc_match.group(1)
                if desc:
                    break
    except:
        pass

    # 解析 __INITIAL_STATE__
    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx == -1:
        print(f"   └─ ⚠️  未找到 __INITIAL_STATE__，无法检测类型")
        return None, title, desc, []

    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    # 查找笔记类型
    note_type = None
    image_urls = []

    # 方法1: 查找 note.noteDetail.type 字段
    # 先尝试查找更具体的 type 字段（避免匹配到错误的 default）
    type_patterns = [
        r'"note".*?"noteDetail".*?"type"\s*:\s*"(\w+)"',  # note.noteDetail.type
        r'"type"\s*:\s*"(video|normal)"',  # 直接匹配 video 或 normal
        r'"model_type"\s*:\s*"(\w+)"',  # model_type 字段
    ]

    for pattern in type_patterns:
        type_match = re.search(pattern, json_str, re.DOTALL)
        if type_match:
            note_type = type_match.group(1)
            if note_type in ['video', 'normal']:
                print(f"   └─ ✅ 检测到类型: {note_type}")
                break

    # 如果还是没找到，检查是否有 video 字段（有 video 说明是视频）
    if note_type not in ['video', 'normal']:
        if '"video"' in json_str and '"media"' in json_str:
            note_type = 'video'
            print(f"   └─ ✅ 根据内容判断为: video")
        elif '"imageList"' in json_str:
            note_type = 'normal'
            print(f"   └─ ✅ 根据内容判断为: normal")

    # 提取图片 URL（用于图文）
    if note_type == 'normal':
        # 查找 imageList
        list_start = json_str.find('"imageList"')
        if list_start >= 0:
            bracket_start = json_str.find('[', list_start)
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
                    img_url = match.group(1)
                    if img_url:
                        try:
                            img_url = img_url.encode('utf-8').decode('unicode_escape')
                        except:
                            pass
                        img_url = img_url.replace(r'\/', '/')
                        if img_url.startswith('http://'):
                            img_url = 'https://' + img_url[7:]
                        if 'xhscdn' in img_url:
                            image_urls.append(img_url)

    return note_type, title, desc, image_urls


# ==================== 视频处理模块 ====================

class VideoNoteProcessor:
    """视频笔记处理器"""

    def __init__(self, output_dir: str, api_key: str = None):
        self.output_dir = Path(output_dir) / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or get_api_key()

    def download_video(self, url: str, title: str) -> Optional[Path]:
        """
        使用 yt-dlp 下载小红书视频

        Args:
            url: 小红书链接
            title: 笔记标题

        Returns:
            下载的视频文件路径
        """
        safe_title = sanitize_filename(title)
        output_file = self.output_dir / safe_title / f"{safe_title}.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 检查是否已存在
        if output_file.exists() and output_file.stat().st_size > 1000:
            print(f"   └─ ⏭️  视频已存在: {output_file.name}")
            return output_file

        print(f"   └─ 📥 下载视频...")

        # 使用 yt-dlp 下载
        import yt_dlp

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(self.output_dir / safe_title / f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'concurrentfragments': 4,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.xiaohongshu.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)

            # 查找下载的文件
            if output_file.exists():
                file_size = output_file.stat().st_size / 1024 / 1024
                print(f"   └─ ✅ 下载完成: {file_size:.1f}MB")
                return output_file
            else:
                # 尝试找任何视频文件
                for ext in ['.mp4', '.mkv', '.webm']:
                    candidate = self.output_dir / safe_title / f"{safe_title}{ext}"
                    if candidate.exists():
                        print(f"   └─ ✅ 下载完成: {candidate.name}")
                        return candidate
                print(f"   └─ ❌ 未找到下载的视频文件")
                return None

        except Exception as e:
            print(f"   └─ ❌ 下载失败: {e}")
            return None

    def process_with_gemini(self, video_path: Path, title: str,
                           mode: str = 'knowledge', model: str = 'flash-lite',
                           url: str = None, likes: int = 0, comments: int = 0) -> bool:
        """
        使用 Gemini 分析视频

        Args:
            video_path: 视频文件路径
            title: 笔记标题
            mode: 分析模式
            model: Gemini 模型
            url: 原始链接
            likes: 点赞数
            comments: 评论数

        Returns:
            是否成功
        """
        # 导入 Gemini 相关模块
        try:
            import google.generativeai as genai
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
        except ImportError:
            print(f"   └─ ❌ 未安装 google-generativeai 库")
            return False

        if not self.api_key:
            print(f"   └─ ❌ 未配置 Gemini API Key")
            return False

        print(f"   └─ 🤖 Gemini 分析中...")

        # 获取视频时长
        try:
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
                capture_output=True, text=True, timeout=10
            )
            duration_sec = float(result.stdout.strip()) if result.stdout.strip() else 0
            duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}" if duration_sec else "未知"
        except:
            duration_sec = 0
            duration_str = "未知"

        start_time = time.time()

        try:
            genai.configure(api_key=self.api_key)
            model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash-lite'])
            gen_model = genai.GenerativeModel(model_name)

            # 上传视频
            print(f"   └─ 📤 上传视频到 Gemini...")
            video_file = genai.upload_file(path=str(video_path))

            # 等待处理
            print(f"   └─ ⏳ 等待视频处理...")
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name != "ACTIVE":
                print(f"   └─ ❌ 视频处理失败: {video_file.state.name}")
                genai.delete_file(video_file.name)
                return False

            # 构建提示词
            prompt = self._get_prompt(mode)

            # 分析视频
            print(f"   └─ 🔄 分析中...")
            response = gen_model.generate_content([video_file, prompt])

            # 提取 token 使用信息
            token_info = {
                'prompt_tokens': 0,
                'candidates_tokens': 0,
                'total_tokens': 0
            }
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info['prompt_tokens'] = response.usage_metadata.prompt_token_count or 0
                token_info['candidates_tokens'] = response.usage_metadata.candidates_token_count or 0
                token_info['total_tokens'] = response.usage_metadata.total_token_count or 0

            # 删除上传的文件
            genai.delete_file(video_file.name)

            elapsed = time.time() - start_time

            # 保存结果
            output_file = video_path.parent / "analysis.md"
            self._save_result(
                output_file, title, response.text, mode, model_name,
                url=url, likes=likes, comments=comments,
                duration=duration_str, duration_sec=duration_sec,
                elapsed=elapsed, token_info=token_info
            )

            print(f"   └─ ✅ 分析完成 ({elapsed:.1f}秒)")
            if token_info['total_tokens'] > 0:
                print(f"   └─ 📊 Token: {token_info['total_tokens']:,}")
            return True

        except Exception as e:
            print(f"   └─ ❌ 分析失败: {e}")
            return False

    def process_with_whisper(self, video_path: Path, title: str,
                            model_size: str = 'base') -> Optional[Path]:
        """
        使用 Whisper 转录视频生成 SRT 字幕

        Args:
            video_path: 视频文件路径
            title: 笔记标题
            model_size: Whisper 模型大小

        Returns:
            SRT 文件路径
        """
        import whisper
        from datetime import timedelta

        print(f"   └─ 🎙️  Whisper 转录中... (模型: {model_size})")

        try:
            # 加载模型
            model = whisper.load_model(model_size)

            # 转录
            result = model.transcribe(str(video_path), language='zh')

            # 生成 SRT
            srt_path = video_path.parent / "subtitle.srt"

            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(result['segments'], 1):
                    start_time = timedelta(seconds=segment['start'])
                    end_time = timedelta(seconds=segment['end'])
                    text = segment['text'].strip()

                    f.write(f"{i}\n")
                    f.write(f"{self._format_timedelta(start_time)} --> {self._format_timedelta(end_time)}\n")
                    f.write(f"{text}\n\n")

            print(f"   └─ ✅ 字幕生成完成")
            return srt_path

        except Exception as e:
            print(f"   └─ ❌ 转录失败: {e}")
            return None

    def _format_timedelta(self, td: timedelta) -> str:
        """格式化时间差为 SRT 时间格式"""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def _get_prompt(self, mode: str) -> str:
        """获取分析提示词"""
        if mode == 'knowledge':
            return """你是一个专业的视频内容分析师，擅长将视频内容转化为结构化的知识库笔记。请详细分析这个视频，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 视频基本信息
- **视频类型**: [教育课程/知识科普/新闻评论/产品测评/生活分享/其他]
- **核心主题**: [一句话概括]
- **内容风格**: [干货教程/种草推荐/日常生活/观点分享]

## 📖 视频大意（100-200字）
[用精炼的书面语言概括视频核心内容]

## 🎯 核心观点
[如果视频有明确观点，列出主要论点]

## 💡 亮点与价值
### 独特之处
[这个视频与众不同的地方]

### 实用价值
- **参考性**: [高/中/低] - [说明]

## 🔗 相关延伸
[基于视频内容，推荐值得深入了解的相关话题]

请确保输出结构完整，每个部分都要有实质内容。"""
        else:
            return """请用中文详细总结这个视频的主要内容，包括：
1. 视频的主题和核心观点
2. 主要讨论的问题或话题
3. 关键信息和亮点
4. 任何值得注意的细节"""

    def _save_result(self, output_file: Path, title: str, result: str,
                     mode: str, model: str, url: str = None, likes: int = 0,
                     comments: int = 0, duration: str = "", duration_sec: float = 0,
                     elapsed: float = 0, token_info: dict = None):
        """保存分析结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title} - Gemini 视频分析\n\n")

            # 视频信息表格
            f.write(f"## 📹 视频信息\n\n")
            f.write(f"| 项目 | 内容 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| **笔记标题** | {title} |\n")
            if url:
                f.write(f"| **原始链接** | [{url}]({url}) |\n")
            f.write(f"| **视频时长** | {duration} |\n")
            if likes > 0:
                f.write(f"| **点赞数** | {likes:,} |\n")
            if comments > 0:
                f.write(f"| **评论数** | {comments:,} |\n")

            # 分析信息
            f.write(f"\n## 📊 分析信息\n\n")
            f.write(f"| 项目 | 内容 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
            f.write(f"| **使用模型** | {model} |\n")
            f.write(f"| **分析模式** | {mode} |\n")
            f.write(f"| **处理耗时** | {elapsed:.1f}秒 |\n")
            if duration_sec > 0:
                f.write(f"| **实时比率** | {duration_sec/elapsed:.1f}x |\n")

            # Token 使用
            if token_info and token_info.get('total_tokens', 0) > 0:
                f.write(f"\n## 💰 Token 使用\n\n")
                f.write(f"| 项目 | 数量 |\n")
                f.write(f"|------|------|\n")
                f.write(f"| **输入 Token** | {token_info.get('prompt_tokens', 0):,} |\n")
                f.write(f"| **输出 Token** | {token_info.get('candidates_tokens', 0):,} |\n")
                f.write(f"| **总计 Token** | {token_info.get('total_tokens', 0):,} |\n")

            f.write(f"\n---\n\n")
            f.write(f"## 🤖 AI 分析结果\n\n")
            f.write(result)


# ==================== 图文处理模块 ====================

class ImageNoteProcessor:
    """图文笔记处理器"""

    def __init__(self, output_dir: str, api_key: str = None):
        self.output_dir = Path(output_dir) / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or get_api_key()

    def process(self, url: str, title: str, desc: str, image_urls: List[str],
                mode: str = 'knowledge', model: str = 'flash-lite') -> bool:
        """
        处理图文笔记

        Args:
            url: 小红书链接
            title: 笔记标题
            desc: 笔记描述
            image_urls: 图片URL列表
            mode: 分析模式
            model: Gemini 模型

        Returns:
            是否成功
        """
        # 导入 Gemini 相关模块
        try:
            import google.generativeai as genai
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
        except ImportError:
            print(f"   └─ ❌ 未安装 google-generativeai 库")
            return False

        if not self.api_key:
            print(f"   └─ ❌ 未配置 Gemini API Key")
            return False

        # 创建笔记目录
        safe_title = sanitize_filename(title)
        note_dir = self.output_dir / safe_title
        note_dir.mkdir(parents=True, exist_ok=True)

        # 下载图片
        print(f"   └─ 📥 下载 {len(image_urls)} 张图片...")
        downloaded_paths = self._download_images(image_urls, note_dir)

        if not downloaded_paths:
            print(f"   └─ ❌ 图片下载失败")
            return False

        # 上传图片到 Gemini
        print(f"   └─ 📤 上传图片到 Gemini...")

        try:
            genai.configure(api_key=self.api_key)
            model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash-lite'])
            gen_model = genai.GenerativeModel(model_name)

            uploaded_files = []
            for img_path in downloaded_paths:
                try:
                    img_file = genai.upload_file(path=str(img_path))
                    while img_file.state.name == "PROCESSING":
                        time.sleep(1)
                        img_file = genai.get_file(img_file.name)
                    if img_file.state.name == "ACTIVE":
                        uploaded_files.append(img_file)
                except:
                    pass

            if not uploaded_files:
                print(f"   └─ ❌ 图片上传失败")
                return False

            print(f"   └─ ✅ 上传了 {len(uploaded_files)} 张图片")

            # 构建提示词
            text_content = f"笔记标题: {title}\n\n笔记描述: {desc}\n\n"
            prompt = self._get_prompt(mode, text_content)

            # 分析图文
            print(f"   └─ 🔄 分析中...")
            contents = uploaded_files + [prompt]
            response = gen_model.generate_content(contents)

            # 删除上传的文件
            for f in uploaded_files:
                try:
                    genai.delete_file(f.name)
                except:
                    pass

            # 保存结果
            output_file = note_dir / "analysis.md"
            self._save_result(output_file, title, desc, response.text, mode, model_name)

            print(f"   └─ ✅ 分析完成")
            return True

        except Exception as e:
            print(f"   └─ ❌ 分析失败: {e}")
            return False

    def _download_images(self, image_urls: List[str], output_dir: Path) -> List[Path]:
        """下载图片"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
        }

        downloaded_paths = []

        for i, img_url in enumerate(image_urls, 1):
            try:
                print(f"   └─ [{i}/{len(image_urls)}] 下载中...", end='\r')
                img_response = requests.get(img_url, headers=headers, timeout=30)

                if img_response.status_code == 200:
                    # 确定扩展名
                    content_type = img_response.headers.get('Content-Type', '')
                    if 'png' in content_type:
                        ext = '.png'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    else:
                        ext = '.jpg'

                    filename = f"image_{i:02d}{ext}"
                    filepath = output_dir / filename

                    with open(filepath, 'wb') as f:
                        f.write(img_response.content)

                    downloaded_paths.append(filepath)
            except:
                pass

        print(f"   └─ ✅ 下载了 {len(downloaded_paths)}/{len(image_urls)} 张图片")
        return downloaded_paths

    def _get_prompt(self, mode: str, text: str) -> str:
        """获取分析提示词"""
        if mode == 'knowledge':
            return f"""你是一个专业的小红书图文笔记分析师，擅长将图文内容转化为结构化的知识库笔记。请分析以下图文笔记，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 笔记基本信息
- **笔记类型**: [穿搭分享/美妆教程/美食探店/旅行攻略/知识科普/产品测评/生活记录/其他]
- **核心主题**: [一句话概括]
- **内容风格**: [干货教程/种草推荐/日常生活/观点分享]

## 📖 图文内容摘要（150-250字）
[结合图片和文字，用精炼的语言概括笔记核心内容]

## 🎯 核心信息提取
### 主题/产品
- **主要对象**: [笔记介绍的主要产品/地点/话题]
- **关键特点**: [列举3-5个关键特点]

## 📸 图片分析
[分析图片内容]
- **图片数量**: 若干张
- **图片风格**: [实拍图/街拍图/摆拍图/平铺图/细节图]
- **视觉效果**: [图片的氛围感、色调、构图等]

## 💡 亮点与价值
### 独特之处
[这篇笔记与众不同的地方]

### 实用价值
- **参考性**: [高/中/低] - [说明]

请确保输出结构完整，每个部分都要有实质内容。

## 笔记文字内容:

{text}"""
        else:
            return f"""请用中文详细总结这个图文笔记的内容，包括：
1. 笔记的主题和类型
2. 主要展示的产品/内容/场景
3. 关键信息和亮点
4. 图片的视觉效果

## 笔记文字内容:

{text}"""

    def _save_result(self, output_file: Path, title: str, desc: str,
                     result: str, mode: str, model: str):
        """保存分析结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title} - 图文分析\n\n")
            f.write(f"## 📌 元信息\n\n")
            f.write(f"| 项目 | 内容 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| **笔记标题** | {title} |\n")
            f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
            f.write(f"| **使用模型** | {model} |\n")
            f.write(f"| **分析模式** | {mode} |\n")
            f.write(f"\n---\n\n")
            f.write(f"## 📄 原始文字内容\n\n")
            f.write(f"{desc}\n\n")
            f.write(f"---\n\n")
            f.write(f"## 🤖 AI 分析结果\n\n")
            f.write(result)


# ==================== 主处理流程 ====================

def process_note(url: str, output_dir: str = DEFAULT_OUTPUT_DIR,
                generate_srt: bool = True, analysis_mode: str = 'knowledge',
                gemini_model: str = 'flash-lite', whisper_model: str = 'base',
                known_type: str = None, likes: int = 0, comments: int = 0) -> Dict:
    """
    处理单个小红书笔记

    Args:
        url: 小红书链接
        output_dir: 输出目录
        generate_srt: 是否生成 SRT 字幕
        analysis_mode: Gemini 分析模式
        gemini_model: Gemini 模型
        whisper_model: Whisper 模型
        known_type: 已知的笔记类型
        likes: 点赞数
        comments: 评论数

    Returns:
        处理结果字典
    """
    result = {
        'url': url,
        'type': None,
        'title': '',
        'success': False,
        'error': None,
        'output_dir': None
    }

    print(f"\n{'='*60}")
    print(f"处理: {url[:60]}...")
    print(f"{'='*60}")

    # 如果已知类型，直接使用；否则检测
    if known_type and known_type in ['video', 'normal']:
        note_type = known_type
        title = ""  # 需要从页面获取
        desc = ""
        image_urls = []
        print(f"   └─ 📋 使用已知类型: {note_type}")
        # 仍需要获取标题
        _, title, _, _ = detect_note_type(url)
    else:
        # 检测笔记类型
        note_type, title, desc, image_urls = detect_note_type(url)

    if note_type not in ['video', 'normal']:
        result['error'] = f"无法识别的笔记类型: {note_type}"
        return result

    result['type'] = note_type
    result['title'] = title

    # 根据类型处理
    if note_type == 'video':
        print(f"   └─ 🎬 视频笔记")

        video_processor = VideoNoteProcessor(output_dir)

        # 下载视频
        video_path = video_processor.download_video(url, title)
        if not video_path:
            result['error'] = "视频下载失败"
            return result

        # Gemini 分析
        if not video_processor.process_with_gemini(video_path, title, analysis_mode, gemini_model, url, likes, comments):
            result['error'] = "Gemini 分析失败"
            return result

        # Whisper 转录
        if generate_srt:
            video_processor.process_with_whisper(video_path, title, whisper_model)

        result['success'] = True
        result['output_dir'] = str(video_path.parent)

    elif note_type == 'normal':
        print(f"   └─ 📕 图文笔记")

        image_processor = ImageNoteProcessor(output_dir)

        if not image_processor.process(url, title, desc, image_urls, analysis_mode, gemini_model):
            result['error'] = "图文分析失败"
            return result

        result['success'] = True
        result['output_dir'] = str(image_processor.output_dir / sanitize_filename(title))

    else:
        result['error'] = f"未知笔记类型: {note_type}"
        return result

    return result


def process_csv(csv_path: str, output_dir: str = DEFAULT_OUTPUT_DIR,
                generate_srt: bool = True, analysis_mode: str = 'knowledge',
                gemini_model: str = 'flash-lite', whisper_model: str = 'base',
                limit: int = None) -> List[Dict]:
    """
    批量处理 CSV 文件

    Args:
        csv_path: CSV 文件路径
        output_dir: 输出目录
        generate_srt: 是否生成 SRT 字幕
        analysis_mode: Gemini 分析模式
        gemini_model: Gemini 模型
        whisper_model: Whisper 模型
        limit: 限制处理数量

    Returns:
        处理结果列表
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        return []

    # 读取 CSV
    notes = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('链接', '') or row.get('url', '')
            if url:
                # 解析点赞数和评论数
                try:
                    likes = int(row.get('点赞数', 0) or row.get('likes', 0) or 0)
                    comments = int(row.get('评论数', 0) or row.get('comments', 0) or 0)
                except (ValueError, TypeError):
                    likes = 0
                    comments = 0

                notes.append({
                    'url': url,
                    'title': row.get('标题', '') or row.get('title', ''),
                    'type': row.get('类型', '') or row.get('type', ''),
                    'likes': likes,
                    'comments': comments
                })

    if not notes:
        print(f"❌ CSV 中没有有效链接")
        return []

    print(f"\n📋 找到 {len(notes)} 个笔记")

    # 限制处理数量
    if limit and limit < len(notes):
        notes = notes[:limit]
        print(f"⚠️  限制处理数量: {limit}")

    # 处理每个笔记
    results = []
    for i, note in enumerate(notes, 1):
        print(f"\n[{i}/{len(notes)}] ", end='')
        result = process_note(
            note['url'],
            output_dir,
            generate_srt,
            analysis_mode,
            gemini_model,
            whisper_model,
            note.get('type'),  # 传递 CSV 中的类型
            note.get('likes', 0),  # 传递点赞数
            note.get('comments', 0)  # 传递评论数
        )
        results.append(result)

        # 避免请求过快
        if i < len(notes):
            time.sleep(2)

    # 打印总结
    print(f"\n{'='*60}")
    print(f"📊 处理完成")
    print(f"{'='*60}")
    success = sum(1 for r in results if r['success'])
    failed = len(results) - success
    print(f"总计: {len(results)} | 成功: {success} | 失败: {failed}")

    # 保存摘要
    summary_path = Path(output_dir) / "summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['链接', '标题', '类型', '状态', '输出目录', '错误'])
        for r in results:
            writer.writerow([
                r['url'],
                r['title'],
                r['type'] or '',
                '成功' if r['success'] else '失败',
                r.get('output_dir', ''),
                r.get('error', '')
            ])
    print(f"📄 摘要已保存: {summary_path}")

    return results


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书链接转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 处理单个链接:
   python xhs_link_transcriber.py --url "小红书链接"

2. 批量处理 CSV:
   python xhs_link_transcriber.py --csv notes.csv

3. 仅 Gemini 分析（不生成 SRT）:
   python xhs_link_transcriber.py --csv notes.csv --no-srt

4. 指定 Gemini 分析模式:
   python xhs_link_transcriber.py --csv notes.csv --analysis-mode knowledge
        """
    )

    parser.add_argument('--url', help='小红书笔记链接')
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_DIR, help='输出目录')
    parser.add_argument('--no-srt', action='store_true', help='不生成 SRT 字幕')
    parser.add_argument('--analysis-mode', choices=['knowledge', 'summary'],
                       default='knowledge', help='Gemini 分析模式')
    parser.add_argument('--gemini-model', choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite', help='Gemini 模型')
    parser.add_argument('--whisper-model', choices=['tiny', 'base', 'small', 'medium', 'large'],
                       default='base', help='Whisper 模型')
    parser.add_argument('--limit', type=int, help='限制处理数量（用于测试）')

    args = parser.parse_args()

    # 检查输入
    if not args.url and not args.csv:
        parser.print_help()
        return

    # 检查 API Key
    if not get_api_key():
        print("❌ 未配置 Gemini API Key")
        print("\n请通过以下方式之一配置 API Key:")
        print("1. 设置环境变量: export GEMINI_API_KEY='your-key'")
        print("2. 在 config_api.py 中添加:")
        print('   API_CONFIG = {"gemini": {"api_key": "your-key"}}')
        return

    # 处理
    if args.url:
        process_note(
            args.url,
            args.output,
            not args.no_srt,
            args.analysis_mode,
            args.gemini_model,
            args.whisper_model
        )
    else:
        process_csv(
            args.csv,
            args.output,
            not args.no_srt,
            args.analysis_mode,
            args.gemini_model,
            args.whisper_model,
            args.limit
        )


if __name__ == "__main__":
    main()
