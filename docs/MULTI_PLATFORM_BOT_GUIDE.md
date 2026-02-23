# 多平台内容分析Bot使用指南

## 🎯 功能概述

多平台内容分析Bot是一个Telegram机器人，支持自动识别和分析以下平台的内容：

- **B站（Bilibili）** - 视频分析
- **小红书（XiaohongShu）** - 视频和图文分析

## 📋 前置要求

### 1. Python环境
- Python 3.8 或更高版本
- 建议使用系统Python（避免conda环境DLL问题）

### 2. 必需的Python包
```bash
pip install python-telegram-bot
```

### 3. 配置文件
在 `config/bot_config.json` 中配置以下信息：

```json
{
  "bot_token": "你的Telegram_Bot_Token",
  "allowed_users": [],
  "proxy_url": null,
  "gemini_api_key": "你的Gemini_API_Key"
}
```

### 4. 获取Bot Token
1. 在Telegram中搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建新Bot
3. 按提示设置Bot名称
4. 保存获得的Token到 `config/bot_config.json`

## 🚀 快速开始

### 方法1：使用批处理脚本（推荐）

```bash
start_multi_platform_bot.bat
```

这个脚本会自动：
1. 验证Bot配置
2. 检查并安装依赖
3. 启动Bot

### 方法2：手动启动

```bash
# 1. 验证配置
python test_multi_platform_bot.py

# 2. 启动Bot
python bot/multi_platform_summary_bot.py
```

## 📖 使用方法

### 基本命令

- `/start` - 开始使用Bot，显示欢迎信息
- `/help` - 查看帮助信息

### 分析内容

直接发送任意平台的链接，Bot会自动：

1. 识别平台（B站/小红书）
2. 识别内容类型（视频/图文）
3. 自动选择合适的分析模式
4. 执行分析并生成报告

### 支持的链接格式

#### B站
- **视频**: `https://www.bilibili.com/video/BV号`
- **用户主页**: `https://space.bilibili.com/用户ID`

#### 小红书
- **笔记**: `https://www.xiaohongshu.com/explore/笔记ID`
- **用户主页**: `https://www.xiaohongshu.com/user/profile/用户ID`
- **短链接**: `https://xhslink.com/...`

## 🔧 工作原理

### URL路由系统

Bot使用智能URL路由器自动识别平台和内容类型：

```
用户发送链接
    ↓
URL路由器分析
    ↓
┌─────────────┬────────────────┬────────────────┐
│  B站视频     │  小红书视频      │  小红书图文     │
│  ↓          │  ↓             │  ↓            │
│  字幕分析    │  字幕转录+分析   │  风格检测+分析  │
│  Gemini API │  Whisper+Gemini │  Gemini API   │
└─────────────┴────────────────┴────────────────┘
    ↓
生成Markdown报告
    ↓
保存到 output/ 目录
```

### 分析模式

#### B站视频分析
1. 下载视频字幕（如有）
2. 使用Gemini API分析字幕内容
3. 生成知识库型分析报告

#### 小红书视频分析
1. 下载视频音频
2. 使用Whisper转录生成字幕
3. 使用Gemini API分析字幕内容
4. 生成知识库型分析报告

#### 小红书图文分析
1. 下载图片和文案
2. 自动检测内容风格（life_vlog、tech_review等）
3. 使用Gemini API分析内容
4. 生成风格化分析报告

## 📂 输出文件

分析完成后，报告会保存在以下位置：

```
output/
├── bilibili/          # B站分析报告
│   ├── summaries/     # Gemini分析结果
│   └── transcripts/   # 字幕文件
├── xiaohongshu/       # 小红书分析报告
│   ├── video_analysis/    # 视频分析结果
│   └── image_analysis/    # 图文分析结果
└── learning_notes/    # 知识库笔记
```

## ⚠️ 常见问题

### 1. Bot无法启动

**问题**: 启动后立即停止或报错

**解决方案**:
```bash
# 检查配置
python test_multi_platform_bot.py

# 重新安装依赖
pip install python-telegram-bot --force-reinstall
```

### 2. Conda环境DLL错误

**问题**: `ImportError: DLL load failed while importing pyexpat`

**解决方案**: 使用系统Python而不是conda环境

### 3. 分析失败

**问题**: Bot显示"分析过程中出现警告"

**可能原因**:
- 网络连接问题
- API配额不足
- 目标内容需要登录

**解决方案**:
- 检查网络连接
- 检查 `config/bot_config.json` 中的API Key
- 查看日志文件获取详细错误信息

### 4. Bot无响应

**问题**: 发送链接后Bot没有反应

**解决方案**:
1. 检查链接格式是否正确
2. 查看Bot控制台是否有错误信息
3. 确认Bot仍在运行（没有崩溃）

## 🔍 故障排查

### 完整的诊断流程

```bash
# 1. 验证配置
python test_multi_platform_bot.py

# 2. 测试Bot连接
python -c "import telegram; print('OK')"

# 3. 查看Bot日志
# Bot运行时的控制台输出包含详细的错误信息

# 4. 手动测试分析功能
python utils/unified_content_analyzer.py --url "测试链接"
```

### 获取帮助

如果问题仍未解决：

1. 检查 `docs/` 目录下的其他文档
2. 查看 `CLAUDE.md` 了解项目结构
3. 运行测试脚本验证各个组件

## 📊 技术架构

### Bot结构

```
bot/multi_platform_summary_bot.py
├── MultiPlatformAnalyzer    # URL分析器
│   └── analyze()           # 识别平台和类型
├── cmd_start()             # /start命令
├── cmd_help()              # /help命令
├── handle_message()        # 消息处理器
├── handle_bilibili_video() # B站视频处理
└── handle_xhs_content()    # 小红书内容处理
```

### 依赖关系

```
multi_platform_summary_bot.py
    ↓ 调用
unified_content_analyzer.py (统一分析入口)
    ↓ 路由到
├── auto_bili_workflow.py         # B站工作流
├── auto_xhs_subtitle_workflow.py # 小红书视频工作流
└── auto_xhs_image_workflow.py    # 小红书图文工作流
```

## 🎨 未来扩展

计划中的功能：

- [ ] 支持更多平台（抖音、快手等）
- [ ] 自定义分析模式
- [ ] 批量分析任务
- [ ] 分析进度实时通知
- [ ] Web界面

## 📝 更新日志

### v1.0.0 (2026-02-23)
- ✅ 支持B站视频分析
- ✅ 支持小红书视频和图文分析
- ✅ 自动平台检测
- ✅ 统一的URL路由
- ✅ 完整的错误处理

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**创建时间**: 2026-02-23
**最后更新**: 2026-02-23
