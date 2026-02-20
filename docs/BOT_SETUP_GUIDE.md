# 视频处理 Bot 部署指南

## 功能概述

一个 Telegram Bot，可以自动处理视频链接，支持：
- 🎙️ 字幕提取 (Whisper)
- ✍️ 字幕优化 (GLM AI)
- 🤖 AI 视频分析 (Gemini)
- 🎯 完整处理流程

## 快速开始

### 步骤 1: 创建 Telegram Bot

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建新 bot
3. 按提示设置 bot 名称
4. 复制获得的 Token (格式: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 步骤 2: 配置

创建 `config/bot_config.json`:

```json
{
  "bot_token": "你的Bot Token",
  "allowed_users": []
}
```

### 步骤 3: 安装依赖

```bash
pip install python-telegram-bot
```

### 步骤 4: 启动 Bot

```bash
python video_bot.py
```

## 部署方案

### 方案 A: 本地运行 (推荐新手)

**适用场景**: 偶尔使用，电脑开着就行

```bash
# 启动 bot
python video_bot.py
```

Bot 运行后，在 Telegram 中给你的 bot 发送消息即可。

---

### 方案 B: 本地 + ngrok (外网访问)

**适用场景**: 在家电脑运行，外网也能访问

1. **下载 ngrok**: https://ngrok.com/download

2. **启动 bot** (保留这个窗口):
```bash
python video_bot.py
```

3. **新开窗口，启动 ngrok**:
```bash
ngrok http 8443
```

4. **复制 ngrok 提供的 https 地址**

---

### 方案 C: macMini 家庭服务器

**适用场景**: 24/7 稳定运行

1. **使用 pm2 保持进程运行**:
```bash
# 安装 pm2
npm install -g pm2

# 启动 bot
pm2 start python --name video-bot -- video_bot.py

# 查看状态
pm2 status

# 查看日志
pm2 logs video-bot

# 开机自启
pm2 startup
pm2 save
```

2. **设置端口转发** (可选，用于外网访问)
   - 路由器设置转发 8443 端口到 macMini

3. **或使用 ngrok**:
```bash
ngrok http 8443
```

---

### 方案 D: Railway 云部署 (免费)

**适用场景**: 云端运行，不占用本地资源

1. **访问 [railway.app](https://railway.app)**

2. **点击 Deploy New Project**

3. **选择 Deploy from GitHub repo**

4. **配置环境变量**:
   - `TELEGRAM_BOT_TOKEN`: 你的 bot token
   - `PYTHON_VERSION`: `3.10`

5. **添加启动命令**:
   - `python video_bot.py`

---

## 使用方法

### 发送视频链接

直接向 bot 发送视频链接:

```
https://www.bilibili.com/video/BV1xx411c7mD/
```

### 选择处理类型

Bot 会返回菜单:

```
┌─────────────────┬─────────────────┐
│  🎙️ 仅字幕提取   │  ✍️ 字幕+优化    │
├─────────────────┼─────────────────┤
│  🤖 AI 视频分析  │  🎯 完整处理     │
├─────────────────┴─────────────────┤
│           ❌ 取消任务              │
└───────────────────────────────────┘
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用 |
| `/help` | 查看帮助 |
| `/status` | 系统状态 |
| `/queue` | 我的任务 |

---

## 配置说明

### 任务队列配置

编辑 `video_bot.py`:

```python
MAX_QUEUE_SIZE = 10        # 最大队列长度
MAX_CONCURRENT_TASKS = 1    # 同时处理的任务数
```

### Whisper 模型选择

在 bot 选择"字幕+优化"或"完整处理"时，默认使用 `medium` 模型。

修改模型需要编辑代码中的 `whisper_model` 参数。

### Gemini API

AI 视频分析需要 Gemini API Key。

在 `config_api.py` 中添加:

```python
API_CONFIG = {
    "gemini": {
        "api_key": "你的Gemini_API_Key"
    }
}
```

获取 API Key: https://makersuite.google.com/app/apikey

---

## 故障排除

### Bot 无响应

1. 检查 bot 是否正在运行
2. 检查 Token 是否正确
3. 查看 bot 窗口的错误信息

### 字幕提取失败

1. 检查视频链接是否有效
2. 检查网络连接
3. 检查 yt-dlp 是否可用: `yt-dlp --version`

### AI 分析失败

1. 检查是否配置了 Gemini API Key
2. 检查 API 配额是否用完

---

## 文件结构

```
biliSub/
├── video_bot.py              # 主 bot 文件
├── config/
│   ├── bot_config.json       # Bot 配置
│   └── bot_config.example.json
├── ultimate_transcribe.py    # 字幕提取
├── optimize_srt_glm.py       # 字幕优化
├── video_understand_gemini.py # AI 分析
├── output/
│   └── bot/                  # Bot 输出目录
│       └── [task_id]/
│           ├── video.mp4
│           ├── subtitle.srt
│           └── analysis.md
└── bot_tasks/                # 任务记录
```

---

## 安全建议

1. **限制用户** (可选): 在 `bot_config.json` 中添加允许的用户 ID
2. **速率限制**: 建议设置 `MAX_QUEUE_SIZE` 防止滥用
3. **定期清理**: 删除 `output/bot/` 下的旧文件

---

## 未来扩展

- [ ] 支持更多平台 (抖音、快手)
- [ ] 支持 Web 界面
- [ ] 支持批量处理
- [ ] 支持自定义 Whisper 模型
- [ ] 支持字幕翻译
