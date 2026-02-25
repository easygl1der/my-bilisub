# 自动内容处理 Bot - 使用指南

## 🎯 功能总览

### 支持的平台
| 平台 | 支持内容 | 处理方式 |
|------|---------|---------|
| **B站** | 视频/字幕/笔记/评论 | 下载、字幕提取、学习笔记生成、评论爬取 |
| **小红书** | 视频/图文/笔记/评论 | 下载、图片分析、学习笔记、评论爬取 |
| **YouTube** | 视频/笔记 | 下载、学习笔记 |

## 📝 快速开始

### 1. 配置 Bot

```bash
# 复制配置模板
cp config/bot_config.json.example config/bot_config.json

# 编辑配置文件，填入你的密钥
{
  "bot_token": "123456789:ABCDEF...",  # Telegram Bot Token
  "gemini_api_key": "your_gemini_api_key_here"  # Gemini API Key
}
```

### 2. 启动 Bot

```bash
cd d:\桌面\biliSub
python bots/auto_content_bot.py
```

## 🎛 Bot 命令列表

| 命令 | 功能 | 参数 |
|------|------|------|
| `/start` | 欢迎信息 | - |
| `/help` | 显示帮助 | - |
| `/download <url>` | 下载视频 | `--info-only` 仅获取信息 |
| `/subtitle <url>` | B站字幕分析 | `-m` 模型 |
| `/notes <url>` | 学习笔记生成 | `--keyframes N` 关键帧数<br>`--no-gemini` 禁用AI<br>`-m flash-lite` 模型 |
| `/comments <url>` | 爬取评论 | `-c N` 评论数量 |
| `/auto <url>` | 智能处理 | `--generate-notes` 同时生成笔记<br>`--fetch-comments` 同时爬取评论<br>`-c N` 评论数量 |

## 📋 使用示例

### 基础使用

```bash
# B站视频下载
/download https://www.bilibili.com/video/BV1UPZtBiEFS

# 获取视频信息（不下载）
/download --info-only https://www.bilibili.com/video/BV1UPZtBiEFS
```

### B站字幕分析

```bash
# 默认模型
/subtitle https://www.bilibili.com/video/BV1UPZtBiEFS

# 使用 pro 模型
/subtitle https://www.bilibili.com/video/BV1UPZtBiEFS -m pro
```

### 学习笔记生成

```bash
# 默认配置
/notes https://www.bilibili.com/video/BV1UPZtBiEFS

# 指定12个关键帧
/notes https://www.bilibili.com/video/BV1UPZtBiEFS --keyframes 12

# 禁用AI智能检测（均匀采样）
/notes https://www.bilibili.com/video/BV1UPZtBiEFS --no-gemini

# 使用 flash 模型
/notes https://www.bilibili.com/video/BV1UPZtBiEFS -m flash
```

### 评论爬取

```bash
# 默认50条评论
/comments https://www.bilibili.com/video/BV1UPZtBiEFS

# 爬取100条评论
/comments https://www.bilibili.com/video/BV1UPZtBiEFS -c 100
```

### 智能自动处理

```bash
# 下载 + 爬取评论
/auto https://www.bilibili.com/video/BV1UPZtBiEFS --fetch-comments

# 下载 + 笔记 + 爬取评论
/auto https://www.bilibili.com/video/BV1UPZtBiEFS --generate-notes --fetch-comments

# 自定义配置
/auto https://www.bilibili.com/video/BV1UPZtBiEFS --generate-notes --fetch-comments -c 20
```

## 📂 输出文件说明

处理完成后，文件会保存到以下目录：

```
d:\桌面\biliSub\
├── test_downloads\              # 视频文件
│   ├── 产品君\盘点一周AI大事_2月15日__王炸视频模型.mp4
│   └── ...
├── output\subtitles\            # B站字幕
│   └── 产品君\
│       ├── xxx_ai-zh.srt
│       └── BV1xxx_AI总结.md
├── learning_notes\               # 学习笔记
│   └── 视频标题_学习笔记.md
│       └── assets\              # 关键帧图片
├── bili_comments_output\        # B站评论
│   └── bili_comments_BV1xxx_时间戳.json
├── xhs_images\                  # 小红书图片
│   └── 用户名\标题\
│       ├── xxx.jpg
│       └── content.txt
├── xhs_analysis\                # 小红书分析
│   └── 用户名_标题_时间戳.md
└── xhs_comments_output\        # 小红书评论
    └── xhs_comments_xxx_时间戳.json
    └── xhs_comments_xxx_时间戳.summary.json
└── output\bot\                  # Bot 相关输出
```

## 🎯 特性说明

### 智能自动检测
- 发送任意链接即可，Bot 自动识别平台并调用对应处理
- B站视频 → 下载视频
- 小红书图文 → 图片下载 + AI分析
- 小红书视频 → 下载视频
- YouTube → 下载视频

### 进度反馈
- 实时进度更新
- 开始、完成、失败状态提示
- 支持消息编辑更新进度

### 用户隔离
- 每个用户独立进度跟踪
- 多任务并行处理（未实现）
- 消息 ID 管理

## ⚠️ 注意事项

1. **API 配置**
   - 需要配置 Gemini API Key 才能使用学习笔记功能
   - 需要配置 B站 Cookie 才能爬取评论
   - 需要配置小红书 Cookie 才能爬取评论

2. **依赖安装**
   - pip install python-telegram-bot
   - 所有依赖已在 auto_content_workflow.py 中

3. **性能考虑**
   - 视频下载可能较慢，请耐心等待
   - AI 分析需要网络连接
   - 学习笔记生成需要处理视频，时间较长

4. **资源限制**
   - Telegram Bot Token 有限额调用
   - Gemini API Key 有免费额度限制

## 🚀 启动 Bot

```bash
# 1. 配置密钥
cp config/bot_config.json.example config/bot_config.json
# 编辑配置文件，填入你的密钥

# 2. 启动 Bot
python bots/auto_content_bot.py
```

## 📞 故障排除

### Bot 无法启动
```bash
# 检查 python-telegram-bot 是否安装
pip show python-telegram-bot

# 安装
pip install python-telegram-bot
```

### 进度不更新
- 确保 Bot 有编辑消息的权限
- 检查消息 ID 是否正确匹配

### 任务失败
- 检查 `auto_content_workflow.py` 是否存在
- 手动运行该脚本验证功能
- 检查网络连接

### 输出文件未找到
- 检查当前工作目录
- 检查输出路径是否正确

## 📚 获取帮助

如需帮助，请查看项目 README 或联系开发者。
