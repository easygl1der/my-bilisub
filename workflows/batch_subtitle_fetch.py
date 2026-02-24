"""
批量提取B站字幕并更新CSV状态
基于 test_bilibili_api.py 的字幕获取功能

使用示例:
    python batch_subtitle_fetch.py "MediaCrawler/bilibili_videos_output/小天fotos.csv"
"""

import asyncio
import json
import aiohttp
import csv
import sys
import re
import time
from pathlib import Path
from bilibili_api import video, Credential
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============= 配置区 =============
# Cookie 文件路径（从 utils/ 回到父目录的 config/）
COOKIE_FILE = Path(__file__).parent.parent / "config" / "cookies_bilibili_api.txt"
# 字幕输出目录（从 utils/ 回到父目录的 output/）
SUBTITLE_OUTPUT_DIR = Path(__file__).parent.parent / "output" / "subtitles"
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


async def fetch_subtitle_srt(bvid: str, title: str, author_dir: Path) -> dict:
    """
    获取单个视频的 SRT 字幕

    返回:
        {
            'success': bool,
            'srt_path': str or None,
            'error': str or None,
            'fallback_needed': bool  # 是否需要使用视频下载+Gemini分析作为备选方案
        }
    """
    result = {'success': False, 'srt_path': None, 'error': None, 'fallback_needed': False}

    try:
        v = video.Video(bvid=bvid, credential=get_credential())
        author_dir.mkdir(parents=True, exist_ok=True)

        # 获取视频信息
        info = await v.get_info()
        cid = info["cid"]

        # 获取字幕列表
        player_info = await v.get_player_info(cid=cid)
        subtitles = player_info.get("subtitle", {}).get("subtitles", [])

        if not subtitles:
            result['error'] = '该视频无字幕'
            result['fallback_needed'] = True  # 标记需要使用视频下载+Gemini分析备选方案
            return result

        # 下载第一条字幕（通常是中文）
        sub = subtitles[0]
        url = "https:" + sub["subtitle_url"]
        lan = sub['lan']

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)

        # 清理文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
        base_name = f"{safe_title}_{lan}"
        srt_path = author_dir / f"{base_name}.srt"

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


def read_csv_videos(csv_path: Path) -> list:
    """读取 CSV 文件，返回视频列表"""
    videos = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            videos.append(row)

    return videos


