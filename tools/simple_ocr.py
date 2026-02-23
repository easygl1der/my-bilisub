#!/usr/bin/env python3
"""
简单的视频 OCR 工具
用法: python simple_ocr.py <B站视频链接>
"""

import sys
import tempfile
import subprocess
from pathlib import Path

# 下载视频（使用 yt-dlp）
def download_video(url, output_dir="."):
    print(f"⬇️  下载视频: {url}")
    result = subprocess.run([
        "yt-dlp",
        "-f", "worst[ext=mp4]/worst",  # 最低画质，下载快
        "-o", f"{output_dir}/video.%(ext)s",
        url
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ 下载失败: {result.stderr}")
        return None

    # 找到下载的视频文件
    video_file = list(Path(output_dir).glob("video.*"))
    return video_file[0] if video_file else None


# OCR 识别（使用 RapidOCR，Mac 友好）
def ocr_video(video_path):
    try:
        from rapidocr import RapidOCR
    except ImportError:
        print("📦 安装 RapidOCR...")
        subprocess.run([sys.executable, "-m", "pip", "install", "rapidocr-onnxruntime"], check=True)
        from rapidocr import RapidOCR

    print("🔍 初始化 OCR...")
    ocr = RapidOCR()
    print("🎬 开始识别...")

    # 用 ffmpeg 读取视频帧
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json", str(video_path)
    ], capture_output=True, text=True)

    import json
    info = json.loads(result.stdout)
    w = int(info['streams'][0]['width'])
    h = int(info['streams'][0]['height'])

    # 流式读取 + OCR
    ffmpeg_cmd = [
        "ffmpeg", "-i", str(video_path), "-loglevel", "error",
        "-vf", "select=not(mod(n\\,30))",  # 每秒1帧
        "-vsync", "0", "-f", "image2pipe", "-pix_fmt", "bgr24",
        "-vcodec", "rawvideo", "pipe:"
    ]

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    frame_size = w * h * 3

    texts = []
    frame_idx = 0

    import numpy as np
    while True:
        raw = process.stdout.read(frame_size)
        if len(raw) != frame_size:
            break
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
        result, _ = ocr(frame)
        if result:
            for line in result:
                texts.append(line[0])
        frame_idx += 30
        if frame_idx % 300 == 0:
            print(f"  进度: {frame_idx//30}秒")

    process.terminate()
    return texts


def main():
    if len(sys.argv) < 2:
        url = input("请输入 B站视频链接: ").strip()
    else:
        url = sys.argv[1]

    # 下载
    video_file = download_video(url)
    if not video_file:
        return

    print(f"✅ 下载完成: {video_file}")

    # OCR
    texts = ocr_video(video_file)

    # 输出
    print(f"\n📝 识别结果 ({len(texts)} 条):")
    print("=" * 50)
    for i, text in enumerate(texts[:20], 1):
        print(f"[{i}] {text}")

    if len(texts) > 20:
        print(f"... 还有 {len(texts)-20} 条")

    # 保存
    output_file = video_file.with_suffix(".txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(texts))
    print(f"\n💾 已保存到: {output_file}")

    # 清理视频文件
    video_file.unlink()
    print("🗑️  临时视频已删除")


if __name__ == "__main__":
    main()
