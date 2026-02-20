"""
B站字幕获取测试 - 方法二：yt-dlp

环境准备:
    pip install yt-dlp

Cookie 配置:
    1. 优先使用 ../config/cookies_bilibili.txt 文件
    2. 如使用浏览器，设置 BROWSER = "chrome"
"""

import yt_dlp
import json
from pathlib import Path


# ============= 配置区 =============
# 测试视频 BV 号
TEST_BVID = "BV1oQZ7B9EB4"

# Cookie 来源: 文件路径 或浏览器名称 (chrome, firefox, edge)
# 文件路径优先级更高
COOKIE_FILE = Path(__file__).parent.parent / "config" / "cookies_bilibili.txt"
BROWSER = "chrome"  # 仅当 COOKIE_FILE 不存在时使用

# 字幕语言
LANG = "zh-Hans"
# =================================


def get_ydl_opts(use_list: bool = False) -> dict:
    """构建 yt-dlp 配置"""
    opts = {
        "quiet": False,
        "no_cookies": True,  # 不保存 cookies 回文件
    }

    # Cookie 配置：优先使用文件
    if COOKIE_FILE.exists():
        opts["cookiefile"] = str(COOKIE_FILE)
        print(f"使用 Cookie 文件: {COOKIE_FILE}")
    else:
        opts["cookiesfrombrowser"] = (BROWSER,)
        print(f"使用浏览器 Cookie: {BROWSER}")

    if use_list:
        opts["listsubtitles"] = True

    return opts


def list_subtitles(bvid: str):
    """列出视频所有可用字幕"""
    url = f"https://www.bilibili.com/video/{bvid}"
    ydl_opts = get_ydl_opts(use_list=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=False)


def download_subtitle(bvid: str, lang: str = "zh-Hans", output_dir: str = "output"):
    """下载视频字幕"""
    url = f"https://www.bilibili.com/video/{bvid}"
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # 基础配置
    ydl_opts = get_ydl_opts()
    ydl_opts.update({
        "skip_download": True,           # 不下载视频
        "writesubtitles": True,          # 下载人工字幕
        "writeautomaticsub": True,       # 下载 AI 自动字幕
        "subtitleslangs": [lang],
        "subtitlesformat": "json3",      # bilibili 原始格式
        "outtmpl": str(output_path / f"{bvid}.%(ext)s"),
    })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print("=" * 50)
        print(f"开始下载 {bvid} 的字幕...")
        print(f"目标语言: {lang}")
        print("=" * 50)

        info = ydl.extract_info(url, download=True)

        print("\n" + "=" * 50)
        print("下载结果:")
        print(f"  视频标题: {info.get('title')}")
        print(f"  可用字幕: {list(info.get('subtitles', {}).keys())}")
        print(f"  可用自动字幕: {list(info.get('automatic_captions', {}).keys())}")

    # 检查下载的文件
    downloaded_files = list(output_path.glob(f"{bvid}*.{lang}.*"))
    if downloaded_files:
        print(f"\n已下载文件:")
        for f in downloaded_files:
            print(f"  - {f}")

            # 如果是 JSON 格式，尝试解析并转换为其他格式
            if f.suffix == ".json3" or f.suffix == ".json":
                convert_subtitle_json(f, output_path)


def convert_subtitle_json(json_path: Path, output_dir: Path):
    """将 yt-dlp 下载的 JSON 字幕转换为 SRT 和 TXT"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        base_name = json_path.stem.replace(f".{json_path.suffix.split('.')[-1]}", "")

        # yt-dlp 的 JSON 格式: events 数组
        events = data.get("events", [])

        # 转换为 SRT
        srt_path = output_dir / f"{base_name}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, event in enumerate(events, 1):
                # yt-dlp 时间格式可能是 "start: 1.234, duration: 5.678"
                start = event.get("tStart", 0) / 1000  # 转换为秒
                duration = event.get("dDurationMs", 0) / 1000
                end = start + duration

                # 或使用 seps 字段: "start:1.234,end:6.912"
                if "seps" in event:
                    parts = event["seps"].split(",")
                    start = float(parts[0].split(":")[1])
                    end = float(parts[1].split(":")[1])

                content = event.get("secontent", "").strip()

                start_time = format_srt_time(start)
                end_time = format_srt_time(end)

                f.write(f"{i}\n{start_time} --> {end_time}\n{content}\n\n")

        print(f"    转换生成: {srt_path}")

        # 转换为 TXT
        txt_path = output_dir / f"{base_name}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for event in events:
                start = event.get("tStart", 0) / 1000
                duration = event.get("dDurationMs", 0) / 1000
                end = start + duration
                content = event.get("secontent", "").strip()
                f.write(f"[{start:.1f}s -> {end:.1f}s] {content}\n")

        print(f"    转换生成: {txt_path}")

    except Exception as e:
        print(f"    转换失败: {e}")


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        TEST_BVID = sys.argv[1]
    if len(sys.argv) > 2:
        LANG = sys.argv[2]

    print(f"测试视频: {TEST_BVID}")
    print(f"字幕语言: {LANG}")
    if COOKIE_FILE.exists():
        print(f"Cookie 来源: 文件 ({COOKIE_FILE})")
    else:
        print(f"Cookie 来源: {BROWSER} 浏览器")
    print()

    # 先列出可用字幕
    print("第一步: 列出可用字幕")
    print("-" * 30)
    list_subtitles(TEST_BVID)

    print("\n第二步: 下载字幕")
    print("-" * 30)
    download_subtitle(TEST_BVID, LANG)
