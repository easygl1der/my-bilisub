# BiliSub 文件结构说明

## 概述

BiliSub 是一个多平台视频/图文内容AI分析工具，支持 **B站** 和 **小红书**。

### 6大核心功能

1. **视频/图文内容获取**
   - B站视频：字幕提取、视频下载
   - 小红书视频：字幕提取、视频下载
   - 小红书图文：图片下载
   - 评论获取：小红书评论

2. **AI分析**
   - Gemini API 驱动
   - 多种分析模式（知识库、总结、详细、转录、简单）
   - 学习笔记生成（含时间戳和关键帧）

3. **批量用户分析**
   - 提取用户主页所有内容
   - 分析用户创作风格

4. **自动刷主页**
   - B站推荐流AI分析
   - 小红书推荐流AI分析

5. **Telegram Bot**
   - 远程执行所有功能
   - 实时进度通知

6. **优化功能**
   - 音频直接分析（避免下载视频）
   - 关键帧提取

---

## 目录结构

```
biliSub/
├── README.md                    # 主文档
├── FILE_STRUCTURE.md            # 本文档
├── CLAUDE.md                    # Claude Code 项目说明
├── config_api.py                # API配置（Gemini等）
├── requirements.txt             # Python依赖
│
├── tools/                       # 核心工具脚本
│   ├── ultimate_transcribe.py   # 主字幕提取工具（内置/OCR/Whisper）
│   ├── check_subtitle.py        # 检查内置字幕
│   ├── optimize_srt_glm.py     # 字幕优化（GLM API）
│   ├── srt_prompts.py          # 优化提示词定义
│   ├── download_videos_from_csv.py  # 批量下载视频
│   └── simple_ocr.py           # 简易OCR工具
│
├── platforms/                   # 平台实现
│   ├── base/
│   │   ├── __init__.py
│   │   ├── platform_base.py     # 抽象基类
│   │   ├── browser_launcher.py  # 浏览器启动器
│   │   └── cdp_browser.py      # CDP浏览器管理器
│   ├── bilibili/
│   │   └── cookie_manager.py   # B站Cookie管理
│   └── xiaohongshu/
│       ├── author_fetcher.py    # 用户信息提取
│       ├── image_downloader.py   # 图片下载
│       ├── fetch_xhs_image_notes.py  # 获取用户图文
│       └── fetch_xhs_videos.py      # 获取用户视频
│
├── analysis/                    # AI分析模块（Gemini）
│   ├── video_analyzer.py        # 视频AI分析
│   ├── subtitle_analyzer.py     # 字幕AI总结
│   ├── image_analyzer.py        # 图文AI分析
│   ├── homepage_analyzer.py     # 首页数据分析
│   ├── comment_analyzer.py      # 评论分析
│   ├── xhs_image_analysis.py   # XHS图片分析
│   └── xhs_simple_analysis.py  # XHS简易分析
│
├── workflows/                   # 端到端工作流
│   ├── video_to_notes.py       # 视频→字幕→AI笔记
│   ├── xhs_link_transcriber.py # XHS链接转录
│   ├── ai_bilibili_homepage.py # B站首页工作流
│   ├── ai_xiaohongshu_homepage.py  # XHS首页工作流
│   ├── auto_bili_workflow.py   # B站用户批量分析
│   ├── auto_xhs_image_workflow.py  # XHS图文批量分析
│   ├── auto_xhs_subtitle_workflow.py  # XHS视频批量分析
│   ├── batch_subtitle_fetch.py # 批量字幕获取
│   ├── analyze_downloaded_videos.py  # 分析已下载视频
│   └── batch_process_videos.py # 批量处理视频
│
├── bots/                        # Telegram Bot
│   ├── video_summary_bot.py     # 主Bot（最完整）
│   ├── bili_homepage_bot.py    # B站首页Bot
│   ├── multi_platform_bot.py   # 多平台Bot
│   ├── multi_platform_summary_bot.py  # 多平台总结Bot
│   ├── video_bot.py            # 原始视频Bot
│   ├── simple_bot.py           # 简易Bot
│   ├── run_monitor.py          # 监控运行器
│   ├── telegram_notifier.py     # 通知模块
│   ├── cookie_manager.py        # Bot Cookie管理
│   └── handlers/              # 处理器目录
│
├── utils/                       # 工具模块
│   ├── unified_content_analyzer.py  # 统一内容分析
│   ├── video_fallback_processor.py  # 视频备用处理
│   ├── enhance_progress.py      # 进度增强
│   ├── enhanced_workflow.py     # 增强工作流
│   ├── batch_transcribe_local.py   # 本地批量转录
│   └── process_csv_workflow.py # CSV处理工作流
│
├── config/                      # 配置文件
│   ├── cookies.txt             # Cookie模板
│   ├── telegram_config.json    # Bot配置
│   ├── bot_config.json         # Bot详细配置
│   └── second_brain.yaml      # Second Brain配置
│
├── tests/                       # 测试文件
│   ├── test_bili_access.py
│   ├── test_bilibili_cookie.py
│   ├── test_gemini_analysis.py
│   ├── test_gemini_simple.py
│   ├── test_bot_config.py
│   ├── test_bot_functionality.py
│   ├── test_bot_simple.py
│   ├── test_bot_full.py
│   ├── test_full_workflow.py
│   ├── test_homepage_simple.py
│   ├── test_author_extraction.py
│   ├── quick_test_xhs_scrape.py
│   └── quick_verification.py
│
├── docs/                        # 文档目录
│   ├── README_FULL.md
│   ├── HOW_TO_USE.md
│   ├── BOT_COMPLETE_GUIDE.md
│   ├── PROJECT_COMPLETION_SUMMARY.md
│   └── ... (更多文档)
│
└── output/                      # 输出目录
    ├── subtitles/              # 提取的字幕
    ├── videos/                 # 下载的视频
    ├── analysis/               # AI分析结果
    ├── learning_notes/          # 学习笔记
    └── ... (更多输出目录)
```

