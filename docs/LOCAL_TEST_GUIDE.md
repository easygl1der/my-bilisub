# 本地测试完整指南

## 第一步：安装轻量版依赖

```bash
cd D:\桌面\biliSub
pip install python-telegram-bot google-generativeai yt-dlp requests
```

## 第二步：创建本地配置文件

```bash
# 创建 config 目录（如果还没有）
mkdir config
```

编辑 `config/bot_config.json`：

```json
{
  "bot_token": "8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ",
  "allowed_users": [],
  "proxy_url": "http://127.0.0.1:7890",
  "gemini_api_key": "AIzaSyDH_QflfbjgGguAFLB5GWq6L4E-kfdC6HI"
}
```

## 第三步：启动代理

启动你的 Clash/VPN

## 第四步：运行 Bot

```bash
cd D:\桌面\biliSub
python video_bot_lite.py
```

看到这个说明成功：
```
🚀 视频分析 Bot 启动...
📁 输出: output/bot
🌐 使用代理: http://127.0.0.1:7890
```

## 第五步：在 Telegram 测试

1. 找到 `@MyVideoAnalysis_bot`
2. 发送 `/start`
3. 发送一个视频链接
4. 选择分析模式
5. 等待结果

## 第六步：本地测试成功后，上传到 Railway

本地跑通了，再执行：

```bash
# 设置代理
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

# 登录 Railway
railway login

# 初始化项目
railway init

# 上传代码
railway up

# 设置环境变量
railway variables set TELEGRAM_BOT_TOKEN=8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ
railway variables set GEMINI_API_KEY=AIzaSyDH_QflfbjgGguAFLB5GWq6L4E-kfdC6HI

# 部署
railway deploy
```

---

## 问题排查

### Bot 启动失败
- 检查代理是否开启
- 检查 Token 是否正确

### 视频下载失败
- 检查网络连接
- 检查视频链接是否有效

### AI 分析失败
- 检查 Gemini API Key 是否正确
- 检查 API 配额是否用完

---

## 快速命令

```bash
# 安装依赖
pip install python-telegram-bot google-generativeai yt-dlp requests

# 运行 Bot
python video_bot_lite.py
```
