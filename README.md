# BiliSub - 视频字幕下载与 AI 智能处理工具

一个功能强大的视频字幕处理工具链，支持 B站、小红书、YouTube 等主流平台。集成了视频下载、语音识别（Whisper）、字幕优化（智谱GLM）和 AI 视频内容分析（Gemini）功能。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 目录

- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
- [命令行参数](#命令行参数)
- [项目结构](#项目结构)
- [使用示例](#使用示例)
- [性能参考](#性能参考)
- [常见问题](#常见问题)
- [进阶功能](#进阶功能)
- [完整文档](#完整文档)

---

## 核心功能

| 功能 | 说明 | 支持平台 |
|------|------|---------|
| **视频下载** | 流式下载提速 4 倍，支持断点续传 | B站/小红书/YouTube |
| **内置字幕检查** | 优先提取平台内置字幕（秒级完成） | B站/YouTube |
| **OCR 识别** | 识别视频画面中的文字（PaddleOCR） | 所有平台 |
| ** Whisper 识别** | 本地语音识别，5 种模型可选 | 所有平台 |
| **GLM 优化** | 7 种优化模式，修正错别字、添加标点 | - |
| **Gemini 分析** | AI 视频内容理解，生成知识库笔记 | - |
| **批量处理** | 支持 CSV/TXT 文件批量处理 | - |
| **Telegram Bot** | 通过机器人处理视频 | - |

---

## 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/your-repo/biliSub.git
cd biliSub

# 安装基础依赖
pip install -r requirements.txt

# (可选) 安装 OCR 支持
pip install paddleocr opencv-python paddlepaddle
```

### 2. 配置 API 密钥（推荐使用环境变量）

```bash
# Linux/Mac
export ZHIPU_API_KEY='your-zhipu-key'
export GEMINI_API_KEY='your-gemini-key'

# Windows PowerShell
$env:ZHIPU_API_KEY='your-zhipu-key'
$env:GEMINI_API_KEY='your-gemini-key'

# Windows CMD
set ZHIPU_API_KEY=your-zhipu-key
set GEMINI_API_KEY=your-gemini-key
```

也可以创建 `config_api.py` 文件：

```python
API_CONFIG = {
    "zhipu": {
        "api_key": "your_zhipu_api_key",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "temperature": 0.3,
        "top_p": 0.7,
        "max_tokens": 2000
    },
    "gemini": {
        "api_key": "your_gemini_api_key"
    }
}
```

---

## 使用方法

### 方式一：单视频处理（推荐新手）

```bash
# 下载 + Whisper 识别 + GLM 优化（一步完成）
python batch_process_videos.py -u "视频URL" -m medium -p tech
```

### 方式二：分步处理（推荐进阶用户）

```bash
# 步骤1：下载并生成字幕
python ultimate_transcribe.py -u "视频URL" -m medium -f srt

# 步骤2：优化字幕
python optimize_srt_glm.py -s output/transcripts/视频.srt -p tech

# 步骤3：AI 分析（可选）
python analysis/video_understand_gemini.py -video "视频.mp4" -m knowledge
```

### 方式三：批量处理

```bash
# 创建 videos.txt，每行一个 URL
python batch_process_videos.py -i videos.txt -m medium -p tech

# 或使用 CSV 文件
python batch_process_videos.py -i videos.csv -m medium -p tech
```

### 方式四：Gemini AI 视频分析

```bash
# 分析单个视频（生成知识库型笔记）
python analysis/video_understand_gemini.py -video "video.mp4" -m knowledge

# 批量分析目录（自动并发）
python analysis/video_understand_gemini.py -dir "downloaded_videos" -m knowledge
```

### 方式五：字幕摘要生成

```bash
# 批量生成字幕摘要并汇总
python analysis/gemini_subtitle_summary.py "output/transcripts/作者名" -m flash-lite
```

---

## 命令行参数

### ultimate_transcribe.py - 主转录工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u, --url` | 视频链接 | - |
| `--model` | Whisper 模型 | small |
| `--no-ocr` | 禁用 OCR | - |
| `--compare` | 对比所有方案 | - |
| `-f, --format` | 输出格式 | srt |

**Whisper 模型选择**：`tiny` | `base` | `small` | `medium` | `large`

| 模型 | 文件大小 | 内存需求 | 速度 | 精度 | 推荐场景 |
|------|---------|---------|------|------|---------|
| tiny | ~40MB | ~1GB | 最快 | 较低 | 快速测试 |
| base | ~75MB | ~1GB | 快 | 中等 | 短视频 |
| small | ~250MB | ~2GB | 中等 | 良好 | 日常使用 |
| medium | ~770MB | ~5GB | 较慢 | 很好 | **中文推荐** |
| large | ~1550MB | ~10GB | 最慢 | 最佳 | 高精度需求 |

### optimize_srt_glm.py - 字幕优化工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --srt` | SRT 文件路径 | - |
| `-d, --dir` | 批量处理目录 | - |
| `-p, --prompt` | 优化模式 | optimization |
| `-b, --batch-size` | 批处理大小 | 5 |

**优化模式选择**：

| 模式 | 特点 | 适用场景 |
|------|------|---------|
| `optimization` | 平衡模式 | **通用场景（推荐）** |
| `simple` | 快速模式 | 批量处理 |
| `tech` | 技术术语规范 | 技术教程 |
| `interview` | 对话格式处理 | 访谈/对话 |
| `vlog` | 自然口语化 | 生活/Vlog |
| `conservative` | 保守模式 | 高准确性要求 |
| `aggressive` | 深度优化 | 口语严重视频 |

### batch_process_videos.py - 批量处理工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u, --urls` | 一个或多个 URL | - |
| `-i, --input-file` | URL 列表文件（txt/csv） | - |
| `-m, --model` | Whisper 模型 | medium |
| `-p, --prompt` | GLM 优化模式 | optimization |
| `-o, --output` | 报告输出文件 | batch_report.json |

### video_understand_gemini.py - Gemini 视频分析

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-video` | 视频文件路径 | - |
| `-dir` | 视频目录（批量） | - |
| `-m, --mode` | 分析模式 | knowledge |
| `--model` | Gemini 模型 | flash-lite |
| `-j, --jobs` | 并发数 | 自动 |
| `--force` | 强制重新处理 | - |
| `--keep` | 保留上传的文件 | - |

**分析模式选择**：

| 模式 | 输出内容 | 适用场景 |
|------|---------|---------|
| `knowledge` | 知识库型笔记 | **构建第二大脑（推荐）** |
| `summary` | 详细总结 | 内容概览 |
| `brief` | 简洁总结 | 快速了解 |
| `detailed` | 深度分析 | 完整理解 |
| `transcript` | 对话提取 | 访谈整理 |

**Gemini 模型选择**：`flash-lite` | `flash` | `pro`

| 模型 | 请求/分钟 | 请求/天 | 说明 |
|------|----------|---------|------|
| flash-lite | 15 | 1000 | **推荐，免费额度最高** |
| flash | 5 | 100 | 速度与质量平衡 |
| pro | 10 | 100 | 最高质量 |

---

## 项目结构

```
biliSub/
├── 核心工具（根目录）
│   ├── ultimate_transcribe.py      # 主转录工具（推荐）
│   ├── batch_process_videos.py     # 批量处理
│   ├── check_subtitle.py           # 字幕检查
│   ├── optimize_srt_glm.py         # GLM 字幕优化
│   └── srt_prompts.py              # 优化提示词定义
│
├── AI 分析模块 (analysis/)
│   ├── video_understand_gemini.py  # Gemini 视频分析
│   ├── gemini_subtitle_summary.py  # 字幕摘要生成
│   ├── comment_analyzer.py         # 评论分析
│   └── multimodal_gemini.py        # 多模态分析
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
├── 机器人模块 (bot/)
│   ├── video_bot.py                # Telegram 机器人
│   ├── telegram_notifier.py        # 通知机器人
│   └── cookie_manager.py           # Cookie 管理
│
├── 工具集 (utils/)
│   ├── batch_transcribe_local.py   # 本地视频批量转录
│   ├── enhanced_workflow.py        # 增强工作流
│   └── auto_bili_workflow.py       # 自动化工作流
│
├── MediaCrawler/                   # 社交媒体爬虫子模块
│   └── (独立项目，支持多平台爬取)
│
├── 配置
│   ├── config_api.py               # API 密钥配置（需创建）
│   └── requirements.txt            # 依赖清单
│
├── 文档 (docs/)
│   ├── README_FULL.md              # 完整使用指引
│   ├── QUICK_START.md              # 快速开始指南
│   ├── SRT_OPTIMIZATION_GUIDE.md   # 字幕优化指南
│   └── BATCH_PROCESSING_GUIDE.md   # 批量处理指南
│
└── 输出目录
    ├── output/transcripts/         # Whisper 生成的字幕
    ├── output/optimized_srt/       # GLM 优化后的字幕
    ├── output/xiaohongshu/         # 小红书视频
    ├── gemini_analysis/            # Gemini 分析结果
    └── downloaded_videos/          # 下载的视频
```

---

## 使用示例

### 示例 1：处理 B站技术教程

```bash
# 下载 + 识别 + 优化（一步完成）
python batch_process_videos.py \
    -u "https://www.bilibili.com/video/BV1xx411c79H" \
    -m medium \
    -p tech
```

### 示例 2：批量处理课程视频

```bash
# 创建 course.txt，每行一个视频链接
python batch_process_videos.py -i course.txt -m medium -p tech

# 查看处理报告
cat batch_report.md
```

### 示例 3：使用 Gemini 生成知识库笔记

```bash
# 分析单个视频
python analysis/video_understand_gemini.py \
    -video "downloaded/video.mp4" \
    -m knowledge

# 批量分析（自动并发，flash-lite 模型 10 线程）
python analysis/video_understand_gemini.py \
    -dir "downloaded_videos" \
    -m knowledge
```

### 示例 4：检查视频是否有内置字幕

```bash
# 先检查，避免不必要的 Whisper 处理
python check_subtitle.py "视频URL"

# 如果有内置字幕会显示下载链接
# 如果没有再使用 Whisper
```

### 示例 5：本地视频批量转录

```bash
# 处理已下载的视频目录
python utils/batch_transcribe_local.py -i "downloaded_videos" -m medium

# 跳过已存在字幕的视频
python utils/batch_transcribe_local.py -i "videos" --skip-existing
```

### 示例 6：作者视频内容汇总

```bash
# 生成作者所有视频的 AI 汇总报告
python analysis/gemini_subtitle_summary.py \
    "output/transcripts/作者名" \
    -m flash-lite \
    -j 5
```

---

## 性能参考

| 视频时长 | Whisper (medium) | GLM 优化 | Gemini (flash-lite) | 总计 |
|---------|-----------------|---------|---------------------|------|
| 5 分钟 | ~3-5 分钟 | ~40 秒 | ~1 分钟 | ~5-7 分钟 |
| 10 分钟 | ~6-10 分钟 | ~60 秒 | ~2 分钟 | ~9-13 分钟 |
| 30 分钟 | ~18-30 分钟 | ~120 秒 | ~4 分钟 | ~23-37 分钟 |
| 1 小时 | ~35-60 分钟 | ~4-6 分钟 | ~8-15 分钟 | ~50-85 分钟 |

*注：时间仅供参考，实际时间取决于硬件配置和网络状况*

---

## 常见问题

### Q1: Whisper 模型选择建议？

| 场景 | 推荐模型 | 说明 |
|------|---------|------|
| 快速测试 | tiny/base | 速度优先 |
| 日常使用 | small | 平衡选择 |
| 中文内容 | **medium** | 推荐配置 |
| 高精度需求 | large | 最准确 |

### Q2: GLM 优化模式如何选择？

| 视频类型 | 推荐模式 |
|---------|---------|
| 技术教程 | `tech` |
| 访谈对话 | `interview` |
| Vlog 日常 | `vlog` |
| 通用场景 | `optimization` |

### Q3: Gemini 免费配额？

| 模型 | 请求/分钟 | 请求/天 | 推荐 |
|------|----------|---------|------|
| flash-lite | 15 | 1000 | 批量处理 |
| flash | 5 | 100 | 日常使用 |
| pro | 10 | 100 | 高质量需求 |

### Q4: 如何处理长视频？

1. 使用较小的 Whisper 模型（small）
2. 分段处理视频
3. 使用 Gemini 的批量功能（自动跳过已完成）
4. 使用 `--skip-existing` 跳过已处理的视频

### Q5: B站下载失败怎么办？

```bash
# 更新 Cookie
python platforms/bilibili/update_cookie_now.py

# 或使用 MediaCrawler
cd MediaCrawler
python main.py
```

---

## 注意事项

1. **API 费用**：智谱 GLM API 和 Gemini API 调用会产生费用
2. **网络限制**：某些平台可能需要代理访问
3. **内存需求**：medium 模型需要约 5GB 内存
4. **文件大小**：Gemini 最大支持 2GB 视频文件
5. **配额限制**：注意 API 的请求频率限制

---

## 进阶功能

### Telegram Bot

通过 Telegram 机器人处理视频，支持远程操作：

```bash
cd bot
python video_bot.py
```

**Bot 命令：**
- `/start` - 开始使用
- `/help` - 帮助信息
- `/status` - 系统状态
- `/queue` - 查看任务队列

### 教授监控系统

识别小红书上的真实教授账号：

```bash
python platforms/xiaohongshu/xhs_professor_monitor_integration.py \
    --analyze-data \
    --data-dir "MediaCrawler/data/xhs"
```

### MediaCrawler 集成

从 MediaCrawler 数据提取并处理：

```bash
python utils/enhanced_workflow.py --mediacrawler
```

---

## 完整文档

- **[完整使用指引](docs/README_FULL.md)** - 详细的功能说明和参数文档
- **[快速开始指南](docs/QUICK_START.md)** - 新手入门教程
- **[字幕优化指南](docs/SRT_OPTIMIZATION_GUIDE.md)** - 优化模式详解
- **[批量处理指南](docs/BATCH_PROCESSING_GUIDE.md)** - 批量处理教程

---

## 获取 API 密钥

### 智谱 GLM
1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册并登录
3. 创建 API Key
4. 选择 glm-4-flash 模型（速度快、费用低）

### Gemini
1. 访问 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 创建项目并获取 API Key
3. 推荐使用 flash-lite 模型（免费额度高）

---

## 更新日志

### v1.2 (2026-02)
- 新增 `video_understand_gemini.py` - Gemini AI 视频分析
- 新增 `gemini_subtitle_summary.py` - 字幕摘要生成
- 支持 Gemini 2.5 系列模型（flash/flash-lite/pro）
- 知识库型笔记生成模式
- 批量分析支持自动并发
- 模型自动切换（配额不足时）

### v1.1 (2025-02)
- 新增 `batch_process_videos.py` - 一键完成下载+识别+优化
- 7 种 GLM 优化模式
- 批量处理支持 CSV/TXT 文件

### v1.0 (2025-01)
- 初始版本
- B站/小红书视频下载
- Whisper 语音识别
- 基础字幕优化

---

## 许可证

MIT License - 仅供个人学习和研究使用

---

## 相关链接

- [Whisper](https://github.com/openai/whisper) - OpenAI 语音识别
- [智谱AI](https://open.bigmodel.cn/) - GLM API
- [Gemini](https://ai.google.dev/) - Google AI
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载
- [MediaCrawler](MediaCrawler/) - 社交媒体爬虫

---

如有问题或建议，请提交 Issue 或 Pull Request。
