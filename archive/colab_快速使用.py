# 🎬 Colab 快速使用 - 复制到 Colab 单元格运行

# ============= 安装依赖 =============
!pip install -q openai-whisper yt-dlp

# ============= 配置 =============
VIDEO_URL = "https://www.bilibili.com/video/BVxxxxx"  # 👈 改成你的链接
MODEL = "small"  # tiny/base/small/medium/large

# ============= 下载音频 + Whisper 转录 =============
import yt_dlp, whisper, torch, re
from pathlib import Path

# 下载音频
print("⬇️ 下载音频...")
ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'audio.%(ext)s', 'quiet': True}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(VIDEO_URL, download=True)
    title = info.get('title', 'video')

audio_file = list(Path('.').glob('audio.*'))[0]
print(f"✅ 音频: {audio_file}")

# Whisper 转录
print(f"🎙️ Whisper 转录 ({MODEL})...")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model(MODEL, device=device)
result = model.transcribe(str(audio_file), language='zh')

# 保存 SRT
safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
srt_file = f"{safe_title}.srt"
with open(srt_file, 'w', encoding='utf-8') as f:
    for i, seg in enumerate(result['segments'], 1):
        h1, m1, s1 = int(seg['start']//3600), int((seg['start']%3600)//60), int(seg['start']%60)
        h2, m2, s2 = int(seg['end']//3600), int((seg['end']%3600)//60), int(seg['end']%60)
        ms1, ms2 = int((seg['start']%1)*1000), int((seg['end']%1)*1000)
        f.write(f"{i}\n{h1:02d}:{m1:02d}:{s1:02d},{ms1:03d} --> {h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}\n{seg['text'].strip()}\n\n")

print(f"✅ 完成: {srt_file}")

# ============= 下载到本地 =============
from google.colab import files
files.download(srt_file)