def write_csv_status(csv_path: Path, videos: list):
    """写回 CSV 文件，更新 subtitle_status 和 subtitle_error"""
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = list(videos[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(videos)


def generate_summary_md(videos: list, author_name: str, output_dir: Path, total_elapsed: float, csv_path: Path = None) -> Path:
    """生成汇总 MD 文件"""
    md_path = output_dir / f"{author_name}_汇总.md"

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# {author_name} 视频字幕汇总\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**总视频数**: {len(videos)}\n\n")
        f.write(f"**处理耗时**: {total_elapsed:.2f}秒\n\n")
        f.write("---\n\n")

        # 表格标题
        f.write("## 视频列表\n\n")
        f.write("| 序号 | 标题 | 链接 | BV号 | 时长 | 播放量 | 评论数 | 发布时间 | 字幕状态 |\n")
        f.write("|:----:|------|------|:----:|:----:|:------:|:------:|:--------:|:--------:|\n")

        for video_data in videos:
            seq = video_data.get('序号', '')
            title = video_data.get('标题', '').replace('|', '\\|')
            link = video_data.get('链接', '')
            bvid = video_data.get('BV号', '')
            duration = video_data.get('时长', '')
            views = video_data.get('播放量', '')
            comments = video_data.get('评论数', '')
            pub_time = video_data.get('发布时间', '')
            status = video_data.get('subtitle_status', '')

            # 状态图标
            status_icon = '✅' if status == 'success' else ('❌' if status == 'failed' else '⏳')

            f.write(f"| {seq} | {title} | [链接]({link}) | {bvid} | {duration} | {views} | {comments} | {pub_time} | {status_icon} |\n")

        f.write("\n---\n\n")

        # 统计信息
        success_count = sum(1 for v in videos if v.get('subtitle_status') == 'success')
        fail_count = sum(1 for v in videos if v.get('subtitle_status') == 'failed')
        pending_count = len(videos) - success_count - fail_count
        fallback_needed_count = sum(1 for v in videos if v.get('fallback_needed', False))

        f.write("## 统计\n\n")
        f.write(f"- ✅ 成功提取: {success_count}\n")
        f.write(f"- ❌ 提取失败: {fail_count}\n")
        f.write(f"- ⏳ 未处理/跳过: {pending_count}\n")

        if fallback_needed_count > 0:
            f.write(f"- 🎬 需要视频分析备选方案: {fallback_needed_count}\n")
            if csv_path:
                # 支持 Path 和 string 两种类型
                csv_name = csv_path.name if hasattr(csv_path, 'name') else Path(csv_path).name
                f.write(f"\n💡 提示: 可以运行 `python workflows/auto_bili_workflow.py --csv \"{csv_name}\" --enable-fallback` 来处理无字幕视频\n")
            else:
                f.write(f"\n💡 提示: 可以运行 `python workflows/auto_bili_workflow.py --csv \"your_csv_file.csv\" --enable-fallback` 来处理无字幕视频\n")

        # 失败列表
        failed_videos = [v for v in videos if v.get('subtitle_status') == 'failed']
        if failed_videos:
            f.write("\n## 失败视频列表\n\n")
            for v in failed_videos:
                f.write(f"- **{v.get('标题', '')}**: {v.get('subtitle_error', '未知错误')}\n")

    return md_path


async def process_batch(csv_path: str, limit: int = None, force: bool = False):
    """批量处理视频字幕提取

    Args:
        csv_path: CSV 文件路径
        limit: 限制处理视频数量（默认：处理全部）
        force: 强制重新获取，不跳过已成功的视频
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        print(f"错误: CSV 文件不存在: {csv_path}")
        return

    # 从 CSV 文件名提取作者名
    author_name = csv_file.stem  # 去掉路径和后缀，如 "小天fotos.csv" -> "小天fotos"
    print(f"作者: {author_name}")

    print(f"读取 CSV 文件: {csv_path}")
    videos = read_csv_videos(csv_file)

    if not videos:
        print("错误: CSV 文件为空或格式不正确")
        return

    # 应用限制
    if limit and limit < len(videos):
        videos = videos[:limit]
        print(f"限制处理数量: {limit}")

    print(f"找到 {len(videos)} 个视频")
    print("=" * 60)

    # 统计
    success_count = 0
    fail_count = 0
    skip_count = 0

    # 总计时
    total_start_time = time.time()

    # 创建作者专属目录
    author_dir = SUBTITLE_OUTPUT_DIR / author_name
    author_dir.mkdir(parents=True, exist_ok=True)
    print(f"字幕保存目录: {author_dir}")

    for i, video_data in enumerate(videos, 1):
        bvid = video_data.get('BV号', '')
        title = video_data.get('标题', '')
        link = video_data.get('链接', '')

        if not bvid:
            print(f"\n[{i}/{len(videos)}] 跳过: BV号为空")
            skip_count += 1
            continue

        # 如果已经有成功状态，可以选择跳过（除非 force=True）
        current_status = video_data.get('subtitle_status', '').strip()
        if current_status == 'success' and not force:
            print(f"\n[{i}/{len(videos)}] 跳过: {title[:30]}... (已成功)")
            skip_count += 1
            continue

        # 单个视频计时
        video_start_time = time.time()

        print(f"\n[{i}/{len(videos)}] 正在处理: {title}")
        print(f"  BV: {bvid}")

        # 获取字幕
        result = await fetch_subtitle_srt(bvid, title, author_dir)

        # 计算耗时
        elapsed = time.time() - video_start_time

        if result['success']:
            print(f"  ✅ 成功 | 耗时: {elapsed:.2f}秒")
            print(f"  保存路径: {result['srt_path']}")
            video_data['subtitle_status'] = 'success'
            video_data['subtitle_error'] = ''
            success_count += 1
        else:
            print(f"  ❌ 失败 | 耗时: {elapsed:.2f}秒")
            print(f"  错误原因: {result['error']}")
            video_data['subtitle_status'] = 'failed'
            video_data['subtitle_error'] = result['error']

            # 添加fallback跟踪字段
            if result.get('fallback_needed', False):
                video_data['fallback_needed'] = True
                video_data['fallback_status'] = 'pending'
                print(f"  💡 将使用视频下载+Gemini分析作为备选方案")

            fail_count += 1

        # 总进度
        total_elapsed = time.time() - total_start_time
        print(f"  总进度耗时: {total_elapsed:.2f}秒")

        # 每处理 5 个视频保存一次进度
        if i % 5 == 0:
            write_csv_status(csv_file, videos)
            print(f"  [进度已保存]")

    # 最终保存
    write_csv_status(csv_file, videos)

    # 总耗时
    total_elapsed = time.time() - total_start_time

    # 生成 MD 汇总文件
    md_path = generate_summary_md(videos, author_name, SUBTITLE_OUTPUT_DIR, total_elapsed, csv_file)

    print("\n" + "=" * 60)
    print(f"批量处理完成!")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  跳过: {skip_count}")
    print(f"  总耗时: {total_elapsed:.2f}秒")
    print(f"  字幕保存目录: {author_dir}")
    print(f"  汇总文件: {md_path}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="批量提取B站字幕并更新CSV状态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_subtitle_fetch.py "data/videos.csv"
  python batch_subtitle_fetch.py "data/videos.csv" --limit 100
  python batch_subtitle_fetch.py "data/videos.csv" --limit 50 --force
        """
    )
    parser.add_argument("csv_file", help="CSV 文件路径")
    parser.add_argument("--limit", "-l", type=int, default=None,
                        help="限制处理视频数量（默认：处理全部）")
    parser.add_argument("--force", "-f", action="store_true",
                        help="强制重新获取，跳过已成功的视频")

    args = parser.parse_args()

    try:
        await process_batch(args.csv_file, limit=args.limit, force=args.force)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
