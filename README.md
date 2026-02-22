# BiliSub - 视频内容 AI 分析工具

基于 Gemini AI 的视频内容分析工具，支持 B站、小红书、YouTube 等平台的视频下载与智能分析。

**核心功能：一键下载视频 → AI 分析生成知识库笔记**

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 Gemini API Key
# 方式一：环境变量（推荐）
export GEMINI_API_KEY='your-key'

# 方式二：创建 config_api.py
# API_CONFIG = {"gemini": {"api_key": "your-key"}}

# 3. 分析单个视频
python analysis/video_understand_gemini.py -video "视频路径" -m knowledge

# 4. 批量分析目录
python analysis/video_understand_gemini.py -dir "视频目录" -m knowledge
```

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **视频下载** | 支持 B站/小红书/YouTube，流式下载提速 4 倍 |
| **Gemini 分析** | AI 视频内容理解，5 种分析模式 |
| **知识库笔记** | 自动生成结构化笔记，适合构建第二大脑 |
| **批量处理** | 支持目录批量分析，自动并发 |

---

## Gemini 分析模式

| 模式 | 输出内容 | 适用场景 |
|------|---------|---------|
| `knowledge` | 知识库型笔记 | **推荐，构建第二大脑** |
| `summary` | 详细总结 | 内容概览 |
| `brief` | 简洁总结 | 快速了解 |
| `detailed` | 深度分析 | 完整理解 |
| `transcript` | 对话提取 | 访谈整理 |

### knowledge 模式输出结构

```
## 📋 视频基本信息
- 视频类型、核心主题、内容结构

## 📖 视频大意（100-200字）
精炼概括核心内容

## 🎯 核心观点（三段论）
大前提、小前提、结论

## 📊 论点论据结构
主要论点、次要论点及支撑

## 💎 金句提取
引经据典、故事案例、精辟论据

## 📝 书面文稿
去除口语冗余的正式文本

## ⚠️ 内容质量分析
情绪操控检测、信息可靠性评估

## 🔗 相关延伸
推荐深入了解的方向
```

---

## 使用方法

### 方式一：直接分析视频文件

```bash
# 分析已下载的视频
python analysis/video_understand_gemini.py \
    -video "downloaded/video.mp4" \
    -m knowledge
```

### 方式二：下载 + 分析

```bash
# 先下载视频
yt-dlp "视频URL" -o "downloaded/%(title)s.%(ext)s"

# 再分析
python analysis/video_understand_gemini.py \
    -video "downloaded/video.mp4" \
    -m knowledge
```

### 方式三：批量分析目录

```bash
# 批量分析（自动并发，flash-lite 模型 10 线程）
python analysis/video_understand_gemini.py \
    -dir "downloaded_videos" \
    -m knowledge

# 指定并发数
python analysis/video_understand_gemini.py \
    -dir "downloaded_videos" \
    -j 5
```

### 方式四：只处理新视频

```bash
# 自动跳过已分析的视频
python analysis/video_understand_gemini.py \
    -dir "downloaded_videos" \
    -m knowledge
```

---

## 命令行参数

```
python analysis/video_understand_gemini.py [选项]

必需参数（二选一）:
  -video PATH      单个视频文件路径
  -dir PATH        视频目录（批量处理）

分析模式:
  -m, --mode TEXT  分析模式 (默认: knowledge)
                  可选: knowledge/summary/brief/detailed/transcript

Gemini 设置:
  --model TEXT     Gemini 模型 (默认: flash-lite)
                  可选: flash-lite/flash/pro
  -j, --jobs INT   并发处理数 (默认: 自动设置)
                  flash-lite: 10, flash: 3, pro: 6
  --api-key TEXT   Gemini API Key (覆盖配置文件)

输出控制:
  -o, --output PATH    输出目录 (默认: gemini_analysis)
  --keep               保留上传的文件
  --force              强制重新处理所有视频

其他:
  --list-modes     列出所有提示词模式
