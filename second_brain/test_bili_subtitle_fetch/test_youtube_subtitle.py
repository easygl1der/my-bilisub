"""
YouTube 字幕获取测试 - 使用 youtube-transcript-api

环境准备:
    pip install youtube-transcript-api

功能:
    - 获取人工字幕
    - 获取 AI 自动生成字幕
    - 支持多语言
    - 不需要 API Key
"""

import sys
import json
from pathlib import Path

# Windows 编码修复
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter, SRTFormatter, JSONFormatter
except ImportError:
    print("错误: 未安装 youtube-transcript-api")
    print("请运行: pip install youtube-transcript-api")
    sys.exit(1)


# ============= 配置区 =============
# 测试视频 ID (YouTube 视频 ID，不是完整 URL)
TEST_VIDEO_ID = "dQw4w9WgXcQ"  # Rick Roll，有多语言字幕

# 或使用其他测试视频
# TEST_VIDEO_ID = "jNQXAC9IVRw"  # "Me at the zoo" - YouTube 第一个视频
# TEST_VIDEO_ID = "3dCli9yqQG4"  # 有中文自动字幕的视频
# =================================


def extract_video_id(url_or_id: str) -> str:
    """从 URL 或 ID 中提取视频 ID"""
    if len(url_or_id) == 11 and not url_or_id.startswith("http"):
        return url_or_id

    import re
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def list_transcripts(video_id: str):
    """列出视频所有可用字幕"""
    print("=" * 50)
    print(f"获取视频 {video_id} 的字幕列表...")
    print("=" * 50)

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        print("\n【可用字幕】")
        for transcript in transcript_list:
            lang_name = get_language_name(transcript.language_code)
            generated = " (AI生成)" if hasattr(transcript, 'is_generated') and transcript.is_generated else ""
            print(f"  - {transcript.language_code} ({lang_name}){generated}")

        return transcript_list
    except Exception as e:
        print(f"错误: {e}")
        return None


def get_language_name(code: str) -> str:
    """语言代码映射"""
    lang_map = {
        'zh': '中文',
        'zh-Hans': '简体中文',
        'zh-Hant': '繁体中文',
        'en': '英语',
        'ja': '日语',
        'ko': '韩语',
        'es': '西班牙语',
        'fr': '法语',
        'de': '德语',
        'ru': '俄语',
        'ar': '阿拉伯语',
        'pt': '葡萄牙语',
    }
    return lang_map.get(code, code)


def download_transcript(video_id: str, lang_code: str = None, output_dir: str = "output"):
    """下载字幕并保存为多种格式"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"\n下载字幕: {video_id} (语言: {lang_code})")
    print("-" * 40)

    try:
        api = YouTubeTranscriptApi()
        # 获取字幕
        if lang_code:
            fetched = api.fetch(video_id, languages=[lang_code])
        else:
            # 自动获取可用字幕
            fetched = api.fetch(video_id)

        # 获取原始数据
        transcript_data = fetched.to_raw_data()

        base_name = f"youtube_{video_id}"

        # 1. 保存 JSON 原始格式
        json_path = output_path / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON: {json_path}")

        # 2. 保存 TXT 格式
        txt_path = output_path / f"{base_name}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for entry in transcript_data:
                f.write(f"[{entry['start']:.2f}s] {entry['text']}\n")
        print(f"✓ TXT: {txt_path}")

        # 3. 保存 SRT 格式
        srt_path = output_path / f"{base_name}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, entry in enumerate(transcript_data, 1):
                start_time = format_srt_time(entry['start'])
                end_time = format_srt_time(entry['start'] + entry.get('duration', 0))
                f.write(f"{i}\n{start_time} --> {end_time}\n{entry['text']}\n\n")
        print(f"✓ SRT: {srt_path}")

        # 打印前几条预览
        print("\n【字幕预览】")
        for entry in transcript_data[:3]:
            print(f"  [{entry['start']:.2f}s] {entry['text']}")
        if len(transcript_data) > 3:
            print(f"  ... (共 {len(transcript_data)} 条)")

        return transcript_data

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def translate_transcript(video_id: str, target_lang: str = "zh-Hans"):
    """翻译 AI 自动字幕到目标语言"""
    print(f"\n翻译字幕到: {get_language_name(target_lang)}")
    print("-" * 40)

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(
            video_id,
            languages=['en'],  # 原始语言
            translate_to=target_lang
        )

        # 获取原始数据
        transcript_data = fetched.to_raw_data()

        # 保存翻译后的字幕
        output_path = Path("output")
        translated_path = output_path / f"youtube_{video_id}_translated.txt"
        with open(translated_path, "w", encoding="utf-8") as f:
            for entry in transcript_data:
                f.write(f"[{entry['start']:.2f}s] {entry['text']}\n")

        print(f"✓ 已保存翻译: {translated_path}")

        # 预览
        print("\n【翻译预览】")
        for entry in transcript_data[:3]:
            print(f"  [{entry['start']:.2f}s] {entry['text']}")

    except Exception as e:
        print(f"翻译失败: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="YouTube 字幕下载工具")
    parser.add_argument("video", nargs="?", default=TEST_VIDEO_ID, help="视频 ID 或 URL")
    parser.add_argument("--lang", "-l", default=None, help="指定语言代码 (如 zh-Hans, en)")
    parser.add_argument("--translate", "-t", action="store_true", help="翻译自动字幕")
    parser.add_argument("--list-only", action="store_true", help="只列出字幕，不下载")
    args = parser.parse_args()

    # 提取视频 ID
    video_id = extract_video_id(args.video)
    print(f"视频 ID: {video_id}")
    print(f"视频 URL: https://www.youtube.com/watch?v={video_id}")
    print()

    # 列出字幕
    transcript_list = list_transcripts(video_id)
    if not transcript_list and args.list_only:
        return

    if args.list_only:
        return

    # 下载字幕
    download_transcript(video_id, args.lang)

    # 翻译 (如果需要)
    if args.translate:
        translate_transcript(video_id)


if __name__ == "__main__":
    main()
