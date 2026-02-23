#!/usr/bin/env python3
"""
终极视频转录工具 - 集成所有方案

功能:
1. 流式下载视频/音频
2. 内置字幕检查
3. 视频OCR识别（使用VideOCR的PaddleOCR）
4. Whisper语音转录
5. 详细的时间统计对比

优先级:
1. 内置字幕 (最快)
2. 视频OCR (中等，识别画面文字)
3. Whisper语音 (最慢，但识别语音)
"""

import os
import sys
import json
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Optional, List

import yt_dlp

# ==================== 配置 ====================
WHISPER_MODEL = "medium"  # tiny/base/small/medium/large
OUTPUT_DIR = Path("output/ultimate")
USE_OCR = True  # 是否使用OCR
# ==============================================

# VideOCR路径
VIDEOCR_PATH = Path("D:/桌面/biliSub/VideOCR/CLI")


def detect_platform(url: str) -> str:
    """识别平台"""
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    else:
        return 'unknown'


def check_builtin_subtitles(url: str) -> Optional[Dict]:
    """方案1: 检查并提取内置字幕"""
    print("\n" + "=" * 70)
    print("🔍 方案 1/3: 检查内置字幕")
    print("=" * 70)

    start_time = time.time()

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitlesformat': 'srt',
            'subtitleslangs': ['zh-Hans', 'zh-Hant', 'zh', 'zh-CN'],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            has_subs = bool(info.get('subtitles') or info.get('automatic_captions'))
            elapsed = time.time() - start_time

            print(f"⏱️  检查耗时: {elapsed:.2f}秒")

            if has_subs:
                print("✅ 发现字幕!")
                # B站字幕需要特殊API，这里简化处理
                # 实际应用中需要使用bilibili_api
                print("⚠️  需要使用API下载字幕，跳过")
                return None

            print("❌ 无可用字幕")
            return None

    except Exception as e:
        print(f"⚠️  检查失败: {e}")
        return None


