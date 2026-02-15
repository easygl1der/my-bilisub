#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频流式转字幕：链接 → 音频流 → Whisper ASR → SRT/JSON 输出
依赖: pip install yt-dlp openai-whisper
"""

import yt_dlp
import whisper
import tempfile
import os
import sys
import json
from pathlib import Path

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def download_audio_stream(url, temp_dir):
    """流式下载 B站 音频到临时文件"""
    ydl_opts = {
        'format': 'bestaudio/best',      # 只下最佳音频
        'outtmpl': str(temp_dir / '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_file = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.' + info['ext']
        print(f"✅ 下载完成: {audio_file} (时长: {info.get('duration', '?')}s)")
        return audio_file

def transcribe_with_whisper(audio_file):
    """Whisper 转录"""
    print("🔄 Whisper 转录中（使用 medium 模型以提高精度）...")
    model = whisper.load_model("medium")  # tiny/base/small/medium/large
    result = model.transcribe(
        audio_file,
        language="zh",           # 中文
        task="transcribe",       # 转录（非翻译）
        verbose=True
    )
    return result

def save_srt(segments, output_path):
    """保存为 SRT 字幕文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg['start'])
            end = format_timestamp(seg['end'])
            f.write(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n\n")
    print(f"✅ SRT 保存: {output_path}")

def format_timestamp(seconds):
    """秒 → SRT 时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

if __name__ == "__main__":
    # 你的 B站链接
    url = "https://www.bilibili.com/video/BV1fkzpB8EqD?spm_id_from=333.1007.tianma.1-1-1.click"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Step 1: 流式下载音频
        audio_file = download_audio_stream(url, temp_path)

        # Step 2: Whisper 转录
        result = transcribe_with_whisper(audio_file)

        # Step 3: 保存结果
        title = result.get("language", "transcript")  # 可优化为视频标题
        srt_path = f"{title}.srt"
        json_path = f"{title}.json"

        save_srt(result["segments"], srt_path)

        # 保存完整 JSON（兼容你 Gummy 格式）
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "text": result["text"],
                "segments": result["segments"],
                "language": result["language"]
            }, f, ensure_ascii=False, indent=2)

        print(f"\n🎉 完成！")
        print(f"   SRT: {srt_path}")
        print(f"   JSON: {json_path}")
        print(f"   总字数: {len(result['text'])}")
