# Telegram Bot 刷主页功能使用指南

## 功能概述

这个 Telegram Bot 现在支持自动刷B站首页推荐并生成AI分析报告！

## 新增指令

### 1. `/scrape_bilibili` - 刷B站首页推荐

**格式**:
```
/scrape_bilibili [刷新次数] [最大视频数]
```

**示例**:
```
/scrape_bilibili           # 使用默认配置（刷新3次，最多50个视频）
/scrape_bilibili 5         # 刷新5次，最多50个视频
/scrape_bilibili 3 100     # 刷新3次，最多100个视频
```

**功能说明**:
- 自动打开B站首页并多次刷新
- 采集推荐视频信息（BV号、标题、UP主、链接等）
- 提取视频字幕（如果有）
- 使用AI生成分析报告，包括：
  - 推送趋势分析
  - 视频分类总结
  - UP主分析
- 将报告发送到Telegram

**输出内容**:
- 刷新记录总览
- 各批次视频主题分布
- 算法推送趋势分析
- 详细分类总结（按主题分组）
- 每个视频的完整信息和字幕摘要

### 2. `/scrape_xiaohongshu` - 刷小红书推荐

**状态**: 🚧 开发中

## 使用流程

### 步骤1: 启动Bot

```bash
E:\Anaconda\envs\bilisub\python.exe bot\video_summary_bot.py
```

你会看到：
```
============================================================
🤖 视频总结 Bot 启动中...
============================================================

✅ Bot Token: 8457937188:AAGTil6...307mC6Y
✅ Bot 配置完成

============================================================
🔄 Bot 正在运行...
============================================================
```

### 步骤2: 在Telegram中发送指令

打开Telegram，找到你的bot，发送：

```
/scrape_bilibili 3 50
```

### 步骤3: 等待完成

Bot会报告进度：
```
🚀 开始刷B站首页推荐

📊 配置:
  • 刷新次数: 3
  • 最大视频数: 50

⏳ 启动中...
```

然后：
```
📡 正在采集首页推荐...
```

### 步骤4: 查看报告

完成后，bot会发送：
```
✅ B站首页推荐刷取完成！

📊 采集信息:
  • 刷新次数: 3
  • 最大视频数: 50

📝 以下是报告摘要:

# B站首页推荐AI分析报告

**生成时间**: 2026-02-23 13:38:00
**采集视频数**: 26
**刷新批次**: 3

---

## 刷新记录总览
...
```

## 完整功能列表

### 视频分析功能（原有）
- 发送B站视频链接，自动提取字幕并生成AI总结
- 支持多种分析模式：
  - `/mode` - 简洁版（快速总结）
  - `/mode` - 知识库版（结构化笔记）
  - `/mode` - 详细版（全面分析）
  - `/mode` - 转录版（详细转录）

### 刷主页功能（新增）
- `/scrape_bilibili` - 刷B站首页推荐
- `/scrape_xiaohongshu` - 刷小红书推荐（开发中）

### 其他命令
- `/start` - 开始使用
- `/help` - 查看帮助
- `/stop` - 停止当前任务

## 配置要求

### 必需配置

1. **Bot Token** - 在 `config/telegram_config.json` 中配置
```json
{
  "bot_token": "你的Bot_Token"
}
```

2. **B站Cookie** - 在 `config/cookies.txt` 中配置
```ini
[bilibili]
SESSDATA=你的SESSDATA
bili_jct=你的bili_jct
DedeUserID=你的DedeUserID
```

3. **Gemini API Key** - 设置环境变量
```bash
# Windows
set GEMINI_API_KEY=你的API_Key

# Linux/Mac
export GEMINI_API_KEY=你的API_Key
```

### 可选配置

- **代理设置** - 如果需要使用代理
```json
{
  "bot_token": "你的Bot_Token",
  "proxy_url": "http://127.0.0.1:7890"
}
```

## 报告存储位置

生成的完整报告会保存在：
```
MediaCrawler/bilibili_subtitles/homepage_YYYY-MM-DD_AI总结.md
```

例如：
```
MediaCrawler/bilibili_subtitles/homepage_2026-02-23_AI总结.md
```

## 常见问题

### Q: Bot提示"未找到B站Cookie"
**A**: 请检查 `config/cookies.txt` 文件是否正确配置了B站的Cookie

### Q: AI分析失败
**A**: 请确保：
1. GEMINI_API_KEY 环境变量已设置
2. API Key有效且有足够的配额
3. 网络连接正常

### Q: 采集的视频数量少于预期
**A**: 这是正常的，因为：
1. Bot会自动去重，相同BV号只记录一次
2. 每次刷新可能推荐重复的视频
3. B站推荐算法会根据用户习惯调整

### Q: 如何停止正在运行的任务？
**A**: 发送 `/stop` 命令

## 示例输出

### 推送趋势分析示例
```markdown
## 刷新记录总览

| 刷新批次 | 视频数 | 主要主题 |
|----------|--------|----------|
| 第1次    | 9      | 科技（AI、编程、自动化）、科普（哲学、医药、美食） |
| 第2次    | 8      | 科技（AI、编程、模型）、科普（医学、历史/文化） |
| 第3次    | 9      | 科技（AI、芯片、汽车）、科普（生物/生理、文化） |

## 算法推送趋势分析

**1. 主题的收敛与发散：**
- AI/智能体/编程/科技是强烈的持续兴趣点
- 科普的广度增加
- 生活记录与人文关怀的出现
...
```

### 详细分类示例
```markdown
## 科技与AI (7个视频)

### 1. 「Github一周热点103期」超轻量的clawdbot...
- **BV号**: BV1spFxzYE4d
- **UP主**: IT咖啡馆 (UID: 65564239)
- **UP主主页**: https://space.bilibili.com/65564239
- **视频链接**: https://www.bilibili.com/video/BV1spFxzYE4d
- **字幕摘要**: 本期Github一周热点汇总...
- **推荐批次**: 第1次刷新
```

## 技术细节

### 依赖项
- `python-telegram-bot` - Telegram Bot API
- `playwright` - 浏览器自动化
- `bilibili-api` - B站API封装
- `google-generativeai` - Gemini AI
- `httpx` - HTTP客户端
- `beautifulsoup4` - HTML解析

### 架构
```
Telegram Bot
    ↓
调用 ai_bilibili_homepage.py
    ↓
1. 使用 Playwright 刷B站首页
2. 采集视频信息（BV号、标题、UP主等）
3. 提取字幕（使用 bilibili_api）
4. 调用 Gemini AI 生成分析报告
    ↓
将报告发送回Telegram
```

## 未来计划

- [ ] 支持小红书主页刷取
- [ ] 支持自定义刷新策略
- [ ] 支持定时自动刷取
- [ ] 支持多账号数据对比
- [ ] 支持导出到Notion/Obsidian等笔记工具

## 更新日志

### 2026-02-23
- ✅ 添加 `/scrape_bilibili` 指令
- ✅ 支持自定义刷新次数和视频数
- ✅ 自动生成AI分析报告
- ✅ 通过Telegram发送结果
- 🚧 小红书刷取功能开发中
