# BiliSub - B站/小红书视频字幕下载与处理工具

一个功能强大的视频字幕处理工具链，支持 B站、小红书等主流平台。集成了视频下载、语音识别（Whisper）、字幕优化（智谱GLM）和 AI 视频内容分析（Gemini）功能。

## 主要功能

| 功能 | 说明 |
|------|------|
| 视频下载 | 支持 B站、小红书视频下载，流式下载提速 4 倍 |
| 内置字幕检查 | 优先提取平台内置字幕（最快） |
| Whisper 识别 | 本地语音识别，支持 5 种模型 |
| GLM 优化 | 7 种优化模式，修正错别字、添加标点 |
| Gemini 分析 | AI 视频内容理解，生成知识库笔记 |
| 批量处理 | 支持 CSV/TXT 文件批量处理 |

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

### 2. 配置 API 密钥（可选）

创建 `config_api.py` 文件：

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

或使用环境变量：

```bash
# Linux/Mac
export GEMINI_API_KEY='your-key'

# Windows
set GEMINI_API_KEY=your-key
```

## 使用方法

### 方式一：单视频处理（推荐新手）

```bash
# 下载视频 + Whisper 识别 + GLM 优化（一步完成）
python batch_process_videos.py -u "视频URL" -m medium -p tech
```

### 方式二：分步处理（推荐进阶用户）

```bash
# 步骤1：下载并生成字幕
python ultimate_transcribe.py -u "视频URL" -m medium -f srt

# 步骤2：优化字幕
python optimize_srt_glm.py -s output/transcripts/视频.srt -p tech
```

### 方式三：批量处理

```bash
# 创建 videos.txt，每行一个 URL
python batch_process_videos.py -i videos.txt -m medium -p tech
```

### 方式四：Gemini AI 视频分析

```bash
# 分析单个视频（生成知识库型笔记）
python video_understand_gemini.py -video "video.mp4" -m knowledge

# 批量分析目录
python video_understand_gemini.py -dir "downloaded_videos" -m knowledge
```

## 命令行参数

### ultimate_transcribe.py - 主转录工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u, --url` | 视频链接 | - |
| `--model` | Whisper 模型 | small |
| `--no-ocr` | 禁用 OCR | - |
| `--compare` | 对比所有方案 | - |

**Whisper 模型选择**：`tiny` | `base` | `small` | `medium` | `large`

### optimize_srt_glm.py - 字幕优化工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --srt` | SRT 文件路径 | - |
| `-d, --dir` | 批量处理目录 | - |
| `-p, --prompt` | 优化模式 | optimization |
| `-b, --batch-size` | 批处理大小 | 5 |

**优化模式选择**：
- `optimization` - 平衡模式（推荐）
- `simple` - 快速模式
- `tech` - 技术视频
- `interview` - 访谈对话
- `vlog` - 生活类
- `conservative` - 保守模式
- `aggressive` - 深度优化

### batch_process_videos.py - 批量处理工具

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u, --urls` | 一个或多个 URL | - |
| `-i, --input-file` | URL 列表文件 | - |
| `-m, --model` | Whisper 模型 | medium |
| `-p, --prompt` | GLM 优化模式 | optimization |

### video_understand_gemini.py - Gemini 视频分析

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-video` | 视频文件路径 | - |
| `-dir` | 视频目录（批量） | - |
| `-m, --mode` | 分析模式 | summary |
| `--model` | Gemini 模型 | flash-lite |
| `-j, --jobs` | 并发数 | 自动 |
| `--force` | 强制重新处理 | - |

**分析模式选择**：
- `knowledge` - 知识库型笔记（推荐）
- `summary` - 详细总结
- `brief` - 简洁总结
- `detailed` - 深度分析
- `transcript` - 对话提取

**Gemini 模型选择**：`flash-lite` | `flash` | `pro`

## 项目结构