```

---

## Gemini 模型选择

| 模型 | 请求/分钟 | 请求/天 | 速度 | 质量 | 推荐 |
|------|----------|---------|------|------|------|
| **flash-lite** | 15 | 1000 | 快 | 良好 | 批量处理 |
| flash | 5 | 100 | 中 | 很好 | 日常使用 |
| pro | 10 | 100 | 慢 | 最佳 | 高质量需求 |

**免费配额说明：**
- flash-lite：每天 1000 次请求
- flash/pro：每天 100 次请求
- 配额每天 0 点重置

---

## 项目结构

```
biliSub/
├── analysis/
│   └── video_understand_gemini.py    # 主分析工具
├── config_api.py                     # API 配置文件
├── requirements.txt                  # 依赖清单
├── docs/                             # 文档
│   └── README_FULL.md                # 完整文档
└── gemini_analysis/                  # 输出目录
    └── 作者名/
        └── 视频_时间戳.md
```

---

## 配置 API Key

### 方式一：环境变量（推荐）

```bash
# Linux/Mac
export GEMINI_API_KEY='your-key'

# Windows PowerShell
$env:GEMINI_API_KEY='your-key'

# Windows CMD
set GEMINI_API_KEY=your-key
```

### 方式二：配置文件

创建 `config_api.py`：

```python
API_CONFIG = {
    "gemini": {
        "api_key": "your_gemini_api_key"
    }
}
```

### 获取 API Key

1. 访问 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 创建项目
3. 生成 API Key

---

## 使用示例

### 示例 1：分析单个视频

```bash
python analysis/video_understand_gemini.py \
    -video "课程视频.mp4" \
    -m knowledge
```

### 示例 2：批量分析 UP 主视频

```bash
# 先用 yt-dlp 下载频道视频
yt-dlp -f "bestvideo+bestaudio" "频道URL" -o "downloads/%(uploader)s/%(title)s.%(ext)s"

# 批量分析
python analysis/video_understand_gemini.py \
    -dir "downloads/UP主名" \
    -m knowledge
```

### 示例 3：简洁模式快速了解

```bash
python analysis/video_understand_gemini.py \
    -video "video.mp4" \
    -m brief
```

### 示例 4：访谈对话提取

```bash
python analysis/video_understand_gemini.py \
    -video "访谈.mp4" \
    -m transcript
```

---

## 输出文件

分析结果保存为 Markdown 格式：

```
gemini_analysis/
└── 视频/
    └── 视频名称_20260221_120000.md
```

每个分析文件包含：
- 元信息表格（视频文件、分析时间、使用模型、Token 使用）
- 结构化分析内容
- 质量评估（信息可靠性、知识价值评级）

---

## 性能参考

| 视频时长 | flash-lite | flash | pro |
|---------|-----------|-------|-----|
| 5 分钟 | ~1 分钟 | ~1.5 分钟 | ~2 分钟 |
| 10 分钟 | ~2 分钟 | ~3 分钟 | ~4 分钟 |
| 30 分钟 | ~4 分钟 | ~6 分钟 | ~10 分钟 |

*注：包含上传和处理时间*

---

## 常见问题

### Q: 视频大小限制？

A: Gemini 最大支持 2GB 视频文件。超过建议先压缩或分段。

### Q: 配额用完了怎么办？

A: 等待第二天重置，或使用 flash-lite 模型（配额最多）。

### Q: 分析中断了怎么办？

A: 重新运行相同命令，会自动跳过已分析的视频。

### Q: 如何提高分析速度？

A:
1. 使用 flash-lite 模型
2. 增加并发数 `-j 10`
3. 确保网络稳定

---

## 可选功能：Whisper 字幕

如果需要提取视频字幕，可以使用内置的 Whisper 工具：

```bash
# 安装 Whisper
pip install openai-whisper

# 提取字幕
python ultimate_transcribe.py -u "视频URL" --model medium
```

**Whisper 模型选择：**
- `small` - 日常使用
- `medium` - 中文推荐
- `large` - 高精度需求

---

## 依赖安装

```bash
# 基础依赖（必需）
pip install google-generativeai yt-dlp

# 字幕功能（可选）
pip install openai-whisper

# Telegram Bot（可选）
pip install python-telegram-bot
```

或使用 requirements.txt：

```bash
pip install -r requirements.txt
```

---

## 更新日志

### v1.2 (2026-02)
- 新增 Gemini 2.5 系列模型支持
- 知识库型笔记生成模式
- 批量分析自动并发
- 模型自动切换（配额不足时）

---

## 相关链接

- [Gemini API 文档](https://ai.google.dev/)
- [yt-dlp 文档](https://github.com/yt-dlp/yt-dlp)
- [完整文档](docs/README_FULL.md)

---

## 许可证

MIT License - 仅供个人学习和研究使用
