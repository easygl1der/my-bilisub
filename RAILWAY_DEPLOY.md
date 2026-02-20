# Railway 部署指南

## 步骤 1: 准备 GitHub 仓库

1. 把项目推送到 GitHub（如果没有的话）
2. 确保仓库包含：
   - `video_bot.py`
   - `requirements.txt`
   - `railway.json`

## 步骤 2: Railway 部署

### 方式 A: 从 GitHub 部署（推荐）

1. 访问 https://railway.app
2. 登录/注册（建议用 GitHub 登录）
3. 点击 **New Project** → **Deploy from GitHub repo**
4. 选择你的仓库
5. Railway 会自动检测 Python 项目

### 方式 B: 直接部署（不用 GitHub）

1. 访问 https://railway.app/new
2. 选择 **Deploy from CLI**
3. 安装 Railway CLI：
   ```bash
   npm install -g railway
   railway login
   railway init
   railway up
   ```

## 步骤 3: 配置环境变量

在 Railway 项目设置中添加环境变量：

| 变量名 | 值 |
|--------|-----|
| `TELEGRAM_BOT_TOKEN` | `8514628240:AAHYRGBhQvCuNkFq7g-ZmexehOoflTM3KSQ` |
| `TELEGRAM_PROXY_URL` | 留空（Railway 在国外，不需要代理）|

## 步骤 4: 设置启动命令

在 Railway 设置中：
- **Root Directory**: `/`
- **Start Command**: `python video_bot.py`

## 步骤 5: 部署

点击 **Deploy** 按钮，等待构建完成。

---

## 部署后检查

1. 查看 **Logs** 标签，确认 bot 正常启动
2. 去 Telegram 发送 `/start` 测试

## 注意事项

- Railway 免费额度：$5/月，足够个人使用
- 免费版会自动休眠（无流量30分钟后）
- 升级到付费计划可保持 24/7 运行

## 监控

在 Railway 可以看到：
- CPU 使用率
- 内存使用
- 日志输出
- 部署历史
