# Railway 部署完整步骤（从零开始）

## 前提条件
- 已安装 Node.js
- 已安装 Railway CLI: `npm install -g @railway/cli`
- 有代理软件（Clash/VPN）
- 有 Telegram Bot Token
- 有 Gemini API Key

---

## 第一步：登录 Railway

```bash
# 1. 启动你的代理软件（Clash/VPN）

# 2. 设置代理环境变量
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

# 3. 登录 Railway
railway login
```

（会自动打开浏览器，点击授权登录）

---

## 第二步：创建项目

```bash
# 进入项目目录
cd D:\桌面\biliSub

# 初始化项目
railway init
```

按提示操作：
- 选择 workspace
- 输入项目名（如：`video-bot-lite`）

---

## 第三步：上传代码

```bash
# 上传所有文件
railway up
```

等待上传完成（显示 Compressed 100%）

---

## 第四步：设置环境变量

```bash
# 设置 Telegram Bot Token
railway variables set TELEGRAM_BOT_TOKEN=8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ

# 设置 Gemini API Key
railway variables set GEMINI_API_KEY=AIzaSyDH_QflfbjgGguAFLB5GWq6L4E-kfdC6HI
```

---

## 第五步：部署

```bash
# 开始部署
railway deploy
```

等待构建完成（约 2-3 分钟）

---

## 第六步：查看日志

```bash
# 实时查看日志
railway logs
```

看到以下内容说明成功：
```
🚀 视频分析 Bot 启动...
📁 输出: output/bot
```

按 `Ctrl+C` 退出日志查看（Bot 不会停止）

---

## 第七步：测试

1. 打开 Telegram
2. 找到 `@MyVideoAnalysis_bot`
3. 发送 `/start`
4. 发送一个视频链接测试

---

## 常用命令

```bash
# 查看项目状态
railway status

# 查看日志
railway logs

# 重新部署
railway deploy

# 打开项目网页
railway open

# 设置/查看环境变量
railway variables list
```

---

## 如果代理连接失败

尝试 SOCKS5 代理：

```bash
set HTTP_PROXY=socks5://127.0.0.1:7891
set HTTPS_PROXY=socks5://127.0.0.1:7891
```

或者查看你的 Clash 设置确认端口号。

---

## 完整流程（复制粘贴版）

```bash
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
cd D:\桌面\biliSub
railway init
railway up
railway variables set TELEGRAM_BOT_TOKEN=8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ
railway variables set GEMINI_API_KEY=AIzaSyDH_QflfbjgGguAFLB5GWq6L4E-kfdC6HI
railway deploy
railway logs
```
