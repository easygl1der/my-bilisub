# 多平台内容分析 Bot - 完整使用指南

## 📋 功能概述

Bot 支持以下功能：
- ✅ B站视频分析（提取字幕 + AI总结）
- ✅ 小红书笔记分析（AI分析图文内容）
- ✅ 刷B站首页推荐（自动采集 + AI分析）
- ✅ 刷小红书推荐（自动采集 + AI分析）
- ✅ 多种分析模式切换

---

## 🚀 快速开始

### 1. 启动Bot

```bash
python bot/video_summary_bot.py
```

### 2. 在Telegram中使用

1. 找到你的Bot：`@MyVideoAnalysis_bot`
2. 发送 `/start` 开始使用

---

## 📖 命令说明

### 基本命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用Bot |
| `/help` | 查看帮助信息 |
| `/mode` | 切换分析模式 |
| `/stop` | 停止当前分析 |

### 刷主页命令

| 命令 | 说明 | 格式 | 示例 |
|------|------|------|------|
| `/scrape_bilibili` | 刷B站首页推荐 | `/scrape_bilibili [刷新次数] [最大视频数]` | `/scrape_bilibili 3 50` |
| `/scrape_xiaohongshu` | 刷小红书推荐 | `/scrape_xiaohongshu [刷新次数] [最大笔记数]` | `/scrape_xiaohongshu 3 50` |

**默认值**：
- 刷新次数：3次
- 最大视频/笔记数：50个

---

## 📝 分析模式

### 简洁版 (`simple`)
- 快速总结
- 100字内大意
- 核心观点（3-5个要点）
- 值得记录的信息

### 知识库版 (`knowledge`) - 默认
- 结构化笔记
- 适合构建第二大脑
- 包含：视频大意、核心观点、金句、核心内容、质量评估

### 详细版 (`detailed`)
- 全面深入分析
- 包含论据结构
- 情绪操控检测
- 信息源可信度评估

### 转录版 (`transcript`)
- 详细提取对话
- 按时间顺序整理
- 保留完整细节

---

## 🔧 使用示例

### 示例1：分析B站视频

```
你: https://www.bilibili.com/video/BV1xx411c7mD

Bot: 📺 识别到B站视频
     BV号: BV1xx411c7mD
     📝 模式: KNOWLEDGE

     📥 正在提取字幕...

     [提取完成后]

Bot: ✅ 字幕提取成功
     标题: [视频标题]...

     🤖 正在AI分析 (模式: KNOWLEDGE)...

     [AI分析结果]
```

### 示例2：分析小红书笔记

```
你: https://www.xiaohongshu.com/explore/699c16b4000000002801f20a

Bot: 📱 识别到小红书笔记
     ID: 699c16b4000000002801f20a

     ⏳ 正在分析...

Bot: ✅ 小红书笔记分析完成！
     📁 报告已保存到 output/ 目录
```

### 示例3：刷B站首页推荐

```
你: /scrape_bilibili 5 100

Bot: 🚀 开始刷B站首页推荐

     📊 配置:
       • 刷新次数: 5
       • 最大视频数: 100

     📡 正在采集首页推荐...

     [采集和分析完成后]

Bot: ✅ B站首页推荐刷取完成！

     📊 采集信息:
       • 刷新次数: 5
       • 最大视频数: 100

     📝 以下是报告摘要:

     [AI分析报告]

     📁 完整报告已保存到: homepage_2026-02-23_AI总结.md
```

### 示例4：刷小红书推荐

```
你: /scrape_xiaohongshu 3 50

Bot: 🚀 开始刷小红书推荐

     📊 配置:
       • 刷新次数: 3
       • 最大笔记数: 50

     📡 正在采集推荐内容...

     [采集和分析完成后]

Bot: ✅ 小红书推荐刷取完成！

     📊 采集信息:
       • 刷新次数: 3
       • 最大笔记数: 50

     📝 以下是报告摘要:

     [AI分析报告]

     📁 完整报告已保存到: xiaohongshu_homepage_2026-02-23_AI报告.md
```

### 示例5：切换分析模式

```
你: /mode

Bot: ⚙️ 分析模式选择

     当前模式: **知识库版**

     选择模式:

     [📝 简洁版]  [📚 知识库版]
     [📊 详细版]  [📄 转录版]

你: [点击 📝 简洁版]

Bot: ✅ 模式已切换到: **简洁版**

     现在发送视频链接将使用此模式分析。
```

---

## 📁 输出文件

### B站首页刷取
- CSV数据：`MediaCrawler/bilibili_subtitles/homepage_YYYY-MM-DD.csv`
- AI报告：`MediaCrawler/bilibili_subtitles/homepage_YYYY-MM-DD_AI总结.md`

### 小红书推荐刷取
- CSV数据：`output/xiaohongshu_homepage/xiaohongshu_homepage_YYYY-MM-DD.csv`
- AI报告：`output/xiaohongshu_homepage/xiaohongshu_homepage_YYYY-MM-DD_AI报告.md`

### 单个B站视频分析
- 字幕文件：`output/subtitles/[视频标题]_[语言].srt`
- AI分析：直接发送到Telegram

