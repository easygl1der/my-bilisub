#!/usr/bin/env python3
"""
B站视频自动化工作流程

一键完成：
1. 抓取用户视频列表 / 处理单个视频
2. 批量提取字幕 / 提取单个视频字幕
3. 生成AI摘要报告

使用示例:
    # 基本用法 - 获取最新10个视频并完成全部流程
    python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/492139282/?spm_id_from=333.788.upinfo.head.click" --count 10

    # 新增：直接分析单个视频链接
    python workflows/auto_bili_workflow.py --video-url "https://www.bilibili.com/video/BV1mWieBhEtL/?-Arouter=story&buvid=YA4FA8AEA282F4DF42C7B0BC2CF09F0E55E1&from_spmid=tm.recommend.0.0&is_story_h5=true&mid=2UYYhXDIEUl4rvxj5J2NjQ%3D%3D&plat_id=163&share_from=ugc&share_medium=iphone&share_plat=ios&share_session_id=453D5E23-4600-41B1-A416-DE1722D052DA&share_source=COPY&share_tag=s_i&spmid=main.ugc-video-detail-vertical.0.0&timestamp=1772040421&unique_k=u5PQcMC&up_id=492139282&vd_source=b55594d2ba73cdd7666e94ca2cf2fe93&spm_id_from=333.788.videopod.sections"

    # 新增：分析单个视频并指定模型
    python workflows/auto_bili_workflow.py --video-url "https://www.bilibili.com/video/BV1xxxx" --model flash

    # 增量模式 - 跳过已处理的视频
    python workflows/auto_bili_workflow.py --user "用户名" --incremental

    # 指定 Gemini 模型和并发数
    python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 20 --model flash -j 5

    # 从已有CSV开始，跳过视频抓取
    python workflows/auto_bili_workflow.py --csv "MediaCrawler/bilibili_videos_output/用户名.csv" --count 20

    # 仅抓取视频和提取字幕，不生成AI摘要
    python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 30 --no-summary

    # 仅生成AI摘要（已有字幕）
    python workflows/auto_bili_workflow.py --user "用户名" --summary-only
"""

import argparse
import asyncio
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 路径配置 ====================
# 脚本现在在 workflows/ 目录下，parent.parent 就是项目根目录
SCRIPT_DIR = Path(__file__).parent.parent  # 项目根目录
MEDIA_CRAWLER_DIR = SCRIPT_DIR / "archive" / "MediaCrawler"  # MediaCrawler 已移至 archive/
SUBTITLE_FETCH_SCRIPT = SCRIPT_DIR / "workflows" / "batch_subtitle_fetch.py"  # 已移至 workflows/
SUMMARY_SCRIPT = SCRIPT_DIR / "analysis" / "subtitle_analyzer.py"  # 已重命名
FALLBACK_PROCESSOR_SCRIPT = SCRIPT_DIR / "utils" / "video_fallback_processor.py"

# 输出路径 - 保存到输出目录
MEDIA_CRAWLER_OUTPUT = SCRIPT_DIR / "bilibili_videos_output"
SUBTITLE_OUTPUT = SCRIPT_DIR / "output" / "subtitles"


# ==================== 步骤1: 抓取视频列表 ====================

