# 视频转录工具 - 快速使用指南

## 工具总览

| 工具 | 功能 | 推荐场景 |
|------|------|---------|
| `xiaohongshu_transcribe.py` | 小红书专属转录 | 小红书视频 |
| `streaming_transcribe.py` | B站+小红书统一 | 多平台混合 |
| `check_subtitle.py` | 检查内置字幕 | 确认是否有字幕 |
| `smart_transcribe.py` | 智能方案选择 | 自动优化 |

---

## 快速开始

### 1️⃣ 小红书视频转录

```bash
python xiaohongshu_transcribe.py
```

然后：
1. 选择模式 (1=单链接, 2=批量, 3=快速)
2. 粘贴小红书链接
3. 等待完成

**输出：** `output/xiaohongshu/标题.txt`

---

### 2️⃣ B站/小红书统一工具

```bash
# 单链接
python streaming_transcribe.py -u "视频链接"

# 批量处理
python streaming_transcribe.py -f "links.txt"

# 交互模式
python streaming_transcribe.py -i
```

**输出：** `output/transcripts/平台_标题.*`

---

### 3️⃣ 检查是否有内置字幕

```bash
python check_subtitle.py -u "视频链接"
```

**输出示例：**
```
✅ 发现内置字幕!
   类型: manual
   - 语言: zh-CN
```

---

### 4️⃣ 智能自动选择

```bash
python smart_transcribe.py -u "视频链接"
```

**自动流程：**
1. 检查内置字幕 → 有则直接提取
2. 尝试 OCR 识别 → [开发中]
3. Whisper 语音识别 → 最准确

---

## 输出格式

每个工具都会生成 3 种格式：

| 格式 | 用途 | 示例 |
|------|------|------|
| `.txt` | 纯文本 | 直接复制使用 |
| `.srt` | 字幕文件 | 视频播放器 |
| `.json` | 完整数据 | 程序处理 |

---

## 常见问题

### Q: 下载速度慢？
**A:** 工具已优化并发下载。如仍慢：
- 检查网络连接
- 尝试使用代理

### Q: Whisper 识别不准？
**A:** 调整模型大小：
```python
# 编辑文件顶部
WHISPER_MODEL = "large"  # 更准确但更慢
```

### Q: B站 403 错误？
**A:** 已修复防盗链问题。如仍出现：
- 更新 yt-dlp: `pip install -U yt-dlp`

### Q: 如何批量处理？
**A:** 创建 `links.txt`：
```
https://www.bilibili.com/video/BV1xx411c7xx
https://www.xiaohongshu.com/explore/xxxx
```

然后：
```bash
python streaming_transcribe.py -f links.txt
```

---

## 配置技巧

### 切换 Whisper 模型

编辑任意 `.py` 文件顶部：
```python
WHISPER_MODEL = "small"   # 快速
WHISPER_MODEL = "medium"  # 平衡（默认）
WHISPER_MODEL = "large"   # 精准
```

### 修改输出位置
```python
OUTPUT_DIR = Path("output/my_folder")
```

### 添加下载代理
```python
ydl_opts = {
    'proxy': 'http://127.0.0.1:7890',
    ...
}
```

---

## 性能参考

| 视频时长 | 下载 | 转录(medium) | 总计 |
|---------|------|--------------|------|
| 1分钟 | ~10秒 | ~30秒 | ~40秒 |
| 5分钟 | ~30秒 | ~2分钟 | ~2.5分钟 |
| 10分钟 | ~1分钟 | ~4分钟 | ~5分钟 |

*基于中等配置电脑，实际速度因硬件而异*

---

## 依赖安装

```bash
# Python 依赖
pip install yt-dlp openai-whisper

# FFmpeg（必需）
# Windows: 下载 ffmpeg.exe 并添加到 PATH
# Linux/Mac: brew install ffmpeg 或 sudo apt install ffmpeg
```

---

## 文件说明

```
biliSub/
├── xiaohongshu_transcribe.py      # 小红书工具
├── streaming_transcribe.py        # 统一工具
├── check_subtitle.py              # 字幕检查
├── smart_transcribe.py            # 智能工具
├── PROJECT_SUMMARY.md             # 完整文档
├── README_TOOLS.md                # 本文件
└── output/
    ├── xiaohongshu/               # 小红书输出
    └── transcripts/               # 转录输出
```

---

## 获取帮助

```bash
# 查看工具帮助
python xiaohongshu_transcribe.py --help
python streaming_transcribe.py --help
python check_subtitle.py --help

# 测试环境
python -c "import whisper; import yt_dlp; print('环境OK')"
```

---

**提示：** 首次使用会自动下载 Whisper 模型（medium 约 769MB），请耐心等待。

**最后更新：** 2026-02-15
