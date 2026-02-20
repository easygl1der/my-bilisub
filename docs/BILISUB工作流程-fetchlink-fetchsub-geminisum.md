# BiliSub 视频字幕 AI 总结工作流程

本文档记录从 B站爬取视频信息、下载字幕、到 AI 生成知识库摘要的完整流程。

---

## 📋 流程概览

```
爬取视频信息 → 下载字幕 → AI 生成摘要 → 输出报告
```

---

## 第一步：爬取 B站 UP 主视频信息

使用 MediaCrawler 爬取指定 UP 主的所有视频信息，生成 CSV 文件。

### 文件位置
```
MediaCrawler/fetch_bilibili_videos.py
```

### 操作指令
```bash
# 在 Colab 中运行（推荐）
python /content/drive/MyDrive/my-projects/my-bilisub/MediaCrawler/fetch_bilibili_videos.py

# 本地运行
cd MediaCrawler
python fetch_bilibili_videos.py
```

### 输出文件
```
MediaCrawler/bilibili_videos_output/{UP主名称}.csv
```

### CSV 文件内容
| 序号 | 标题 | 链接 | BV号 | 时长 | 播放量 | 评论数 | 发布时间 | 字幕状态 |
|:----:|------|------|:----:|:----:|:------:|:------:|:--------:|:--------:|

---

## 第二步：批量下载视频字幕

使用 `batch_subtitle_fetch.py` 从 CSV 文件读取视频列表，批量下载 SRT 字幕。

### 文件位置
```
batch_subtitle_fetch.py
```

### 操作指令
```bash
# Windows
python batch_subtitle_fetch.py "MediaCrawler/bilibili_videos_output/小天fotos.csv"

# 参数说明
# - CSV 文件路径：指定要处理的 UP 主 CSV 文件
```

### 功能说明
- 读取 CSV 文件中的 BV 号
- 调用 B站 API 获取字幕
- 保存为 SRT 格式
- 更新 CSV 中的字幕状态（✅成功 / ❌失败）
- 生成汇总 MD 文件

### 输出文件
```
output/subtitles/{UP主名称}/
├── 视频1_ai-zh.srt
├── 视频2_ai-zh.srt
├── ...
└── {UP主名称}_汇总.md
```

---

## 第三步：AI 生成知识库摘要

使用 Gemini API 对字幕进行深度分析，生成结构化的知识库笔记。

### 文件位置
```
gemini_subtitle_summary.py
```

### 操作指令
```bash
# 基本用法
python gemini_subtitle_summary.py "output/subtitles/{UP主名称}"

# 指定并发数（默认3）
python gemini_subtitle_summary.py "output/subtitles/{UP主名称}" -j 5

# 指定 Gemini 模型
python gemini_subtitle_summary.py "output/subtitles/{UP主名称}" --model flash-lite
# 模型选项：
#   - flash-lite: gemini-2.5-flash-lite (15 RPM, 1000 RPD) 最多请求
#   - flash:     gemini-2.5-flash       (5 RPM, 100 RPD)
#   - pro:       gemini-2.5-pro         (10 RPM, 100 RPD)   质量最高
```

### 环境变量设置
```bash
# 设置 Gemini API Key（必须）
setx GEMINI_API_KEY "你的API Key"
# 或临时设置
set GEMINI_API_KEY="你的API Key"
```

### 功能说明
1. **自动读取视频信息**：从 `{UP主名称}_汇总.md` 读取视频基本信息
2. **并发处理**：多线程同时处理多个字幕，提高效率
3. **知识库型摘要**：基于 knowledge 模式生成结构化笔记
4. **实时进度保存**：每处理完一个视频就更新报告
5. **总报告生成**：生成作者内容分析报告

### AI 摘要内容结构
```
## 📋 视频基本信息
- 核心主题、内容结构

## 📖 视频大意
精炼的书面语言概括

## 🎯 核心观点
三段论形式呈现

## 📊 论点论据结构
主要论点、次要论点及支持论据

## 💎 金句/好词好句
引经据典、故事案例、精辟论据、深刻观点

## 📝 书面文稿
去除口语化冗余的正式文稿

## ⚠️ 内容质量分析
情绪操控检测、信息可靠性评估

### 知识价值评估
新颖性、实用性、深度评分
```

### 输出文件
```
output/subtitles/{UP主名称}_AI总结.md
```

### 报告结构
```
# {UP主名称} 视频内容分析报告

## 作者概述
内容领域、创作风格、目标受众

## 核心主题汇总
主要讨论的主题及观点

## 观点倾向与思维方式
论证风格、独特见解

## 内容特色分析
标题风格、叙述方式、个性化元素

## 代表性内容提炼
高价值视频推荐

## 学习价值评估
新颖性、实用性、深度评分

## 附录: 各视频摘要
### 视频1
## 📹 视频信息
| 项目 | 内容 |
|------|------|
| 序号 | 1 |
| 标题 | xxx |
| 链接 | [xxx](xxx) |
| BV号 | xxx |
| 时长 | xx:xx |
| 播放量 | xxx |
| 评论数 | xxx |

[AI 生成的知识库摘要]
```

---

## 完整流程示例

以 UP 主「小天fotos」为例：

```bash
# 1. 爬取视频信息
python MediaCrawler/fetch_bilibili_videos.py

# 2. 下载字幕
python batch_subtitle_fetch.py "MediaCrawler/bilibili_videos_output/小天fotos.csv"

# 3. AI 生成摘要
python gemini_subtitle_summary.py "output/subtitles/小天fotos" -j 5
```

---

## 文件结构

```
biliSub/
├── MediaCrawler/
│   └── fetch_bilibili_videos.py    # 第一步：爬取视频信息
├── batch_subtitle_fetch.py          # 第二步：下载字幕
├── gemini_subtitle_summary.py       # 第三步：AI 摘要
├── config_api.py                    # API 配置（使用环境变量）
├── output/
│   └── subtitles/
│       ├── 小天fotos/               # 字幕文件夹
│       │   ├── 视频1_ai-zh.srt
│       │   ├── 视频2_ai-zh.srt
│       │   └── 小天fotos_汇总.md    # 字幕下载汇总
│       └── 小天fotos_AI总结.md       # 最终 AI 分析报告
└── BILISUB工作流程.md               # 本文档
```

---

## 注意事项

### API Key 配置
- 所有 API Key 通过环境变量设置，不硬编码到代码中
- Gemini API Key: https://aistudio.google.com/app/apikey

### 并发限制
- gemini-2.5-flash-lite: 15 RPM, 1000 RPD（推荐用于批量处理）
- gemini-2.5-flash: 5 RPM, 100 RPD
- gemini-2.5-pro: 10 RPM, 100 RPD

### 常见问题
1. **403 API Key leaked**: API Key 被标记为泄露，需要重新生成
2. **字幕下载失败**: 部分视频可能没有字幕
3. **并发过高**: 降低 `-j` 参数值

---

*最后更新: 2026-02-21*