---

## 使用快速指南

### 我要下载视频字幕

```bash
# B站视频
python tools/ultimate_transcribe.py -u "BILIBILI_VIDEO_URL"

# 小红书视频
python tools/ultimate_transcribe.py -u "XHS_VIDEO_URL"

# 批量从CSV下载
python tools/download_videos_from_csv.py -f videos.csv
```

### 我要检查内置字幕

```bash
python tools/check_subtitle.py "VIDEO_URL"
```

### 我要AI分析视频

```bash
# 直接视频分析
python analysis/video_analyzer.py -v "video.mp4" --mode knowledge

# 字幕总结
python analysis/subtitle_analyzer.py -s "subtitle.srt" --mode detailed

# 图文分析
python analysis/image_analyzer.py -u "XHS_NOTE_URL" --mode knowledge
```

### 我要生成学习笔记（含关键帧）

```bash
python workflows/video_to_notes.py -u "VIDEO_URL" --mode knowledge
```

### 我要分析用户内容

```bash
# 小红书用户图文分析
python workflows/auto_xhs_image_workflow.py -u "XHS_USER_URL"

# 小红书用户视频分析
python workflows/auto_xhs_subtitle_workflow.py -u "XHS_USER_URL"

# B站用户分析
python workflows/auto_bili_workflow.py -u "BILIBILI_USER_URL"
```

### 我要自动刷主页

```bash
# B站首页
python workflows/ai_bilibili_homepage.py --mode full --scrapes 5

# 小红书首页
python workflows/ai_xiaohongshu_homepage.py --scrapes 5
```

### 我要用Telegram Bot

```bash
# 启动主Bot（推荐）
python bots/video_summary_bot.py

# 在Telegram中测试：
# /start - 启动Bot
# 发送视频链接 - 分析视频
# /homepage bilibili - 刷B站首页
# /homepage xiaohongshu - 刷小红书首页
# /mode - 切换分析模式
# /stop - 停止当前任务
```

