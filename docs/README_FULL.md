# BiliSub 完整使用指引

> 最后更新：2026-02-21
> 项目版本：v1.2

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统要求](#2-系统要求)
3. [安装配置](#3-安装配置)
4. [核心功能详解](#4-核心功能详解)
5. [命令行工具完整参数](#5-命令行工具完整参数)
6. [使用场景与最佳实践](#6-使用场景与最佳实践)
7. [输出文件说明](#7-输出文件说明)
8. [API配置与费用说明](#8-api配置与费用说明)
9. [常见问题排查](#9-常见问题排查)
10. [进阶功能](#10-进阶功能)

---

## 1. 项目概述

### 1.1 项目简介

**BiliSub** 是一个功能强大的视频字幕处理工具链，支持多个主流视频平台。

**核心能力：**
- 视频下载（支持流式下载，速度提升4倍）
- 内置字幕提取（最快方案）
- Whisper语音识别（高精度）
- GLM AI字幕优化（7种优化模式）
- Gemini AI视频内容分析（5种分析模式）

### 1.2 支持的平台

| 平台 | 支持功能 | 备注 |
|------|---------|------|
| **B站** | 下载、字幕提取、语音识别 | 需要处理防盗链 |
| **小红书** | 下载、字幕提取、语音识别 | 支持图文内容 |
| **YouTube** | 下载、字幕提取、语音识别 | 可能需要代理 |

### 1.3 项目结构

```
biliSub/
├── 核心工具（根目录）
│   ├── ultimate_transcribe.py      # 主转录工具（推荐）
│   ├── batch_process_videos.py     # 批量处理工具
│   ├── check_subtitle.py           # 字幕检查工具
│   ├── optimize_srt_glm.py         # GLM字幕优化
│   └── srt_prompts.py              # 优化提示词定义
│
├── 平台模块 (platforms/)
│   ├── bilibili/                   # B站相关
│   │   ├── fetch_bili_comments.py  # 评论抓取
│   │   └── update_cookie_now.py    # Cookie更新
│   ├── xiaohongshu/                # 小红书相关
│   │   ├── download_xhs_images.py  # 图片下载
│   │   ├── xhs_professor_monitor*.py  # 教授监控
│   │   └── update_xhs_cookie.py    # Cookie更新
│   └── youtube/                    # YouTube相关
│       └── youtube_channel_downloader.py  # 频道下载
│
├── AI分析模块 (analysis/)
│   ├── gemini_subtitle_summary.py  # Gemini字幕摘要
│   ├── video_understand_gemini.py  # Gemini视频分析
│   ├── comment_analyzer.py         # 评论分析
│   └── multimodal_gemini.py        # 多模态分析
│
├── 机器人模块 (bot/)
│   ├── video_bot.py                # Telegram机器人
│   ├── telegram_notifier.py        # 通知机器人
│   └── cookie_manager.py           # Cookie管理
│
├── 工具集 (utils/)
│   ├── batch_transcribe_local.py   # 本地视频批量转录
│   ├── enhanced_workflow.py        # 增强工作流
│   ├── download_videos_from_csv.py # CSV视频下载
│   └── auto_bili_workflow.py       # 自动化工作流
│
├── MediaCrawler/                   # 社交媒体爬虫子模块
│   └── (独立项目，支持多平台爬取)
│
└── 输出目录
    ├── output/ultimate/            # 主工具输出
    ├── output/transcripts/         # 字幕文件
    ├── output/optimized_srt/       # 优化后字幕
    ├── output/xiaohongshu/         # 小红书视频
    ├── gemini_analysis/            # Gemini分析结果
    └── downloaded_videos/          # 下载的视频
```

---

## 2. 系统要求

### 2.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 双核处理器 | 四核及以上 |
| 内存 | 4GB | 8GB+ |
| 硬盘 | 10GB 可用空间 | 50GB+ SSD |
| GPU | 无 | NVIDIA GPU（加速Whisper） |

### 2.2 软件要求

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.9+ | 推荐3.10或3.11 |
| ffmpeg | 最新版 | 视频处理必需 |
| 操作系统 | Windows/Linux/macOS | Windows需要UTF-8编码支持 |

### 2.3 Python依赖

```
# 核心依赖
yt-dlp          # 视频下载
whisper         # 语音识别
google-generativeai  # Gemini API
requests        # HTTP请求

# 可选依赖
paddleocr       # OCR识别
paddlepaddle    # PaddleOCR后端
python-telegram-bot  # Telegram Bot
```

---

## 3. 安装配置

### 3.1 基础安装

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/biliSub.git
cd biliSub

# 2. 安装Python依赖
pip install -r requirements.txt

# 3. 验证安装
python -c "import whisper; print('Whisper OK')"
python -c "import yt_dlp; print('yt-dlp OK')"
```

### 3.2 可选组件安装

```bash
# OCR支持（用于识别视频内文字）
pip install paddleocr opencv-python paddlepaddle

# Telegram Bot支持
pip install python-telegram-bot

# 新版 Gemini SDK
pip install google-genai
```

### 3.3 API配置

创建 `config_api.py` 文件：

```python
API_CONFIG = {
    # 智谱GLM API配置
    "zhipu": {
        "api_key": "your_zhipu_api_key",  # 从 https://open.bigmodel.cn/ 获取
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "temperature": 0.3,
        "top_p": 0.7,
        "max_tokens": 2000
    },

    # Gemini API配置
    "gemini": {
        "api_key": "your_gemini_api_key"  # 从 https://aistudio.google.com/app/apikey 获取
    }
}
```

### 3.4 环境变量配置（推荐）

```bash
# Linux/macOS
export ZHIPU_API_KEY='your-zhipu-key'
export GEMINI_API_KEY='your-gemini-key'
export TELEGRAM_BOT_TOKEN='your-bot-token'

# Windows PowerShell
$env:ZHIPU_API_KEY='your-zhipu-key'
$env:GEMINI_API_KEY='your-gemini-key'
$env:TELEGRAM_BOT_TOKEN='your-bot-token'

# Windows CMD
set ZHIPU_API_KEY=your-zhipu-key
set GEMINI_API_KEY=your-gemini-key
```

---

## 4. 核心功能详解

### 4.1 视频字幕提取（3种方案）

#### 方案对比

| 方案 | 速度 | 准确度 | 适用场景 |
|------|------|--------|---------|
| **内置字幕** | 最快（秒级） | 取决于作者 | 有CC字幕的视频 |
| **OCR识别** | 中等（分钟级） | 视频有文字时 | 纯文字视频/PPT |
| **Whisper识别** | 较慢（小时级） | 最高 | 所有视频 |

#### 方案1：检查内置字幕（推荐首选）

```bash
# 检查单个视频
python check_subtitle.py -u "视频URL"

# 批量检查
python check_subtitle.py -f videos.txt

# 保存检查报告
python check_subtitle.py -u "视频URL" --save
```

**输出信息：**
- 是否有内置字幕
- 字幕类型（手动/自动）
- 字幕语言
- 下载链接（如果有）

#### 方案2：Whisper语音识别

```bash
# 基础用法
python ultimate_transcribe.py -u "视频URL" --model medium

# 指定输出格式
python ultimate_transcribe.py -u "视频URL" -f srt,txt,json

# 对比所有方案
python ultimate_transcribe.py -u "视频URL" --compare
```

**Whisper模型选择：**

| 模型 | 文件大小 | 内存需求 | 速度 | 精度 | 推荐场景 |
|------|---------|---------|------|------|---------|
| tiny | ~40MB | ~1GB | 最快 | 较低 | 快速测试 |
| base | ~75MB | ~1GB | 快 | 中等 | 短视频 |
| small | ~250MB | ~2GB | 中等 | 良好 | 日常使用 |
| medium | ~770MB | ~5GB | 较慢 | 很好 | 中文推荐 |
| large | ~1550MB | ~10GB | 最慢 | 最佳 | 高精度需求 |

**输出格式：**
- `srt` - 标准字幕格式
- `ass` - 高级字幕格式
- `vtt` - Web字幕格式
- `txt` - 纯文本
- `json` - 结构化数据
- `lrc` - 歌词格式

#### 方案3：OCR视频文字识别

```bash
# 启用OCR（默认开启）
python ultimate_transcribe.py -u "视频URL"

# 禁用OCR
python ultimate_transcribe.py -u "视频URL" --no-ocr
```

**OCR适用场景：**
- PPT讲解类视频
- 代码教学视频
- 纯文字展示视频
- ASMR等无语音视频

### 4.2 字幕AI优化（GLM）

#### 7种优化模式详解

| 模式 | 特点 | 适用场景 |
|------|------|---------|
| **optimization** | 平衡模式，推荐 | 通用场景 |
| **simple** | 快速模式 | 批量处理 |
| **conservative** | 保守模式 | 高准确性要求 |
| **aggressive** | 深度优化 | 口语严重视频 |
| **tech** | 技术术语规范 | 技术教程 |
| **interview** | 对话格式处理 | 访谈/对话 |
| **vlog** | 自然口语化 | 生活/Vlog |

#### 使用方法

```bash
# 优化单个字幕文件
python optimize_srt_glm.py -s output/transcripts/video.srt

# 指定优化模式
python optimize_srt_glm.py -s video.srt -p tech

# 批量优化目录
python optimize_srt_glm.py -d output/transcripts/ -p optimization

# 调整批处理大小
python optimize_srt_glm.py -s video.srt -b 10
```

#### 优化效果对比

**优化前（Whisper原始输出）：**
```
一份引爆全网的cloud code调教指南
两天就引来170多万播放
前爷爷受损会导致认知能力下降
```

**优化后（GLM优化）：**
```
一份引爆全网的Cloud Code调教指南，两天就引来170多万播放。
前额叶受损会导致认知能力下降。
```

### 4.3 AI视频内容分析（Gemini）

#### 5种分析模式

| 模式 | 输出内容 | 适用场景 |
|------|---------|---------|
| **knowledge** | 知识库型笔记 | 构建第二大脑 |
| **summary** | 详细总结 | 内容概览 |
| **brief** | 简洁总结 | 快速了解 |
| **detailed** | 深度分析 | 完整理解 |
| **transcript** | 对话提取 | 访谈整理 |

#### 知识库模式详解

**knowledge** 模式输出结构：
```
## 📋 视频基本信息
- 视频类型、核心主题、内容结构

## 📖 视频大意
100-200字精炼概括

## 🎯 核心观点
三段论形式呈现论点

## 📊 论点论据结构
主要论点、次要论点及支撑

## 💎 金句提取
引经据典、故事案例、精辟论据等

## 📝 书面文稿
去除口语冗余的正式文本

## ⚠️ 内容质量分析
情绪操控检测、信息可靠性评估

## 🔗 相关延伸
推荐深入了解的方向
```

#### 使用方法

```bash
# 分析单个视频（默认knowledge模式）
python analysis/video_understand_gemini.py -video "video.mp4"

# 指定分析模式
python analysis/video_understand_gemini.py -video "video.mp4" -m brief

# 批量分析目录（自动并发）
python analysis/video_understand_gemini.py -dir "downloaded_videos" -m knowledge

# 指定模型
python analysis/video_understand_gemini.py -video "video.mp4" --model flash-lite

# 自定义并发数
python analysis/video_understand_gemini.py -dir "videos" -j 5

# 保留上传的文件
python analysis/video_understand_gemini.py -video "video.mp4" --keep
```

### 4.4 批量处理工作流

#### 方案1：一站式批量处理

```bash
# 从URL列表处理
python batch_process_videos.py -i videos.txt -m medium -p optimization

# 从CSV处理
python batch_process_videos.py -i videos.csv -m medium -p tech

# 命令行指定多个URL
python batch_process_videos.py -u "url1" -u "url2" -u "url3"
```

#### 方案2：增强工作流（集成MediaCrawler）

```bash
# 从MediaCrawler数据提取并处理
python utils/enhanced_workflow.py --mediacrawler

# 导出MediaCrawler数据为CSV
python utils/enhanced_workflow.py --mediacrawler --export-crawled videos.csv

# 只处理失败的视频
python utils/enhanced_workflow.py --csv videos.csv --filter fail

# 限制处理数量
python utils/enhanced_workflow.py --csv videos.csv --limit 3
```

#### 方案3：本地视频批量转录

```bash
# 处理整个目录
python utils/batch_transcribe_local.py -i "downloaded_videos"

# 指定Whisper模型
python utils/batch_transcribe_local.py -i "videos" -m medium

# 跳过已存在字幕的视频
python utils/batch_transcribe_local.py -i "videos" --skip-existing

# 不递归子目录
python utils/batch_transcribe_local.py -i "videos" --no-recursive
```

---

## 5. 命令行工具完整参数

### 5.1 ultimate_transcribe.py

主转录工具，集成所有方案。

```bash
python ultimate_transcribe.py [选项]

选项:
  -u, --url TEXT          视频链接（支持B站/小红书/YouTube）
  --model TEXT            Whisper模型: tiny/base/small/medium/large
  --no-ocr                禁用OCR识别
  --compare               对比所有方案（内置字幕/OCR/Whisper）
  -f, --format TEXT       输出格式: srt,ass,vtt,json,txt,lrc
```

**使用示例：**
```bash
# 完整命令示例
python ultimate_transcribe.py \
    -u "https://www.bilibili.com/video/BV1xx411c79H" \
    --model medium \
    -f srt,txt \
    --no-ocr
```

### 5.2 optimize_srt_glm.py

GLM字幕优化工具。

```bash
python optimize_srt_glm.py [选项]

选项:
  -s, --srt PATH          SRT文件路径
  -d, --dir PATH          批量处理目录
  -p, --prompt TEXT       优化模式: optimization/simple/conservative/
                          aggressive/tech/interview/vlog
  -b, --batch-size INT    批处理大小（默认: 5）
```

**使用示例：**
```bash
# 技术视频优化
python optimize_srt_glm.py \
    -s "output/transcribes/tutorial.srt" \
    -p tech \
    -b 10

# 批量优化
python optimize_srt_glm.py \
    -d "output/transcribes/" \
    -p optimization \
    -b 5
```

### 5.3 batch_process_videos.py

批量视频处理工具。

```bash
python batch_process_videos.py [选项]

选项:
  -u, --urls TEXT [TEXT...]  一个或多个视频URL
  -i, --input-file PATH       URL列表文件（txt/csv）
  -m, --model TEXT            Whisper模型（默认: medium）
  -p, --prompt TEXT           GLM优化模式（默认: optimization）
  -o, --output PATH           报告输出文件（默认: batch_report.json）
```

**使用示例：**
```bash
# 完整批量处理
python batch_process_videos.py \
    -i course_videos.txt \
    -m medium \
    -p tech \
    -o "reports/course_report.json"
```

### 5.4 video_understand_gemini.py

Gemini视频分析工具。

```bash
python analysis/video_understand_gemini.py [选项]

选项:
  -video, --video-file PATH    视频文件路径
  -dir, --directory PATH       视频目录（批量处理）
  -csv, --csv-file PATH        CSV文件（用于状态跟踪）
  -m, --mode TEXT              分析模式: summary/brief/detailed/
                               transcript/knowledge
  -p, --prompt TEXT            自定义提示词
  --model TEXT                 Gemini模型: flash/flash-lite/pro
  -o, --output PATH            输出目录（默认: gemini_analysis）
  -j, --jobs INT               并发处理数
  --force                      强制重新处理所有视频
  --keep                       保留上传的文件
  --list-modes                 列出所有提示词模式
  --api-key TEXT               Gemini API Key
```

**使用示例：**
```bash
# 知识库模式批量分析
python analysis/video_understand_gemini.py \
    -dir "downloaded_videos" \
    -m knowledge \
    --model flash-lite \
    -j 10 \
    -o "analysis_results"
```

### 5.5 gemini_subtitle_summary.py

字幕摘要生成工具。

```bash
python analysis/gemini_subtitle_summary.py [选项]

选项:
  subtitle_dir                字幕文件夹路径（必需）
  -m, --model TEXT            Gemini模型: flash/flash-lite/pro
  -j, --jobs INT              并发处理数（默认: 3）
  -p, --prompt TEXT           自定义汇总提示词
  --api-key TEXT              Gemini API Key
  -i, --incremental           增量模式：跳过已处理的视频
  -a, --append                追加模式：保留已有结果
```

**使用示例：**
```bash
# 生成作者视频摘要
python analysis/gemini_subtitle_summary.py \
    "output/transcripts/作者名" \
    -m flash-lite \
    -j 5 \
    -a
```

---

## 6. 使用场景与最佳实践

### 6.1 场景1：学习笔记整理

**目标：将课程视频转化为结构化笔记**

```bash
# 步骤1：下载视频并提取字幕
python ultimate_transcribe.py -u "课程视频URL" --model medium

# 步骤2：优化字幕（技术模式）
python optimize_srt_glm.py -s output/transcripts/course.srt -p tech

# 步骤3：生成知识库笔记
python analysis/video_understand_gemini.py \
    -video "downloaded/course.mp4" \
    -m knowledge
```

### 6.2 场景2：UP主内容批量分析

**目标：分析某个UP主的所有视频**

```bash
# 步骤1：下载频道视频
python platforms/youtube/youtube_channel_downloader.py "频道URL"

# 步骤2：批量转录
python utils/batch_transcribe_local.py \
    -i "downloaded_videos/UP主名" \
    -m medium \
    --skip-existing

# 步骤3：生成汇总报告
python analysis/gemini_subtitle_summary.py \
    "output/transcripts/UP主名" \
    -m flash-lite \
    -j 5
```

### 6.3 场景4：视频内容数据库构建

**目标：构建个人视频知识库**

```bash
# 完整流程脚本
for url in $(cat video_list.txt); do
    # 1. 下载并转录
    python ultimate_transcribe.py -u "$url" --model medium

    # 2. 优化字幕
    srt_file=$(ls -t output/transcripts/*.srt | head -1)
    python optimize_srt_glm.py -s "$srt_file" -p optimization

    # 3. 分析视频
    video_file=$(ls -t downloaded_videos/*.mp4 | head -1)
    python analysis/video_understand_gemini.py \
        -video "$video_file" \
        -m knowledge
done
```

### 6.4 最佳实践建议

1. **模型选择策略**
   - 短视频(<5分钟)：small 或 base
   - 中等视频(5-30分钟)：medium（推荐）
   - 长视频(>30分钟)：medium 或分段处理
   - 高精度需求：large

2. **优化模式选择**
   - 技术教程：tech
   - 访谈对话：interview
   - Vlog日常：vlog
   - 通用场景：optimization

3. **批量处理建议**
   - 使用 `--skip-existing` 跳过已处理
   - 分批处理，每批10-20个视频
   - 保存处理报告便于追踪

4. **API使用建议**
   - Gemini优先使用 flash-lite（免费额度高）
   - GLM使用 glm-4-flash（速度快、费用低）
   - 批量时控制并发数避免超限

---

## 7. 输出文件说明

### 7.1 输出目录结构

```
output/
├── ultimate/                 # ultimate_transcribe.py 输出
│   ├── [WHISPER_]视频名.txt
│   ├── [WHISPER_]视频名.json
│   └── [WHISPER_]视频名.srt
│
├── transcripts/              # 字幕文件
│   ├── 视频1.srt
│   ├── 视频1.txt
│   └── 视频2.srt
│
├── optimized_srt/            # 优化后字幕
│   ├── 视频1_optimized.srt
│   ├── 视频1_comparison.json
│   └── 视频1_report.md
│
├── xiaohongshu/              # 小红书视频
│   └── 视频.mp4
│
├── audio/                    # 提取的音频
│   └── 视频.wav
│
└── bot/                      # Bot输出
    └── task_001/
        └── result.md

gemini_analysis/              # Gemini分析结果
├── 作者1/
│   ├── 视频1_20260221_120000.md
│   └── 视频2_20260221_120500.md
└── 作者2/
    └── 视频3_20260221_130000.md
```

### 7.2 文件格式说明

#### SRT字幕格式

```
1
00:00:01,000 --> 00:00:04,000
字幕内容

2
00:00:04,500 --> 00:00:08,000
第二段字幕
```

#### 优化报告格式

生成的报告包含：
- **JSON对比报告**：原始vs优化的详细对比
- **Markdown报告**：人类可读的修改摘要
- **优化后SRT**：直接可用的字幕文件

#### Gemini分析报告

每个分析报告包含：
- **元信息表格**：视频文件、分析时间、使用模型、Token使用
- **结构化分析**：根据模式不同的分析内容
- **质量评估**：信息可靠性、知识价值评级

---

## 8. API配置与费用说明

### 8.1 智谱GLM API

**获取方式：**
1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册并登录
3. 创建API Key

**模型选择：**

| 模型 | 价格 | 速度 | 适用场景 |
|------|------|------|---------|
| glm-4-flash | ¥0.1/千tokens | 最快 | 字幕优化（推荐） |
| glm-4-air | ¥1/千tokens | 快 | 平衡需求 |
| glm-4-plus | ¥5/千tokens | 中等 | 高质量需求 |
| glm-4 | ¥10/千tokens | 较慢 | 最高质量 |

**费用估算：**
- 优化10分钟视频字幕：约1000-2000 tokens
- 使用glm-4-flash：约¥0.1-0.2

### 8.2 Gemini API

**获取方式：**
1. 访问 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 创建项目并获取API Key

**模型配额（免费版）：**

| 模型 | 请求/分钟 | 请求/天 | 说明 |
|------|----------|---------|------|
| flash-lite | 15 | 1000 | 推荐，最多请求 |
| flash | 5 | 100 | 速度与质量平衡 |
| pro | 10 | 100 | 最高质量 |

**费用说明：**
- 免费配额内：完全免费
- 超出配额：按量计费
- flash-lite：最经济的选择

### 8.3 环境变量优先级

```
1. 环境变量（最高优先级）
2. config_api.py 文件
3. 命令行参数 --api-key
```

---

## 9. 常见问题排查

### 9.1 下载问题

**问题：B站视频下载失败**
```
解决方案：
1. 更新Cookie：python platforms/bilibili/update_cookie_now.py
2. 使用--no-check-certificates选项
3. 检查网络连接
```

**问题：小红书视频需要登录**
```
解决方案：
1. 使用MediaCrawler爬取
2. 更新Cookie：python platforms/xiaohongshu/update_xhs_cookie.py
```

### 9.2 Whisper问题

**问题：识别速度太慢**
```
解决方案：
1. 使用更小的模型（small/base）
2. 确保使用GPU（检查CUDA）
3. 降低采样率
```

**问题：识别不准确**
```
解决方案：
1. 使用更大的模型（medium/large）
2. 检查音频质量
3. 尝试指定语言：language="zh"
```

### 9.3 API调用问题

**问题：GLM API调用失败**
```
解决方案：
1. 检查API Key是否正确
2. 确认账户余额
3. 检查网络连接
4. 尝试更换模型
```

**问题：Gemini配额不足**
```
解决方案：
1. 等待配额刷新（每天重置）
2. 使用flash-lite模型（配额最高）
3. 降低并发数
4. 切换到其他模型
```

### 9.4 编码问题

**问题：Windows下中文乱码**
```
解决方案：
项目已自动处理UTF-8编码，如仍有问题：
1. 设置系统编码为UTF-8
2. 使用Windows Terminal而非CMD
3. 确保文件保存为UTF-8格式
```

### 9.5 内存问题

**问题：处理大视频时内存溢出**
```
解决方案：
1. 使用较小的模型
2. 分段处理视频
3. 增加系统交换空间
4. 只处理音频而非视频
```

---

## 10. 进阶功能

### 10.1 Telegram Bot

**功能：通过Telegram机器人处理视频**

```bash
# 启动Bot
cd bot
python video_bot.py
```

**Bot命令：**
- `/start` - 开始使用
- `/help` - 帮助信息
- `/status` - 系统状态
- `/queue` - 查看任务队列
- 发送视频链接 - 开始处理

### 10.2 教授监控系统

**功能：识别小红书上的真实教授账号**

```bash
# 分析MediaCrawler数据
python platforms/xiaohongshu/xhs_professor_monitor_integration.py \
    --analyze-data \
    --data-dir "MediaCrawler/data/xhs"

# 添加监控用户
python platforms/xiaohongshu/xhs_professor_monitor_integration.py \
    --add-user "用户URL" \
    --name "用户名"

# 生成报告
python platforms/xiaohongshu/xhs_professor_monitor_integration.py \
    --report \
    --output "professor_report.md"
```

### 10.3 评论分析

**功能：分析视频评论情感和内容**

```bash
python analysis/comment_analyzer.py \
    --video "视频URL" \
    --platform "bilibili"
```

### 10.4 自动化工作流

**功能：定时自动处理新视频**

```bash
# 运行自动化工作流
python utils/auto_bili_workflow.py \
    --config "config/workflow.json" \
    --schedule "0 */6 * * *"  # 每6小时运行一次
```

---

## 附录

### A. 文件格式对照表

| 格式 | 扩展名 | 用途 | 兼容性 |
|------|--------|------|--------|
| SRT | .srt | 通用字幕 | 所有播放器 |
| ASS | .ass | 高级字幕 | 大部分播放器 |
| VTT | .vtt | Web字幕 | 浏览器 |
| LRC | .lrc | 歌词 | 音乐播放器 |
| TXT | .txt | 纯文本 | 所有设备 |
| JSON | .json | 结构化数据 | 程序处理 |

### B. 性能参考数据

| 视频时长 | Whisper(medium) | GLM优化 | Gemini(flash-lite) |
|---------|-----------------|---------|-------------------|
| 5分钟 | 3-5分钟 | 30-60秒 | 1-2分钟 |
| 10分钟 | 6-10分钟 | 60-90秒 | 2-4分钟 |
| 30分钟 | 18-30分钟 | 2-3分钟 | 4-8分钟 |
| 1小时 | 35-60分钟 | 4-6分钟 | 8-15分钟 |

*注：时间仅供参考，实际时间取决于硬件配置和网络状况*

### C. 相关资源链接

- [Whisper GitHub](https://github.com/openai/whisper)
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [智谱AI开放平台](https://open.bigmodel.cn/)
- [Google AI Studio](https://aistudio.google.com/)
- [MediaCrawler文档](./MediaCrawler/docs/)

### D. 更新日志

**v1.2 (2026-02-21)**
- 新增Gemini 2.5系列模型支持
- 添加知识库型笔记生成模式
- 优化批量处理并发控制
- 修复Windows编码问题

**v1.1 (2025-02-15)**
- 新增batch_process_videos.py
- 7种GLM优化模式
- MediaCrawler集成

**v1.0 (2025-01-01)**
- 初始版本
- 基础视频下载和字幕提取

---

**文档维护：** BiliSub项目组
**反馈渠道：** 提交Issue或Pull Request