def fetch_video_list(url: str, count: int = None) -> tuple:
    """
    步骤1: 抓取用户视频列表（直接调用模块，避免subprocess）

    Returns:
        (success: bool, user_name: str, csv_path: Path)
    """
    print("\n" + "=" * 70)
    print("📋 步骤 1/3: 抓取用户视频列表")
    print("=" * 70)

    # 提取UID
    uid = extract_uid_from_url(url)
    if not uid:
        print(f"❌ 无法从URL提取UID: {url}")
        return False, None, None

    print(f"🔍 用户UID: {uid}")

    fetch_script = MEDIA_CRAWLER_DIR / "fetch_bilibili_videos.py"

    if not fetch_script.exists():
        print(f"❌ 找不到脚本: {fetch_script}")
        return False, None, None

    print(f"📡 正在抓取视频列表...")

    # 直接导入模块并调用函数（避免subprocess的开销）
    try:
        import importlib.util

        # 加载模块
        spec = importlib.util.spec_from_file_location(
            "fetch_bilibili_videos",
            fetch_script
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用底层函数，绕过交互式输入
        print("  → 获取用户信息...")
        user_info = module.get_user_info(uid)
        if not user_info:
            print("❌ 无法获取用户信息")
            return False, None, None

        user_name = user_info.get('name', f'用户{uid}')

        print(f"  → 获取视频列表...")
        videos = module.get_user_videos(uid)
        if not videos:
            print("❌ 未获取到视频")
            return False, None, None

        # 限制数量
        if count and count < len(videos):
            videos = videos[:count]
            print(f"  → 限制处理数量: {count}")

        # 处理视频数据
        print(f"  → 处理 {len(videos)} 个视频...")
        processed_videos, author_name = module.process_video_data(videos)

        # 优先使用UP主名
        if author_name:
            user_name = author_name

        # 清理用户名
        import re
        user_name = re.sub(r'[\/\\:*?"<>|]', '_', user_name)

        # 读取历史记录
        historical_links = module.load_historical_links(user_name)

        # 过滤新视频
        new_videos = module.filter_new_videos(processed_videos, historical_links)

        # 保存结果
        csv_out = module.save_results(new_videos, user_name, url)

        print(f"✅ 抓取完成！")
        print(f"   用户: {user_name}")
        print(f"   新视频: {len(new_videos)} 个")

        if csv_out:
            return True, user_name, Path(csv_out)
        else:
            # 没有新视频，但返回现有CSV路径
            existing_csv = MEDIA_CRAWLER_OUTPUT / f"{user_name}.csv"
            if existing_csv.exists():
                return True, user_name, existing_csv
            return False, None, None

    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None


# ==================== 步骤2: 批量提取字幕 ====================

async def fetch_subtitles(csv_path: Path, count: int = None) -> bool:
    """
    步骤2: 批量提取字幕 (调用 utils/batch_subtitle_fetch.py)
    """
    print("\n" + "=" * 70)
    print("📝 步骤 2/3: 批量提取字幕")
    print("=" * 70)

    if not csv_path or not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    if not SUBTITLE_FETCH_SCRIPT.exists():
        print(f"❌ 找不到脚本: {SUBTITLE_FETCH_SCRIPT}")
        return False

    print(f"📄 CSV文件: {csv_path}")
    if count:
        print(f"🔢 限制数量: {count}")

    # 动态导入并运行
    try:
        # 添加 utils 目录到路径
        sys.path.insert(0, str(SUBTITLE_FETCH_SCRIPT.parent))

        # 导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "batch_subtitle_fetch",
            SUBTITLE_FETCH_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用主函数
        await module.process_batch(str(csv_path), limit=count)

        print("\n✅ 字幕提取完成!")
        return True

    except Exception as e:
        print(f"❌ 字幕提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 步骤3: 生成AI摘要 ====================

def generate_summary(user_name: str, model: str = 'flash-lite', jobs: int = 3, incremental: bool = False, append: bool = False) -> bool:
    """
    步骤3: 生成AI摘要报告 (调用 analysis/gemini_subtitle_summary.py)
    """
    print("\n" + "=" * 70)
    print("🤖 步骤 3/3: 生成AI摘要报告")
    print("=" * 70)

    subtitle_dir = SUBTITLE_OUTPUT / user_name

    if not subtitle_dir.exists():
        print(f"❌ 字幕目录不存在: {subtitle_dir}")
        return False

    # 检查SRT文件
    srt_files = list(subtitle_dir.glob("*.srt"))
    if not srt_files:
        print(f"❌ 没有找到SRT文件: {subtitle_dir}")
        return False

    print(f"📁 字幕目录: {subtitle_dir}")
    print(f"📄 SRT文件数: {len(srt_files)}")
    print(f"🤖 模型: {model}")
    print(f"⚡ 并发数: {jobs}")
    if incremental:
        print(f"🔄 增量模式: 跳过已处理视频")

    if not SUMMARY_SCRIPT.exists():
        print(f"❌ 找不到脚本: {SUMMARY_SCRIPT}")
        return False

    # 调用摘要脚本
    try:
        # 导入模块
        sys.path.insert(0, str(SUMMARY_SCRIPT.parent))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gemini_subtitle_summary",
            SUMMARY_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用处理函数
        module.process_subtitles(str(subtitle_dir), model=model, max_workers=jobs,
                                 incremental=incremental, append=append)

        print("\n✅ AI摘要生成完成!")
        return True

    except Exception as e:
        print(f"❌ AI摘要生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 步骤4: 处理无字幕视频（备选方案） ====================

def process_fallback_videos(csv_path: Path, model: str = 'flash-lite', limit: int = None,
                           quality: str = 'best') -> bool:
    """
    步骤4: 处理无字幕视频（使用视频下载+Gemini分析作为备选方案）

    Args:
        csv_path: CSV文件路径
        model: Gemini模型
        limit: 限制处理数量
        quality: 视频质量选项
    """
    print("\n" + "=" * 70)
    print("🎬 步骤 4/4: 处理无字幕视频 (Gemini视频分析)")
    print("=" * 70)

    if not csv_path or not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return False

    if not FALLBACK_PROCESSOR_SCRIPT.exists():
        print(f"❌ 找不到脚本: {FALLBACK_PROCESSOR_SCRIPT}")
        return False

    print(f"📄 CSV文件: {csv_path}")
    if limit:
        print(f"🔢 限制数量: {limit}")
    print(f"🤖 模型: {model}")
    print(f"📺 视频质量: {quality}")

    # 动态导入并运行
    try:
        # 添加 utils 目录到路径
        sys.path.insert(0, str(FALLBACK_PROCESSOR_SCRIPT.parent))

        # 导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "video_fallback_processor",
            FALLBACK_PROCESSOR_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用处理函数
        result = module.process_fallback_videos(str(csv_path), model=model, limit=limit, quality=quality)

        if result.get('total', 0) > 0:
            success_rate = result.get('success', 0) / result.get('total', 1) * 100
            print(f"\n✅ 备选方案处理完成! 成功率: {success_rate:.1f}%")
            return True
        else:
            print(f"\n✅ 没有需要处理的视频")
            return True

    except Exception as e:
        print(f"❌ 备选方案处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 处理单个视频 ====================

async def fetch_single_subtitle(bvid: str, title: str, author_name: str) -> Path:
    """
    直接提取单个视频的字幕（不创建临时CSV）

    Args:
        bvid: BV号
        title: 视频标题
        author_name: 作者名

    Returns:
        字幕文件路径，失败返回 None
    """
    try:
        # 动态导入 batch_subtitle_fetch 模块
        sys.path.insert(0, str(SUBTITLE_FETCH_SCRIPT.parent))
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "batch_subtitle_fetch",
            SUBTITLE_FETCH_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用 fetch_subtitle_srt 函数
        author_dir = SUBTITLE_OUTPUT / author_name
        author_dir.mkdir(parents=True, exist_ok=True)

        print(f"📁 字幕保存目录: {author_dir}")

        result = await module.fetch_subtitle_srt(bvid, title, author_dir)

        if result['success']:
            print(f"✅ 字幕提取成功")
            print(f"   路径: {result['srt_path']}")
            return Path(result['srt_path'])
        else:
            print(f"❌ 字幕提取失败: {result.get('error', '未知错误')}")
            return None

    except Exception as e:
        print(f"❌ 字幕提取异常: {e}")
        import traceback
        traceback.print_exc()
        return None

async def process_single_video(video_url: str, model: str = 'flash-lite') -> bool:
    """
    处理单个视频：提取字幕 + 生成AI摘要

    Args:
        video_url: B站视频链接
        model: Gemini模型

    Returns:
        是否成功
    """
    # 提取BV号
    bvid = extract_bvid_from_url(video_url)
    if not bvid:
        print(f"❌ 无法从URL提取BV号: {video_url}")
        return False

    print(f"\n" + "=" * 70)
    print("🎬 单个视频处理模式")
    print("=" * 70)
    print(f"🔗 视频链接: {video_url}")
    print(f"🆔 BV号: {bvid}")
    print(f"🤖 模型: {model}")

    # 获取视频信息（标题、作者）
    print(f"\n📋 获取视频信息...")
    try:
        import requests

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com'
        }
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        response = requests.get(api_url, headers=headers, timeout=10)
        data = response.json()

        if data.get('code') != 0:
            print(f"❌ API请求失败: {data.get('message', '未知错误')}")
            return False

        video_info = data.get('data', {})
        title = video_info.get('title', '未知标题')
        author = video_info.get('owner', {}).get('name', '未知作者')

        # 清理文件名
        safe_author = re.sub(r'[\/\\:*?"<>|]', '_', author)

        print(f"  📝 标题: {title}")
        print(f"  👤 作者: {author}")

        # 步骤1: 直接提取字幕（不创建临时CSV）
        print(f"\n📝 提取字幕...")
        subtitle_file = await fetch_single_subtitle(bvid, title, safe_author)

        if not subtitle_file:
            print(f"\n⚠️ 字幕提取失败")
            return False

        # 步骤2: 生成AI摘要
        print(f"\n🤖 生成AI摘要...")
        summary_success = generate_single_video_summary(safe_author, subtitle_file, title, bvid, model=model)

        if summary_success:
            print(f"\n" + "=" * 70)
            print(f"🎉 单个视频处理完成!")
            print(f"=" * 70)
            print(f"\n📁 输出文件:")
            print(f"  - 字幕: {subtitle_file}")
            print(f"  - AI摘要: {SUBTITLE_OUTPUT / safe_author / f'{title}_AI总结.md'}")
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 生成单个视频AI摘要 ====================

def generate_single_video_summary(author_name: str, srt_file: Path = None, title: str = "", bvid: str = "",
                                    model: str = 'flash-lite') -> bool:
    """
    为单个视频生成AI摘要（简化版）

    Args:
        author_name: 作者名
        srt_file: 字幕文件路径
        title: 视频标题
        bvid: BV号
        model: Gemini模型

    Returns:
        是否成功
    """
    if not srt_file or not srt_file.exists():
        print(f"❌ 字幕文件不存在: {srt_file}")
        return False

    print(f"📄 字幕文件: {srt_file}")
    print(f"📝 视频标题: {title}")
    print(f"🆔 BV号: {bvid}")

    # 读取字幕内容
    try:
        with open(srt_file, 'r', encoding='utf-8') as f:
            subtitle_text = f.read()
    except Exception as e:
        print(f"❌ 读取字幕失败: {e}")
        return False

    # 简化：调用 Gemini 生成摘要
    try:
        import sys
        sys.path.insert(0, str(SUMMARY_SCRIPT.parent))
        import importlib.util

        # 导入 subtitle_analyzer 模块
        spec = importlib.util.spec_from_file_location(
            "subtitle_analyzer",
            SUMMARY_SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 创建摘要生成器
        analyzer = module.GeminiSummarizer(model=model)

        # 生成摘要
        print(f"\n🤖 正在生成摘要...")
        result = analyzer.generate_summary(subtitle_text, title)

        # 保存摘要到 MD 文件
        output_dir = SUBTITLE_OUTPUT / author_name
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_md = output_dir / f"{title}_AI总结.md"

        md_content = f"""# {title}

## 📋 视频信息
- **BV号**: {bvid}
- **作者**: {author_name}
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{result.get('summary', '')}

---

*本报告由 AI 自动生成，基于视频字幕内容进行分析。*
"""

        with open(summary_md, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"✅ 摘要已保存: {summary_md}")
        print(f"   Token数: {result.get('tokens', 'N/A')}")
        return True

    except Exception as e:
        print(f"❌ AI摘要生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== 工具函数 ====================

def extract_uid_from_url(url: str) -> str:
    """从B站用户链接中提取UID"""
    try:
        if '?' in url:
            url = url.split('?')[0]
        if 'space.bilibili.com/' in url:
            uid = url.split('space.bilibili.com/')[-1].strip('/')
            return uid
    except Exception:
        pass
    return None


def extract_bvid_from_url(url: str) -> str:
    """从B站视频链接中提取BV号"""
    import requests

    try:
        # 移除查询参数
        if '?' in url:
            url = url.split('?')[0]

        # 匹配 BV 号（支持 b23.tv 和 bilibili.com）
        patterns = [
            r'/BV([a-zA-Z0-9]+)',  # /BV1234567890
            r'BV([a-zA-Z0-9]+)',   # BV1234567890
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return 'BV' + match.group(1)

        # 如果没有匹配，尝试通过 HTTP 请求获取重定向后的 URL（针对短链接如 b23.tv/xxxx）
        # b23.tv 短链接会重定向到真实 URL
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.bilibili.com/',
            }
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            final_url = response.url  # 获取重定向后的最终 URL

            # 从重定向后的 URL 中提取 BV 号
            for pattern in patterns:
                match = re.search(pattern, final_url)
                if match:
                    print(f"🔗 短链接重定向: {url} -> {final_url}")
                    return 'BV' + match.group(1)
        except Exception as e:
            print(f"⚠️ HTTP 请求失败: {e}")
    except Exception as e:
        print(f"⚠️ 提取 BV 号时出错: {e}")
    return None


def is_video_url(url: str) -> bool:
    """判断是否为视频链接"""
    return 'bilibili.com/video/' in url or 'b23.tv' in url or extract_bvid_from_url(url) is not None


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="B站用户视频自动化工作流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法 - 获取最新10个视频
  python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 10

  # 【新增】直接分析单个视频链接
  python workflows/auto_bili_workflow.py --video-url "https://www.bilibili.com/video/BV1xxxx"

  # 【新增】分析单个视频并指定模型
  python workflows/auto_bili_workflow.py --video-url "https://www.bilibili.com/video/BV1xxxx" --model flash

  # 增量模式 - 跳过已处理的视频
  python workflows/auto_bili_workflow.py --user "用户名" --incremental

  # 指定 Gemini 模型和并发数
  python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 20 --model flash -j 5

  # 从已有CSV开始，跳过视频抓取
  python workflows/auto_bili_workflow.py --csv "bilibili_videos_output/用户名.csv" --count 20

  # 仅抓取视频和提取字幕，不生成AI摘要
  python workflows/auto_bili_workflow.py --url "https://space.bilibili.com/3546607314274766" --count 30 --no-summary

  # 仅生成AI摘要（已有字幕）
  python workflows/auto_bili_workflow.py --user "用户名" --summary-only

  # 追加模式 - 将新结果追加到现有摘要
  python workflows/auto_bili_workflow.py --user "用户名" --append --incremental

  # 启用无字幕视频备选方案（视频下载+Gemini分析）
  python workflows/auto_bili_workflow.py --csv "bilibili_videos_output/用户名.csv" --enable-fallback
        """
    )

    parser.add_argument("--url", "-u", help="B站用户主页链接")
    parser.add_argument("--video-url", "-v", help="B站视频链接（直接分析单个视频）")
    parser.add_argument("--csv", "-c", help="直接使用已有的CSV文件（跳过步骤1）")
    parser.add_argument("--user", help="指定用户名（用于步骤2和3）")
    parser.add_argument("--count", "-n", type=int, default=None,
                        help="处理的视频数量（默认：全部）")
    parser.add_argument("--model", "-m", choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help="Gemini模型（默认: flash-lite）")
    parser.add_argument("--jobs", "-j", type=int, default=3,
                        help="并发处理数（默认: 3）")
    parser.add_argument("--no-summary", action="store_true",
                        help="跳过AI摘要生成步骤")
    parser.add_argument("--summary-only", action="store_true",
                        help="仅生成AI摘要（跳过步骤1和2）")
    parser.add_argument("--incremental", "-i", action="store_true",
                        help="增量模式：跳过已处理的视频")
    parser.add_argument("--append", "-a", action="store_true",
                        help="追加模式：将新结果追加到现有摘要文件")
    parser.add_argument("--enable-fallback", action="store_true",
                        help="启用无字幕视频备选方案：下载视频并使用Gemini分析")
    parser.add_argument("--fallback-limit", type=int, default=None,
                        help="备选方案处理数量限制（测试用）")
    parser.add_argument("--fallback-quality", type=str, default='best',
                        choices=['best', '1080p', '720p', '480p', '360p', 'audio_only'],
                        help="备选方案视频质量（默认: best）")

    args = parser.parse_args()

    # 验证参数
    if not args.summary_only and not args.csv and not args.url and not args.video_url:
        print("❌ 错误: 必须提供 --url, --video-url, --csv 或使用 --summary-only")
        parser.print_help()
        return 1

    # 处理单个视频链接
    if args.video_url:
        print("\n" + "=" * 70)
        print("🚀 B站单个视频分析")
        print("=" * 70)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        success = asyncio.run(process_single_video(args.video_url, args.model))

        if success:
            print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return 0
        else:
            return 1

    print("\n" + "=" * 70)
    print("🚀 B站用户视频自动化工作流程")
    print("=" * 70)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化变量
    user_name = args.user
    csv_path = None

    # ==================== 步骤1: 抓取视频 ====================
    if not args.summary_only and not args.csv:
        success, name, path = fetch_video_list(args.url, args.count)
        if not success and not path:
            print("\n❌ 视频抓取失败，工作流程终止")
            return 1

        if not user_name:
            user_name = name
        csv_path = path

    # ==================== 使用已有CSV ====================
    elif args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"❌ CSV文件不存在: {csv_path}")
            return 1
        if not user_name:
            user_name = csv_path.stem
        print(f"\n📁 使用指定CSV: {csv_path}")
        print(f"👤 用户名: {user_name}")

    # ==================== 步骤2: 提取字幕 ====================
    if not args.summary_only:
        if csv_path:
            # 步骤2是异步的
            success = asyncio.run(fetch_subtitles(csv_path, args.count))
            if not success:
                print("\n⚠️ 字幕提取失败，但继续尝试生成摘要...")
        else:
            print("\n⚠️ 没有CSV文件，跳过字幕提取")

    # ==================== 步骤3: 生成AI摘要 ====================
    if not args.no_summary or args.summary_only:
        if user_name:
            success = generate_summary(user_name, args.model, args.jobs,
                                       incremental=args.incremental, append=args.append)

            if success:
                # ==================== 步骤4: 处理无字幕视频（备选方案） ====================
                if args.enable_fallback and csv_path:
                    fallback_success = process_fallback_videos(
                        csv_path, args.model, args.fallback_limit, args.fallback_quality
                    )

                print("\n" + "=" * 70)
                print("🎉 工作流程完成!")
                print("=" * 70)
                print(f"\n📁 输出文件:")
                if csv_path:
                    print(f"  - CSV: {csv_path}")
                print(f"  - 字幕: {SUBTITLE_OUTPUT / user_name}")
                print(f"  - AI摘要: {SUBTITLE_OUTPUT / f'{user_name}_AI总结.md'}")

                if args.enable_fallback:
                    print(f"\n💡 无字幕视频已通过备选方案处理:")
                    print(f"  - 视频下载目录: downloaded_videos/{user_name}/")
                    print(f"  - 视频分析: {SUBTITLE_OUTPUT / user_name}/")
            else:
                print("\n⚠️ AI摘要生成失败")
                return 1
        else:
            print("\n❌ 无法确定用户名，无法生成摘要")
            return 1
    else:
        print("\n" + "=" * 70)
        print("✅ 工作流程完成 (跳过AI摘要)")
        print("=" * 70)

    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
