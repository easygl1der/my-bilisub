"""
B站字幕获取测试 - 方法一：bilibili-api-python

环境准备:
    pip install bilibili-api-python

Cookie 配置:
    自动从 ../config/cookies_bilibili.txt 读取
    或手动设置环境变量: BILI_SESSDATA
"""

import asyncio
import json
import aiohttp
import os
import sys
import re
from pathlib import Path
from bilibili_api import video, Credential

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============= 配置区 =============
# Cookie 文件路径 (相对于项目根目录)
# 专用文件，不会被 yt-dlp 覆盖
COOKIE_FILE = Path(__file__).parent.parent / "config" / "cookies_bilibili_api.txt"

# 测试视频 BV 号
TEST_BVID = "BV1oQZ7B9EB4"
# =================================


def load_cookies(cookie_file: Path) -> dict:
    """从 cookie 文件加载 cookies (支持 Netscape 格式和 key=value 格式)"""
    cookies = {}
    if not cookie_file.exists():
        print(f"警告: Cookie 文件不存在: {cookie_file}")
        return cookies

    with open(cookie_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Netscape 格式: domain \t flag \t path \t secure \t expiration \t name \t value
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 7:
                    name = parts[5].strip()
                    value = parts[6].strip()
                    cookies[name] = value
            # 简单格式: key=value
            elif "=" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key, value = parts
                    value = value.rstrip(";").strip()
                    cookies[key] = value

    return cookies


def get_credential() -> Credential:
    """获取认证凭据"""
    # 1. 先尝试从 cookie 文件读取
    cookies = load_cookies(COOKIE_FILE)

    sessdata = cookies.get("SESSDATA") or os.getenv("BILI_SESSDATA", "")
    bili_jct = cookies.get("bili_jct", "")
    buvid3 = cookies.get("buvid3", "")

    # 2. 检查是否完整
    if not sessdata:
        print("警告: 未找到 SESSDATA")
        print("请从浏览器 F12 → Application → Cookies → bilibili.com 获取 SESSDATA")
        print(f"并添加到 {COOKIE_FILE}")
        print("\n提示: 在 cookie 文件中添加一行: SESSDATA=你的值")
        return None

    return Credential(
        sessdata=sessdata,
        bili_jct=bili_jct,
        buvid3=buvid3
    )


# 全局 credential (在 main 中初始化)
credential = None


async def get_subtitle(bvid: str, output_dir: str = "."):
    """获取视频字幕并保存"""

    v = video.Video(bvid=bvid, credential=credential)
    output_path = Path(output_dir)

    # 第一步：获取视频信息（包含 cid）
    print("=" * 50)
    print(f"[1/3] 获取视频信息...")
    info = await v.get_info()
    cid = info["cid"]
    print(f"  视频标题: {info['title']}")
    print(f"  视频作者: {info['owner']['name']}")
    print(f"  cid: {cid}")

    # 第二步：获取播放器信息（含字幕列表）
    print("\n[2/3] 获取字幕列表...")
    player_info = await v.get_player_info(cid=cid)
    subtitles = player_info.get("subtitle", {}).get("subtitles", [])

    if not subtitles:
        print("  该视频无字幕")
        return None

    print(f"  找到 {len(subtitles)} 条字幕:")
    for i, sub in enumerate(subtitles, 1):
        print(f"    [{i}] 语言: {sub['lan_doc']} | 代码: {sub['lan']}")

    # 第三步：下载第一条字幕
    print("\n[3/3] 下载字幕内容...")
    url = "https:" + subtitles[0]["subtitle_url"]
    print(f"  下载 URL: {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)

    # 保存为不同格式
    base_name = f"{bvid}_{subtitles[0]['lan']}"

    # 1. 保存 JSON 原始格式
    json_path = output_path / f"{base_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  已保存 JSON: {json_path}")

    # 2. 保存纯文本格式
    txt_path = output_path / f"{base_name}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for item in data["body"]:
            f.write(f"[{item['from']:.1f}s -> {item['to']:.1f}s] {item['content']}\n")
    print(f"  已保存 TXT: {txt_path}")

    # 3. 保存 SRT 格式
    srt_path = output_path / f"{base_name}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, item in enumerate(data["body"], 1):
            # 时间码转换: 秒 -> SRT 格式 (00:00:00,000)
            start_time = format_srt_time(item['from'])
            end_time = format_srt_time(item['to'])
            f.write(f"{i}\n{start_time} --> {end_time}\n{item['content']}\n\n")
    print(f"  已保存 SRT: {srt_path}")

    return data


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间码格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def main():
    global credential
    credential = get_credential()

    if credential is None:
        return

    print(f"开始获取视频 {TEST_BVID} 的字幕...\n")

    try:
        await get_subtitle(TEST_BVID, output_dir="output")
        print("\n完成!")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
