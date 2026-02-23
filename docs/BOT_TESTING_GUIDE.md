# Bot启动和测试指南

## 🚀 快速启动Bot

### 步骤1: 获取Telegram Bot Token

1. 在Telegram中搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 命令
3. 按提示设置bot名称
4. 获取Bot Token（格式：`123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`）

### 步骤2: 配置Bot

```bash
# 进入项目目录
cd d:\桌面\biliSub

# 复制配置模板
cp config/bot_config.template.json config/bot_config.json

# 编辑配置文件，填入你的Bot Token
# 使用记事本或VS Code打开 config/bot_config.json
# 将 "YOUR_TELEGRAM_BOT_TOKEN" 替换为你的Token
```

**配置文件示例**：
```json
{
  "bot_token": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
  "allowed_users": [],
  "proxy_url": null
}
```

### 步骤3: 安装依赖

由于conda环境有DLL问题，我们使用系统Python或修复环境：

**选项A: 使用系统Python（推荐）**
```bash
# 使用系统Python安装
python -m pip install python-telegram-bot

# 启动Bot
python start_bot.py
```

**选项B: 修复conda环境**
```bash
# 激活环境
conda activate bilisub

# 重新安装pip
conda install pip --force-reinstall

# 安装依赖
pip install python-telegram-bot

# 启动Bot
python start_bot.py
```

**选项C: 创建新环境**
```bash
# 创建新环境
conda create -n bilibot python=3.10 -y
conda activate bilibot

# 安装依赖
pip install python-telegram-bot

# 启动Bot
python start_bot.py
```

### 步骤4: 测试Bot

启动成功后，在Telegram中：

1. 找到你的Bot
2. 发送 `/start` 命令
3. 应该看到欢迎消息

## 🧪 测试命令

### 基础命令测试

```
/start - 查看欢迎消息
/help - 查看帮助信息
```

### 分析功能测试

```
/analyze https://space.bilibili.com/3546607314274766
```

**预期流程**：
1. Bot检测到B站平台
2. 发送"开始分析"消息
3. 等待处理完成
4. 发送结果

### 直接发送链接测试

直接发送任意链接：
```
https://space.bilibili.com/3546607314274766
```

Bot应该自动检测平台并开始分析。

## 🐛 常见问题

### 问题1: Bot无响应

**检查**：
- Bot Token是否正确
- Bot是否正在运行
- 网络连接是否正常

**解决**：
```bash
# 测试Bot Token
curl https://api.telegram.org/bot<TOKEN>/getMe

# 检查Bot是否运行
# 查看终端输出
```

### 问题2: ModuleNotFoundError

**错误**：
```
ModuleNotFoundError: No module named 'telegram'
```

**解决**：
```bash
pip install python-telegram-bot
```

### 问题3: 配置文件未找到

**错误**：
```
未配置 Bot Token
```

**解决**：
```bash
# 确保配置文件存在
ls config/bot_config.json

# 查看文件内容
cat config/bot_config.json
```

### 问题4: 编码错误

**错误**：
```
UnicodeEncodeError
```

**解决**：
这个问题已经在代码中修复，如果还有问题：
```bash
# 设置环境变量
set PYTHONIOENCODING=utf-8

# 然后启动Bot
python start_bot.py
```

## 📝 完整测试流程

### 1. 启动Bot

```bash
cd d:\桌面\biliSub
python start_bot.py
```

**成功输出**：
```
======================================================================
  多平台内容分析 Bot 启动器
======================================================================

📦 检查依赖...
   ✅ python-telegram-bot

🚀 启动 Bot...
📅 时间: 2026-02-23 xx:xx:xx
```

### 2. 在Telegram中测试

**发送**：`/start`

**预期响应**：
```
👋 你好，[你的名字]！

我是**多平台内容分析 Bot**，可以帮你：

🎯 **支持平台**
• B站 (bilibili.com)
• 小红书 (xiaohongshu.com)

🚀 **快速开始**
• 发送任意链接，我自动检测平台
• 或使用命令: /analyze <链接>
```

### 3. 测试分析功能

**发送**：
```
/analyze https://space.bilibili.com/3546607314274766
```

**预期响应**：
```
🔍 检测到: bili - user

⏳ 开始分析，请稍候...
```

## 🎯 快速验证脚本

如果你只想验证Bot代码是否正确，不需要真正启动：

```bash
python -c "from bot.multi_platform_bot import MultiPlatformBot; print('✅ Bot代码正常')"
```

如果输出 `✅ Bot代码正常`，说明代码没有问题。

## 📚 相关文档

- [Bot使用指南](BOT_USAGE_GUIDE.md)
- [Bot集成计划](BOT_INTEGRATION_PLAN.md)
- [最终总结](FINAL_SUMMARY.md)

---

**提示**：Bot需要网络连接到Telegram服务器，确保网络畅通。

**调试**：启动Bot时，终端会显示详细日志，可用于排查问题。
