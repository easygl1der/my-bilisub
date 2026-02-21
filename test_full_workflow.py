#!/usr/bin/env python3
"""
完整工作流测试 - 一键搞定
1. 抓取视频列表
2. 下载视频
3. 提取字幕
4. AI分析

轻量测试: 只处理2个视频
"""

import sys
import asyncio
from pathlib import Path

# 修复 Windows 编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 路径配置
SCRIPT_DIR = Path(__file__).parent
MEDIA_CRAWLER_DIR = SCRIPT_DIR / "MediaCrawler"

# 测试参数
TEST_URL = "https://space.bilibili.com/2475977"
TEST_COUNT = 2  # 只测试2个视频


async def main():
    print("=" * 70)
    print("完整工作流测试")
    print("=" * 70)

    # ============ 步骤1: 抓取视频列表 ============
    print("\n📋 步骤 1/4: 抓取视频列表")

    import importlib.util
    import re

    fetch_script = MEDIA_CRAWLER_DIR / "fetch_bilibili_videos.py"
    spec = importlib.util.spec_from_file_location("fetch", fetch_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    uid = TEST_URL.split('/')[-1].split('?')[0]
    print(f"   UID: {uid}")

    videos = module.get_user_videos(uid)[:TEST_COUNT]
    print(f"   获取 {len(videos)} 个视频")

    processed, author = module.process_video_data(videos)
    user_name = re.sub(r'[\/\\:*?"<>|]', '_', author or f'用户{uid}')
    print(f"   用户: {user_name}")

    # 保存CSV
    csv_path = MEDIA_CRAWLER_DIR / "bilibili_videos_output" / f"{user_name}.csv"
    module.save_results(processed, user_name, TEST_URL)

    # ============ 步骤2: 下载视频 ============
    print("\n⬇️  步骤 2/4: 下载视频")
    print("   (注意: 这会很慢且占用空间)")

    # 检查是否安装 yt-dlp
    try:
        import yt_dlp
    except ImportError:
        print("   ⚠️  需要先安装 yt-dlp: pip install yt-dlp")
        print("   跳过视频下载，直接提取字幕...")
        video_dir = None
    else:
        video_dir = MEDIA_CRAWLER_DIR / "videos" / user_name
        video_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts = {
            'format': 'worse',  # 最低画质，节省空间
            'outtmpl': str(video_dir / '%(title)s.%(ext)s'),
            'cookiefile': None,
            'quiet': True,
            'no_warnings': True,
        }

        downloaded = 0
        for v in processed:
            print(f"   下载: {v['title'][:30]}...")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([v['video_url']])
                downloaded += 1
            except Exception as e:
                print(f"      失败: {e}")

        print(f"   下载完成: {downloaded}/{len(processed)} 个视频")

    # ============ 步骤3: 提取字幕 ============
    print("\n📝 步骤 3/4: 提取字幕")

    fetch_script = SCRIPT_DIR / "utils" / "batch_subtitle_fetch.py"
    spec = importlib.util.spec_from_file_location("fetch_sub", fetch_script)
    module_sub = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_DIR / "utils"))
    spec.loader.exec_module(module_sub)

    await module_sub.process_batch(str(csv_path), limit=TEST_COUNT)
    print("   字幕提取完成")

    # ============ 步骤4: AI分析 ============
    print("\n🤖 步骤 4/4: AI分析")

    summary_script = SCRIPT_DIR / "analysis" / "gemini_subtitle_summary.py"
    spec = importlib.util.spec_from_file_location("summary", summary_script)
    module_sum = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_sum)

    subtitle_dir = MEDIA_CRAWLER_DIR / "bilibili_subtitles" / user_name
    module_sum.process_subtitles(str(subtitle_dir), model='flash-lite', max_workers=1)

    print("\n" + "=" * 70)
    print("✅ 全部完成！")
    print("=" * 70)
    print(f"\n📁 输出文件:")
    print(f"  - CSV: {csv_path}")
    if video_dir:
        print(f"  - 视频: {video_dir}")
    print(f"  - 字幕: {subtitle_dir}")
    print(f"  - 摘要: {subtitle_dir.parent / f'{user_name}_AI总结.md'}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
