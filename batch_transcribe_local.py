#!/usr/bin/env python3
"""
批量本地视频 Whisper 转录工具

功能:
1. 扫描指定目录下的所有视频文件
2. 使用 Whisper 进行语音识别
3. 生成 SRT 字幕文件

支持格式: mp4, mkv, avi, mov, flv, wmv, webm

使用示例:
    # 处理 downloaded_videos 目录下所有视频
    python batch_transcribe_local.py -i downloaded_videos

    # 只处理指定作者的视频
    python batch_transcribe_local.py -i downloaded_videos/作者名

    # 指定 Whisper 模型
    python batch_transcribe_local.py -i downloaded_videos -m medium

    # 跳过已存在字幕的视频
    python batch_transcribe_local.py -i downloaded_videos --skip-existing
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================
WHISPER_MODEL = "small"  # tiny/base/small/medium/large
OUTPUT_DIR = "output/transcripts"
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v'}
# ==============================================


def find_videos(input_dir: Path, recursive: bool = True) -> list:
    """查找目录下的所有视频文件"""
    videos = []

    if recursive:
        for ext in VIDEO_EXTENSIONS:
            videos.extend(input_dir.rglob(f'*{ext}'))
    else:
        for ext in VIDEO_EXTENSIONS:
            videos.extend(input_dir.glob(f'*{ext}'))

    return sorted(videos, key=lambda p: p.stat().st_mtime)


def extract_audio(video_path: Path, output_dir: Path) -> Path:
    """使用 ffmpeg 提取音频"""
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{video_path.stem}.wav"

    # 检查是否已存在
    if audio_path.exists():
        return audio_path

    print(f"   ⬇️  提取音频...")
    start = time.time()

    cmd = [
        'ffmpeg', '-i', str(video_path),
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        '-y', str(audio_path),
        '-loglevel', 'error'
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {result.stderr.decode('utf-8', errors='ignore')}")

    print(f"   ✅ 音频提取完成 ({time.time()-start:.1f}秒)")
    return audio_path


def transcribe_whisper(audio_path: Path, model: str = "small", language: str = "zh") -> dict:
    """使用 Whisper 转录音频"""
    import whisper

    print(f"   🎙️  Whisper 转录中 (模型: {model})...")
    start = time.time()

    # 检测 GPU
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"   🔧 设备: {device.upper()}")

    # 加载模型
    load_start = time.time()
    model_obj = whisper.load_model(model, device=device)
    print(f"   ✅ 模型加载 ({time.time()-load_start:.1f}秒)")

    # 转录
    result = model_obj.transcribe(
        str(audio_path),
        language=language,
        verbose=False
    )

    transcribe_time = time.time() - start
    print(f"   ✅ 转录完成 ({transcribe_time:.1f}秒)")

    return result


def save_srt(result: dict, output_path: Path, video_name: str):
    """保存为 SRT 格式"""
    output_path.mkdir(parents=True, exist_ok=True)
    srt_path = output_path / f"{video_name}.srt"

    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(result['segments'], 1):
            def fmt(t):
                h, m, s = int(t//3600), int((t%3600)//60), int(t%60)
                ms = int((t%1)*1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            f.write(f"{i}\n{fmt(seg['start'])} --> {fmt(seg['end'])}\n{seg['text'].strip()}\n\n")

    print(f"   📄 字幕已保存: {srt_path.name}")
    return srt_path


def save_txt(result: dict, output_path: Path, video_name: str):
    """保存为纯文本"""
    output_path.mkdir(parents=True, exist_ok=True)
    txt_path = output_path / f"{video_name}.txt"

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(result['text'])

    return txt_path


def process_video(video_path: Path, model: str, output_dir: Path, skip_existing: bool = False) -> dict:
    """处理单个视频"""
    result = {
        'video': str(video_path),
        'video_name': video_path.stem,
        'success': False,
        'error': None,
        'elapsed': 0,
        'srt_path': None,
        'txt_path': None
    }

    # 检查是否已存在字幕
    srt_path = output_dir / f"{video_path.stem}.srt"
    if skip_existing and srt_path.exists():
        result['success'] = True
        result['skip_reason'] = '字幕已存在'
        result['srt_path'] = str(srt_path)
        return result

    start = time.time()

    try:
        print(f"\n{'='*70}")
        print(f"🎬 处理: {video_path.name}")
        print(f"{'='*70}")

        # 提取音频
        audio_dir = Path("output/audio")
        audio_path = extract_audio(video_path, audio_dir)

        # Whisper 转录
        transcribe_result = transcribe_whisper(audio_path, model)

        # 保存结果
        srt_path = save_srt(transcribe_result, output_dir, video_path.stem)
        txt_path = save_txt(transcribe_result, output_dir, video_path.stem)

        result['success'] = True
        result['elapsed'] = time.time() - start
        result['srt_path'] = str(srt_path)
        result['txt_path'] = str(txt_path)
        result['duration'] = transcribe_result.get('segments', [-1])[-1].get('end', 0) if transcribe_result.get('segments') else 0

        print(f"   ✅ 完成! 总耗时: {result['elapsed']:.1f}秒")

    except Exception as e:
        result['error'] = str(e)
        result['elapsed'] = time.time() - start
        print(f"   ❌ 失败: {e}")

    return result


def batch_process(input_dir: str, model: str = "small", skip_existing: bool = False):
    """批量处理"""
    input_path = Path(input_dir)
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找视频
    print(f"📁 扫描目录: {input_path}")
    videos = find_videos(input_path)

    if not videos:
        print("❌ 未找到视频文件")
        return

    print(f"✅ 找到 {len(videos)} 个视频文件\n")

    # 统计信息
    results = []
    success_count = 0
    skip_count = 0
    fail_count = 0
    total_time = 0

    for i, video_path in enumerate(videos, 1):
        print(f"\n[进度: {i}/{len(videos)}]")

        result = process_video(video_path, model, output_path, skip_existing)
        results.append(result)

        if result['success']:
            if 'skip_reason' in result:
                skip_count += 1
            else:
                success_count += 1
                total_time += result['elapsed']
        else:
            fail_count += 1

        # 避免过载
        if i < len(videos):
            time.sleep(1)

    # 打印总结
    print(f"\n{'='*70}")
    print("🎉 批量处理完成!")
    print(f"{'='*70}")
    print(f"   总数: {len(videos)}")
    print(f"   成功: {success_count}")
    print(f"   跳过: {skip_count}")
    print(f"   失败: {fail_count}")

    if success_count > 0:
        print(f"   总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
        print(f"   平均: {total_time/success_count:.1f}秒/视频")

    print(f"\n📁 输出目录: {output_path.absolute()}")

    # 保存报告
    report_path = output_path / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"批量转录报告\n")
        f.write(f"{'='*60}\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"输入目录: {input_path}\n")
        f.write(f"Whisper模型: {model}\n\n")
        f.write(f"总数: {len(videos)} | 成功: {success_count} | 跳过: {skip_count} | 失败: {fail_count}\n\n")

        for i, r in enumerate(results, 1):
            status = "✅" if r['success'] else "❌"
            if r['success'] and 'skip_reason' in r:
                status = "⏭️ "
            f.write(f"{i}. {status} {Path(r['video']).name}\n")
            if r.get('error'):
                f.write(f"   错误: {r['error']}\n")

    print(f"📄 报告已保存: {report_path.name}")


def main():
    parser = argparse.ArgumentParser(
        description="批量本地视频 Whisper 转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 处理 downloaded_videos 目录下所有视频:
   python batch_transcribe_local.py -i downloaded_videos

2. 指定 Whisper 模型:
   python batch_transcribe_local.py -i downloaded_videos -m medium

3. 跳过已存在字幕的视频:
   python batch_transcribe_local.py -i downloaded_videos --skip-existing

4. 只处理单个目录（不递归）:
   python batch_transcribe_local.py -i downloaded_videos --no-recursive
        """
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='输入目录（包含视频文件的文件夹）'
    )
    parser.add_argument(
        '-m', '--model',
        default='small',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper 模型（默认: small）'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='跳过已存在字幕的视频'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归扫描子目录'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 目录不存在: {args.input}")
        return

    batch_process(
        input_dir=str(input_path),
        model=args.model,
        skip_existing=args.skip_existing
    )


if __name__ == "__main__":
    main()