```
biliSub/
├── 核心工具
│   ├── ultimate_transcribe.py      # 主工具（推荐）
│   ├── batch_process_videos.py     # 批量处理
│   ├── check_subtitle.py           # 字幕检查
│   └── optimize_srt_glm.py         # GLM 优化
│
├── AI 分析
│   └── video_understand_gemini.py  # Gemini 视频分析
│
├── 配置
│   ├── config_api.py               # API 密钥配置（需创建）
│   ├── srt_prompts.py              # 优化提示词定义
│   └── requirements.txt            # 依赖清单
│
├── 文档
│   ├── README.md                   # 本文档
│   ├── PROJECT_SUMMARY.md          # 完整项目总结
│   ├── QUICK_START.md              # 快速开始指南
│   ├── SRT_OPTIMIZATION_GUIDE.md   # 字幕优化指南
│   └── BATCH_PROCESSING_GUIDE.md   # 批量处理指南
│
└── 输出目录
    ├── output/transcripts/         # Whisper 生成的字幕
    ├── output/optimized_srt/       # GLM 优化后的字幕
    ├── output/xiaohongshu/         # 小红书视频
    └── gemini_analysis/            # Gemini 分析结果
```

## 完整使用示例

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
python video_understand_gemini.py \
    -video "downloaded/video.mp4" \
    -m knowledge

# 批量分析（自动并发，flash-lite 模型 10 线程）
python video_understand_gemini.py \
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

## 性能参考

| 视频时长 | Whisper (medium) | GLM 优化 | Gemini (flash-lite) |
|---------|-----------------|---------|---------------------|
| 5 分钟 | ~3-5 分钟 | ~40 秒 | ~1 分钟 |
| 10 分钟 | ~6-10 分钟 | ~60 秒 | ~2 分钟 |
| 30 分钟 | ~18-30 分钟 | ~120 秒 | ~4 分钟 |

## 常见问题

### Q1: Whisper 模型选择建议？

- **tiny/base**: 快速测试，精度较低
- **small**: 日常使用，平衡速度和精度
- **medium**: 推荐配置，中文识别效果好
- **large**: 高精度需求，耗时较长

### Q2: GLM 优化模式如何选择？

- **技术教程** → `tech`
- **访谈对话** → `interview`
- **Vlog 日常** → `vlog`
- **通用场景** → `optimization`（默认）

### Q3: Gemini 免费配额？

| 模型 | 请求/分钟 | 请求/天 |
|------|----------|---------|
| flash-lite | 15 | 1000 |
| flash | 5 | 100 |
| pro | 10 | 100 |

### Q4: 如何处理长视频？

1. 使用较小的 Whisper 模型（small）
2. 分段处理视频
3. 使用 Gemini 的批量功能（自动跳过已完成）

## 注意事项

1. **API 费用**：智谱 GLM API 和 Gemini API 调用会产生费用
2. **网络限制**：某些平台可能需要代理访问
3. **内存需求**：medium 模型需要约 2GB 内存
4. **文件大小**： Gemini 最大支持 2GB 视频文件

## 配置文件示例

### config_api.py

```python
API_CONFIG = {
    "zhipu": {
        "api_key": "填入智谱AI的API Key",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "temperature": 0.3,
        "top_p": 0.7,
        "max_tokens": 2000
    },
    "gemini": {
        "api_key": "填入Gemini的API Key"
    }
}
```

## 获取 API 密钥

### 智谱 GLM
1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册并登录
3. 创建 API Key

### Gemini
1. 访问 [Google AI Studio](https://makersuite.google.com/)
2. 创建项目并获取 API Key

## 更新日志

### v1.2 (2026-02)
- 新增 `video_understand_gemini.py` - Gemini AI 视频分析
- 支持知识库型笔记生成
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

## 许可证

MIT License - 仅供个人学习和研究使用

## 相关链接

- [Whisper](https://github.com/openai/whisper) - OpenAI 语音识别
- [智谱AI](https://open.bigmodel.cn/) - GLM API
- [Gemini](https://ai.google.dev/) - Google AI
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载

---

如有问题或建议，请提交 Issue。
