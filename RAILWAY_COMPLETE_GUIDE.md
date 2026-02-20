# Railway 完整部署指南

## 准备工作

### 1. 获取 Gemini API Key（必需）

1. 访问 https://aistudio.google.com/app/apikey
2. 点击 **Create API Key**
3. 复制生成的 Key（格式: `AIzaSy...`）

---

## 方法一：通过 GitHub 部署（推荐）

### 步骤 1: 创建 GitHub 仓库

```bash
cd D:\桌面\biliSub

# 初始化 git（如果还没有）
git init

# 创建 .gitignore
cat > .gitignore << EOF
config/bot_config.json
output/
bot_tasks/
*.mp4
*.srt
__pycache__/
*.pyc
.venv/
venv/
EOF

# 提交文件
git add railway.json video_bot_lite.py requirements_lite.txt .gitignore
git commit -m "Add lite video bot"

# 推送到 GitHub（先在 GitHub 创建空仓库）
git remote add origin https://github.com/你的用户名/biliSub-lite.git
git branch -M main
git push -u origin main
```

### 步骤 2: 在 Railway 部署

1. **访问** https://railway.app
2. **登录**（建议用 GitHub 账号）
3. 点击 **New Project** → **Deploy from GitHub repo**
4. 选择你刚创建的仓库 `biliSub-lite`
5. 等待 Railway 检测项目

### 步骤 3: 配置环境变量

在项目页面中：

1. 点击 **Settings** 标签
2. 点击 **Variables**
3. 添加以下变量：

| 变量名 | 值 |
|--------|-----|
| `TELEGRAM_BOT_TOKEN` | `8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ` |
| `GEMINI_API_KEY` | `你从 Google 获取的 API Key` |

### 步骤 4: 开始部署

1. 点击 **Deployments** 标签
2. 点击 **New Deployment** → **Deploy Latest**
3. 等待构建（约 2-3 分钟）

### 步骤 5: 验证

1. 查看 **Logs** 标签，看到 `视频分析 Bot 启动...` 说明成功
2. 去 Telegram 找 `@MyVideoAnalysis_bot`
3. 发送 `/start` 测试

---

## 方法二：用 CLI 直接部署（无需 GitHub）

### 步骤 1: 安装 Railway CLI

```bash
# 安装 Node.js（如果没有）
# 下载: https://nodejs.org/

# 安装 Railway CLI
npm install -g railway
```

### 步骤 2: 登录并初始化

```bash
# 登录 Railway
railway login

# 会自动打开浏览器，点击授权

# 初始化项目
cd D:\桌面\biliSub
railway init

# 选择:
# - Create new project
# - 输入项目名: video-bot-lite
```

### 步骤 3: 上传代码

```bash
# 上传文件
railway up

# 添加文件（如果需要）
railway add video_bot_lite.py
railway add requirements_lite.txt
railway add railway.json
railway up
```

### 步骤 4: 设置环境变量

```bash
# 设置 Bot Token
railway variables set TELEGRAM_BOT_TOKEN=8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ

# 设置 Gemini API Key
railway variables set GEMINI_API_KEY=你的Gemini密钥
```

### 步骤 5: 部署

```bash
# 开始部署
railway deploy

# 查看日志
railway logs
```

### 步骤 6: 验证

看到日志显示 `视频分析 Bot 启动...` 后，去 Telegram 测试。

---

## 常见问题

### Q: 构建失败？
**A**: 检查 `requirements_lite.txt` 文件是否存在

### Q: Bot 启动但没反应？
**A**: 检查环境变量是否正确设置，在 Railway 项目 → Variables 查看

### Q: 视频分析失败？
**A**: 检查 `GEMINI_API_KEY` 是否正确

### Q: 免费额度够用吗？
**A**:
- 免费版: $5/月
- 足够个人使用
- 30分钟无活动会休眠

### Q: 如何查看日志？
**A**: Railway 项目 → Deployments → 点击最新的部署 → Logs

---

## 项目结构

```
biliSub/
├── video_bot_lite.py      # 轻量 Bot（Railway 运行这个）
├── requirements_lite.txt  # 轻量依赖（Railway 用这个）
├── railway.json           # Railway 配置
└── .gitignore            # 忽略敏感文件
```

---

## 快速命令参考

```bash
# 查看日志
railway logs

# 查看项目状态
railway status

# 重新部署
railway up

# 打开项目网页
railway open
```

---

## 成功标志

部署成功后，Railway Logs 会显示：

```
🚀 视频分析 Bot 启动...
📁 输出: output/bot
```

然后你就可以在 Telegram 使用 bot 了！