### 单个小红书笔记分析
- 分析报告：`output/` 目录下的相应文件
- 摘要：发送到Telegram

---

## ⚙️ 配置说明

### Bot配置

文件：`config/telegram_config.json`

```json
{
  "bot_token": "你的Bot_Token",
  "allowed_users": [],
  "proxy_url": null
}
```

### Cookie配置

文件：`config/cookies.txt`

**B站Cookie**（用于视频字幕提取）：
```
[bilibili]
SESSDATA=你的SESSDATA
bili_jct=你的bili_jct
DedeUserID=你的DedeUserID
```

**小红书Cookie**（用于推荐页刷取）：
```
[xiaohongshu]
a1=你的a1值
web_session=你的web_session
webId=你的webId
```

### Gemini API配置

**方式1：环境变量**
```bash
set GEMINI_API_KEY=你的API_Key
```

**方式2：配置文件**

文件：`config/bot_config.json`

```json
{
  "bot_token": "你的Bot_Token",
  "gemini_api_key": "你的Gemini_API_Key",
  "allowed_users": [],
  "proxy_url": null
}
```

---

## 🔍 支持的链接格式

### B站
- 视频链接：`https://www.bilibili.com/video/BVxxxxxx`
- 短链接：`https://b23.tv/xxxxx`

### 小红书
- 笔记链接（explore格式）：`https://www.xiaohongshu.com/explore/xxxxxx`
- 笔记链接（discovery格式）：`https://www.xiaohongshu.com/discovery/item/xxxxxx`
- 短链接：`https://xhslink.com/xxxxx`

---

## ❓ 常见问题

### 1. Bot不回复消息

**原因**：Bot未启动

**解决**：
```bash
python bot/video_summary_bot.py
```

### 2. 提取字幕失败

**原因**：
- 视频无字幕
- B站Cookie配置错误
- Cookie已过期

**解决**：
- 检查视频是否有字幕
- 更新 `config/cookies.txt` 中的B站Cookie

### 3. 小红书刷取失败

**原因**：
- Cookie配置错误
- Cookie已过期
- 未登录状态

**解决**：
- 更新 `config/cookies.txt` 中的小红书Cookie
- 确保Cookie有效（可以从浏览器复制）

### 4. AI分析失败

**原因**：
- 未配置Gemini API Key
- API Key无效
- 网络问题

**解决**：
- 配置 `GEMINI_API_KEY` 环境变量
- 或在 `config/bot_config.json` 中设置 `gemini_api_key`
- 检查网络连接

### 5. 报告文件未找到

**原因**：
- AI分析失败
- 文件路径错误
- 脚本执行失败

**解决**：
- 检查控制台日志
- 确认Gemini API Key配置正确
- 确认相关脚本文件存在

---

## 🛠️ 故障排除

### 查看Bot日志

Bot启动后会显示以下信息：
```
======================================================================
🤖 多平台内容分析 Bot 启动中...
======================================================================

✅ Bot Token: 8457937188:AAG...fNj307mC6Y
🎯 支持平台: B站、小红书
✅ Bot 配置完成

======================================================================
🔄 Bot 正在运行...
======================================================================
```

### 测试Bot配置

运行测试脚本：
```bash
python test_bot_functionality.py
```

该脚本会检查：
- Bot文件是否存在
- Bot语法是否正确
- 配置文件是否完整
- 依赖脚本是否存在
- Cookie配置是否正确
- 链接识别是否正常

---

## 📊 功能特性

### 自动化功能
- ✅ 自动识别平台和内容类型
- ✅ 自动提取B站视频字幕
- ✅ 自动采集推荐页内容
- ✅ 自动生成AI分析报告
- ✅ 支持增量更新CSV文件

### 分析功能
- ✅ 多种分析模式
- ✅ 支持知识库型笔记
- ✅ 支持详细分析
- ✅ 支持转录模式
- ✅ AI生成结构化报告

### 交互功能
- ✅ 任务管理
- ✅ 停止分析
- ✅ 模式切换
- ✅ 实时进度通知

---

## 📝 开发信息

### 核心文件

| 文件 | 说明 |
|------|------|
| `bot/video_summary_bot.py` | Bot主程序 |
| `ai_xiaohongshu_homepage.py` | 小红书首页刷取脚本 |
| `ai_bilibili_homepage.py` | B站首页刷取脚本 |
| `utils/unified_content_analyzer.py` | 统一分析入口 |

### 配置文件

| 文件 | 说明 |
|------|------|
| `config/telegram_config.json` | Bot配置 |
| `config/bot_config.json` | Bot和Gemini配置 |
| `config/cookies.txt` | Cookie配置 |

### 测试脚本

| 文件 | 说明 |
|------|------|
| `test_bot_functionality.py` | Bot功能完整性测试 |

---

## 📞 技术支持

如果遇到问题：
1. 查看Bot日志
2. 运行测试脚本：`python test_bot_functionality.py`
3. 检查配置文件
4. 检查Cookie是否过期

---

**最后更新**: 2026-02-23
