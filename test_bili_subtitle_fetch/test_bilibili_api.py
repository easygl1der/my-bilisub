"""
B站字幕获取工具 - bilibili-api-python

环境准备:
    pip install bilibili-api-python

使用示例:
    # 指定 BV 号
    python test_bilibili_api.py BV1oQZ7B9EB4

    # 指定完整链接
    python test_bilibili_api.py https://www.bilibili.com/video/BV1oQZ7B9EB4

    # 指定输出目录
    python test_bilibili_api.py BV1oQZ7B9EB4 --output output

    # 只获取 JSON 格式
    python test_bilibili_api.py BV1oQZ7B9EB4 --format json
"""

import asyncio
import json
import aiohttp
import os
import sys
import re
import argparse
from pathlib import Path
from bilibili_api import video, Credential

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============= 配置区 =============
# Cookie 文件路径
COOKIE_FILE = Path(__file__).parent.parent / "config" / "cookies_bilibili_api.txt"
# =================================


def load_cookies(cookie_file: Path) -> dict:
    """从 cookie 文件加载 cookies"""
    cookies = {}
    if not cookie_file.exists():
        print(f"警告: Cookie 文件不存在: {cookie_file}")
        return cookies

    with open(cookie_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5].strip()] = parts[6].strip()
            elif "=" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    cookies[parts[0]] = parts[1].rstrip(";").strip()

    return cookies


def get_credential() -> Credential:
    """获取认证凭据"""
    cookies = load_cookies(COOKIE_FILE)
    sessdata = cookies.get("SESSDATA", "")
    bili_jct = cookies.get("bili_jct", "")
    buvid3 = cookies.get("buvid3", "")

    if not sessdata:
        print("错误: 未找到 SESSDATA")
        print(f"请检查 {COOKIE_FILE}")
        return None

    return Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3
    )


def extract_bvid(input_str: str) -> str:
    """从输入中提取 BV 号"""
    # 匹配 BV 开头的 ID
    match = re.search(r'BV[\w]+', input_str, re.IGNORECASE)
    if match:
        return match.group(0)
    return input_str


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def get_subtitle(bvid: str, output_dir: str = ".", formats: list = None):
    """获取视频字幕并保存"""

    v = video.Video(bvid=bvid, credential=get_credential())
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print(f"[1/3] 获取视频信息...")
    info = await v.get_info()
    cid = info["cid"]
    title = info['title']
    print(f"  视频标题: {title}")
    print(f"  视频作者: {info['owner']['name']}")
    print(f"  cid: {cid}")

    print("\n[2/3] 获取字幕列表...")
    player_info = await v.get_player_info(cid=cid)
    subtitles = player_info.get("subtitle", {}).get("subtitles", [])

    if not subtitles:
        print("  该视频无字幕")
        return None

    print(f"  找到 {len(subtitles)} 条字幕:")
    for i, sub in enumerate(subtitles, 1):
        print(f"    [{i}] 语言: {sub['lan_doc']} | 代码: {sub['lan']}")

    # 默认保存所有格式
    if formats is None:
        formats = ["json", "txt", "srt"]

    print(f"\n[3/3] 下载字幕内容...")

    # 清理文件名
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]

    # 下载每条字幕
    results = []
    for sub in subtitles:
        url = "https:" + sub["subtitle_url"]
        lan = sub['lan']
        lan_doc = sub['lan_doc']

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)

        base_name = f"{safe_title}_{lan}"

        # 保存 JSON
        if "json" in formats:
            json_path = output_path / f"{base_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  已保存 JSON: {json_path}")
            results.append(json_path)

        # 保存 TXT
        if "txt" in formats:
            txt_path = output_path / f"{base_name}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                for item in data.get("body", []):
                    f.write(f"[{item['from']:.1f}s -> {item['to']:.1f}s] {item['content']}\n")
            print(f"  已保存 TXT: {txt_path}")
            results.append(txt_path)

        # 保存 SRT
        if "srt" in formats:
            srt_path = output_path / f"{base_name}.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, item in enumerate(data.get("body", []), 1):
                    start_time = format_srt_time(item['from'])
                    end_time = format_srt_time(item['to'])
                    f.write(f"{i}\n{start_time} --> {end_time}\n{item['content']}\n\n")
            print(f"  已保存 SRT: {srt_path}")
            results.append(srt_path)

        # 只下载第一条就退出（默认中文）
        break

    return results


async def main():
    parser = argparse.ArgumentParser(
        description="B站字幕获取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_bilibili_api.py BV1oQZ7B9EB4
  python test_bilibili_api.py https://www.bilibili.com/video/BV1oQZ7B9EB4
  python test_bilibili_api.py BV1oQZ7B9EB4 --output output
  python test_bilibili_api.py BV1oQZ7B9EB4 --format srt
        """
    )

    parser.add_argument("video", help="视频 BV 号或完整链接")
    parser.add_argument("--output", "-o", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--format", "-f", nargs="+",
                       choices=["json", "txt", "srt"],
                       default=["json", "txt", "srt"],
                       help="输出格式 (默认: 全部)")

    args = parser.parse_args()

    # 提取 BV 号
    bvid = extract_bvid(args.video)
    print(f"视频 ID: {bvid}")

    try:
        results = await get_subtitle(bvid, output_dir=args.output, formats=args.format)
        if results:
            print(f"\n✅ 完成! 保存了 {len(results)} 个文件到 {args.output}/")
        else:
            print("\n❌ 该视频没有字幕")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