---

## 分析模式说明

| 模式 | 说明 | 输出 |
|------|------|------|
| `knowledge` | 知识库模式（最全面） | 结构化笔记、核心观点、金句、内容质量分析 |
| `detailed` | 详细分析 | 完整分析、论点结构、证据评估 |
| `summary` | 总结模式 | 概述+核心要点 |
| `transcript` | 转录模式 | 详细对话提取 |
| `simple` | 简单模式 | 快速100字总结 |

---

## 平台支持

### B站 (Bilibili)
- ✅ 视频字幕提取（内置/OCR/Whisper）
- ✅ 视频下载
- ✅ 首页推荐流抓取
- ✅ 用户主页分析
- ✅ Cookie管理

### 小红书 (Xiaohongshu)
- ✅ 视频字幕提取
- ✅ 视频下载
- ✅ 图文图片下载
- ✅ 首页推荐流抓取
- ✅ 用户主页分析
- ✅ 评论获取
- ✅ 作者信息提取

---

## 配置说明

### API配置
编辑 `config_api.py`：
```python
# Gemini API密钥
GEMINI_API_KEY = "your-gemini-api-key"

# GLM API密钥（可选，用于字幕优化）
GLM_API_KEY = "your-glm-api-key"
```

### Bot配置
编辑 `config/telegram_config.json`：
```json
{
    "bot_token": "your-telegram-bot-token",
    "chat_id": "your-telegram-chat-id"
}
```

### Cookie配置
编辑 `config/cookies.txt`：
```ini
[bilibili]
SESSDATA=your-sessdata
bili_jct=your-bili-jct
DedeUserID=your-dedeuserid

[xiaohongshu]
xsec_token=your-xsec-token
a1=your-a1
webId=your-webid
```

---

## 输出目录说明

| 目录 | 内容 |
|------|------|
| `output/subtitles/` | 提取的字幕文件（SRT/VTT/ASS等） |
| `output/videos/` | 下载的视频文件 |
| `output/analysis/` | AI分析结果（Markdown） |
| `output/learning_notes/` | 学习笔记（含关键帧） |
| `bili_comments_output/` | B站评论导出 |
| `bilibili_videos_output/` | B站视频数据导出 |
| `xhs_images/` | 小红书图片下载 |
| `xhs_analysis/` | 小红书分析结果 |

---

## 依赖安装

```bash
pip install -r requirements.txt
```

主要依赖：
- `yt-dlp` - 视频下载和字幕提取
- `openai-whisper` - 语音转录
- `paddleocr` / `rapidocr` - OCR
- `google-generativeai` - Gemini API
- `playwright` - 浏览器自动化
- `python-telegram-bot` - Telegram Bot

---

## 开发说明

### 平台基类
所有平台实现继承自 `platforms/base/platform_base.py`：

```python
from platforms.base import AbstractCrawler

class BilibiliCrawler(AbstractCrawler):
    async def start(self):
        # 实现启动逻辑
        pass
```

### CDP浏览器
使用CDP模式连接现有浏览器：

```python
from platforms.base import CDPBrowserManager
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        cdp = CDPBrowserManager()
        context = await cdp.launch_and_connect(p)
        # 使用浏览器...
        await cdp.cleanup()
```

---

## 故障排除

### 问题：Cookie失效
解决：更新 `config/cookies.txt` 中的cookie值

### 问题：Whisper转录慢
解决：使用较小的模型（`-m tiny` 或 `-m base`）

### 问题：Bot无法启动
解决：检查 `config/telegram_config.json` 中的token和chat_id

### 问题：CDP连接失败
解决：关闭Chrome浏览器或指定不同的debug端口

---

## 更新日志

### v2.0 (当前)
- 重构目录结构
- 移植MediaCrawler基础框架
- 统一文件组织
- 添加CDP浏览器支持

---

## 许可证

本项目仅供学习和研究使用，请遵守目标平台的使用条款。