def ocr_video_subtitles(url: str, video_file: Optional[str] = None) -> Optional[Dict]:
    """
    方案2: 视频OCR识别

    使用VideOCR的PaddleOCR引擎识别视频中的文字
    """
    if not USE_OCR:
        return None

    print("\n" + "=" * 70)
    print("🔍 方案 2/3: 视频OCR识别")
    print("=" * 70)

    total_start = time.time()

    try:
        # 检查VideOCR是否可用
        videocr_module = VIDEOCR_PATH / "videocr"
        if not videocr_module.exists():
            print(f"⚠️  VideOCR模块未找到: {videocr_module}")
            print("   跳过OCR")
            return None

        # 添加到Python路径
        sys.path.insert(0, str(VIDEOCR_PATH))

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 下载视频（如果未提供）
            if not video_file:
                print("⬇️  下载视频...")
                download_start = time.time()

                ydl_opts = {
                    'format': 'worst[ext=mp4]/worst',
                    'outtmpl': str(temp_path / 'video.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'concurrentfragments': 4,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_file = list(temp_path.glob('video.*'))[0]
                    title = info.get('title', 'unknown')
                    duration = info.get('duration', 0)

                download_time = time.time() - download_start
                print(f"✅ 下载完成: {download_time:.2f}秒")
            else:
                title = Path(video_file).stem
                duration = 0
                download_time = 0

            # 使用VideOCR进行OCR
            print("🔎 开始OCR识别...")
            ocr_start = time.time()

            try:
                from videocr import save_subtitles_to_file

                output_srt = temp_path / 'output.srt'

                # 调用VideOCR
                save_subtitles_to_file(
                    video_path=str(video_file),
                    output_path=str(output_srt),
                    lang='ch',  # 中文
                    time_start='0:00',
                    time_end='',
                    conf_threshold=75,
                    sim_threshold=80,
                    use_gpu=False,
                    use_angle_cls=True,
                    show_progress=False,
                )

                ocr_time = time.time() - ocr_start

                # 读取结果
                with open(output_srt, 'r', encoding='utf-8') as f:
                    srt_content = f.read()

                total_time = time.time() - total_start

                # 提取纯文本
                text_lines = []
                for line in srt_content.split('\n'):
                    if line.strip() and '-->' not in line and not line.strip().isdigit():
                        text_lines.append(line.strip())

                ocr_text = '\n'.join(text_lines)

                print(f"✅ OCR完成!")
                print(f"⏱️  OCR耗时: {ocr_time:.2f}秒")
                print(f"⏱️  总耗时: {total_time:.2f}秒")
                print(f"📊 识别到 {len(text_lines)} 行文字")

                if ocr_text.strip():
                    return {
                        'method': 'ocr',
                        'content': ocr_text,
                        'srt': srt_content,
                        'title': title,
                        'duration': duration,
                        'timing': {
                            'download': download_time,
                            'ocr': ocr_time,
                            'total': total_time
                        }
                    }
                else:
                    print("⚠️  未识别到文字")
                    return None

            except ImportError as e:
                print(f"⚠️  导入VideOCR失败: {e}")
                return None

    except Exception as e:
        print(f"❌ OCR失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def whisper_transcribe(url: str) -> Optional[Dict]:
    """方案3: Whisper语音转录"""
    print("\n" + "=" * 70)
    print("🔍 方案 3/3: Whisper语音转录")
    print("=" * 70)

    total_start = time.time()

    try:
        import gc
        import whisper

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 下载音频
            print("⬇️  下载音频...")
            download_start = time.time()

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(temp_path / 'audio.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'concurrentfragments': 4,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_file = list(temp_path.glob('audio.*'))[0]
                title = info.get('title', 'unknown')
                duration = info.get('duration', 0)

            download_time = time.time() - download_start
            print(f"✅ 下载完成: {download_time:.2f}秒")

            # Whisper转录
            print(f"🎙️  Whisper识别中（模型: {WHISPER_MODEL}）...")
            transcribe_start = time.time()

            gc.collect()
            model = whisper.load_model(WHISPER_MODEL)

            result = model.transcribe(
                str(audio_file),
                language="zh",
                task="transcribe",
                verbose=False,
                fp16=False
            )

            transcribe_time = time.time() - transcribe_start

            del model
            gc.collect()

            total_time = time.time() - total_start

            print(f"✅ 识别完成!")
            print(f"⏱️  识别耗时: {transcribe_time:.2f}秒")
            print(f"⏱️  总耗时: {total_time:.2f}秒")
            print(f"📊 速度比: {duration/total_time:.2f}x 实时")

            return {
                'method': 'whisper',
                'content': result['text'],
                'segments': result['segments'],
                'title': title,
                'duration': duration,
                'language': result['language'],
                'timing': {
                    'download': download_time,
                    'transcribe': transcribe_time,
                    'total': total_time,
                    'speed_ratio': duration / total_time
                }
            }

    except Exception as e:
        print(f"❌ Whisper失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_result(result: Dict, output_dir: Path):
    """保存结果"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    title = result.get('title', 'unknown')
    method = result['method'].upper()
    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)[:50]

    # TXT
    txt_path = output_dir / f"[{method}]_{safe_title}.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(result['content'])

    # JSON
    json_path = output_dir / f"[{method}]_{safe_title}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # SRT (如果有)
    if 'srt' in result:
        srt_path = output_dir / f"[{method}]_{safe_title}.srt"
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(result['srt'])

    print(f"\n📁 输出文件:")
    print(f"   📄 {txt_path.name}")
    print(f"   📊 {json_path.name}")
    if 'srt' in result:
        print(f"   🎥 {srt_path.name}")


def compare_all_methods(url: str):
    """对比所有方案"""
    print("=" * 70)
    print("🔬 完整对比测试: 内置字幕 vs OCR vs Whisper")
    print("=" * 70)

    results = {}

    # 方案1: 内置字幕
    result = check_builtin_subtitles(url)
    if result:
        results['builtin'] = result
        save_result(result, output_dir=OUTPUT_DIR / "builtin")
        return  # 如果有内置字幕，直接返回

    # 方案2: OCR
    result = ocr_video_subtitles(url)
    if result:
        results['ocr'] = result
        save_result(result, output_dir=OUTPUT_DIR / "ocr")

    # 方案3: Whisper
    result = whisper_transcribe(url)
    if result:
        results['whisper'] = result
        save_result(result, output_dir=OUTPUT_DIR / "whisper")

    # 打印对比
    if len(results) > 1:
        print("\n" + "=" * 70)
        print("📊 对比结果")
        print("=" * 70)

        for method, result in results.items():
            timing = result.get('timing', {})
            print(f"\n{method.upper()}:")
            print(f"   总耗时: {timing.get('total', 0):.2f}秒")
            print(f"   输出长度: {len(result['content'])} 字符")
            if 'speed_ratio' in timing:
                print(f"   速度比: {timing['speed_ratio']:.2f}x 实时")

        # 速度对比
        if 'ocr' in results and 'whisper' in results:
            ocr_time = results['ocr']['timing']['total']
            whisper_time = results['whisper']['timing']['total']

            print(f"\n🏆 速度对比:")
            if ocr_time < whisper_time:
                ratio = whisper_time / ocr_time
                print(f"   OCR 比 Whisper 快 {ratio:.2f}x")
            else:
                ratio = ocr_time / whisper_time
                print(f"   Whisper 比 OCR 快 {ratio:.2f}x")

            print(f"\n💡 建议:")
            if len(results['ocr']['content']) > 100:
                print(f"   • 视频中有大量文字，OCR 结果更丰富")
            else:
                print(f"   • 视频中文字较少，Whisper 语音识别更完整")


def process_url(url: str, compare: bool = False) -> bool:
    """处理URL"""
    print("=" * 70)
    print("🎬 终极视频转录工具")
    print("=" * 70)

    platform = detect_platform(url)
    print(f"🔍 平台: {platform.upper()}")
    print(f"🔗 链接: {url[:60]}...")
    print(f"📌 Whisper模型: {WHISPER_MODEL}")
    print(f"🤖 OCR: {'启用' if USE_OCR else '禁用'}")

    if compare:
        compare_all_methods(url)
        return True

    # 智能选择
    result = check_builtin_subtitles(url)
    if result:
        print("\n✅ 使用方案: 内置字幕")
        save_result(result, OUTPUT_DIR)
        return True

    result = ocr_video_subtitles(url)
    if result:
        print("\n✅ 使用方案: 视频OCR")
        save_result(result, OUTPUT_DIR)
        return True

    result = whisper_transcribe(url)
    if result:
        print("\n✅ 使用方案: Whisper语音")
        save_result(result, OUTPUT_DIR)
        return True

    print("\n❌ 所有方案均失败")
    return False


def main():
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import argparse
    parser = argparse.ArgumentParser(description="终极视频转录工具")
    parser.add_argument("-u", "--url", help="视频链接")
    parser.add_argument("--compare", action="store_true", help="对比所有方案")
    parser.add_argument("--model", default="small", help="Whisper模型")
    parser.add_argument("--no-ocr", action="store_true", help="禁用OCR")

    args = parser.parse_args()

    global WHISPER_MODEL, USE_OCR
    WHISPER_MODEL = args.model
    USE_OCR = not args.no_ocr

    if args.url:
        process_url(args.url, compare=args.compare)
    else:
        url = input("粘贴视频链接: ").strip()
        if url:
            process_url(url)


if __name__ == "__main__":
    main()
