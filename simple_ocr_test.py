#!/usr/bin/env python3
"""
简化OCR测试 - 使用PaddleOCR

流程:
1. 下载视频
2. 提取关键帧
3. PaddleOCR识别
4. 统计时间
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path

import yt_dlp

# ==================== 配置 ====================
OUTPUT_DIR = Path("output/ocr_test")
FRAMES_TO_EXTRACT = 10  # 提取帧数（用于测试）
# ==============================================


def test_ocr_pipeline(url: str):
    """测试完整OCR流程"""
    print("=" * 70)
    print("🔬 视频OCR测试")
    print("=" * 70)

    total_start = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 步骤1: 下载视频
        print("\n⬇️  步骤 1/4: 下载视频")
        download_start = time.time()

        ydl_opts = {
            'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',  # 兼容格式
            'outtmpl': str(temp_path / 'video.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'concurrentfragments': 4,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_file = list(temp_path.glob('video.*'))[0]
                title = info.get('title', 'unknown')[:50]
                duration = info.get('duration', 0)

            download_time = time.time() - download_start
            print(f"✅ 下载完成: {download_time:.2f}秒")
            print(f"📹 视频: {title}")
            print(f"⏱️  时长: {duration}秒")

        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return

        # 步骤2: 提取帧
        print(f"\n📸 步骤 2/4: 提取关键帧 ({FRAMES_TO_EXTRACT}帧)")
        extract_start = time.time()

        frames_dir = temp_path / 'frames'
        frames_dir.mkdir()

        # 使用ffmpeg提取帧
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(video_file),
            '-vf', f'fps=1',  # 每秒1帧
            '-vframes', str(FRAMES_TO_EXTRACT),
            str(frames_dir / 'frame_%04d.jpg'),
            '-loglevel', 'error',
            '-y'
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ FFmpeg错误: {result.stderr}")
            return

        frame_count = len(list(frames_dir.glob('*.jpg')))
        extract_time = time.time() - extract_start
        print(f"✅ 提取完成: {extract_time:.2f}秒 ({frame_count}帧)")

        # 步骤3: OCR识别
        print(f"\n🔎 步骤 3/4: OCR识别")
        ocr_start = time.time()

        try:
            from paddleocr import PaddleOCR

            # 禁用模型检查提示
            os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

            ocr = PaddleOCR(
                use_textline_orientation=True,  # 新参数名
                lang='ch'
            )
            all_text = []

            for i, frame_file in enumerate(sorted(frames_dir.glob('*.jpg')), 1):
                print(f"   处理帧 {i}/{frame_count}...", end='\r')
                result = ocr.ocr(str(frame_file), cls=True)

                if result and result[0]:
                    for line in result[0]:
                        if line[1][0]:
                            all_text.append(line[1][0])

            ocr_text = '\n'.join(all_text)
            ocr_time = time.time() - ocr_start
            print(f"\n✅ 识别完成: {ocr_time:.2f}秒")
            print(f"📊 识别到 {len(all_text)} 行文字")

        except ImportError:
            print("❌ 未安装PaddleOCR")
            print("   安装: pip install paddleocr")
            return
        except Exception as e:
            print(f"❌ OCR失败: {e}")
            return

        # 步骤4: 保存结果
        print(f"\n💾 步骤 4/4: 保存结果")
        save_start = time.time()

        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)

        # TXT
        txt_path = output_dir / f"{safe_title}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(ocr_text)

        # JSON
        import json
        json_path = output_dir / f"{safe_title}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'title': title,
                'duration': duration,
                'frame_count': frame_count,
                'text_lines': len(all_text),
                'text': ocr_text,
                'timing': {
                    'download': download_time,
                    'extract': extract_time,
                    'ocr': ocr_time,
                    'total': time.time() - total_start
                }
            }, f, ensure_ascii=False, indent=2)

        save_time = time.time() - save_start

        # 打印总结
        total_time = time.time() - total_start

        print(f"✅ 保存完成: {save_time:.2f}秒")

        print(f"\n{'='*70}")
        print(f"📊 时间统计:")
        print(f"   下载视频: {download_time:.2f}秒")
        print(f"   提取帧: {extract_time:.2f}秒")
        print(f"   OCR识别: {ocr_time:.2f}秒")
        print(f"   保存结果: {save_time:.2f}秒")
        print(f"   总耗时: {total_time:.2f}秒")
        print(f"   速度比: {duration/total_time:.2f}x 实时" if total_time > 0 else "")

        print(f"\n📁 输出文件:")
        print(f"   📄 {txt_path.name}")
        print(f"   📊 {json_path.name}")

        # 显示部分结果
        if ocr_text.strip():
            preview = ocr_text[:200].replace('\n', ' ')
            print(f"\n📝 预览:")
            print(f"   {preview}...")


def main():
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import argparse
    parser = argparse.ArgumentParser(description="视频OCR测试工具")
    parser.add_argument("-u", "--url", help="视频链接")

    args = parser.parse_args()

    if args.url:
        test_ocr_pipeline(args.url)
    else:
        # 默认测试链接
        url = "https://www.bilibili.com/video/BV1fkzpB8EqD"
        test_ocr_pipeline(url)


if __name__ == "__main__":
    main()
