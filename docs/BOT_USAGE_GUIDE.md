# 多平台内容分析 Bot 使用指南

## 📋 简介

这是一个支持B站和小红书的Telegram Bot，可以自动分析视频和图文内容。

## 🚀 快速开始

### 1. 配置Bot Token

#### 步骤1: 创建Telegram Bot
1. 在Telegram中搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 命令
3. 按提示设置bot名称
4. 获取Bot Token（格式：`123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`）

#### 步骤2: 配置文件
```bash
# 复制模板
cp config/bot_config.template.json config/bot_config.json

# 编辑配置文件
# 填入你的Bot Token
```

**配置文件格式**:
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "allowed_users": [],
  "proxy_url": null
}
```

### 2. 安装依赖

```bash
pip install python-telegram-bot
```

### 3. 配置Gemini API Key

你已经配置了环境变量 `GEMINI_API_KEY`，Bot会自动使用。

### 4. 启动Bot

```bash
# 方法1: 使用启动脚本（推荐）
python start_bot.py

# 方法2: 直接运行
python bot/multi_platform_bot.py
```

## 📱 Bot命令

### 基础命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/start` | 开始使用Bot | `/start` |
| `/help` | 查看帮助信息 | `/help` |
| `/analyze` | 自动检测平台并分析 | `/analyze https://...` |
| `/bili` | B站专用分析 | `/bili https://bilibili.com/...` |
| `/xhs` | 小红书专用分析 | `/xhs https://xiaohongshu.com/...` |

### 使用场景

#### 场景1: 分析B站用户主页
```
用户: /analyze https://space.bilibili.com/3546607314274766
Bot: 🔍 检测到: bili - user
     ⏳ 开始分析，请稍候...
     ✅ 分析完成！
```

#### 场景2: 分析小红书图文
```
用户: /analyze https://www.xiaohongshu.com/user/profile/12345
Bot: 🔍 检测到: xhs - user
     ⏳ 开始分析，请稍候...
     ✅ 分析完成！
```

#### 场景3: 直接发送链接
```
用户: https://space.bilibili.com/3546607314274766
Bot: [自动检测并分析]
```

## 🎯 支持的内容

### B站 (bilibili.com)
- ✅ 用户主页 - 批量分析多个视频
- ✅ 单个视频 - 分析单个视频
- ✅ 字幕提取 + AI分析

### 小红书 (xiaohongshu.com)
- ✅ 用户主页 - 批量分析视频或图文
- ✅ 视频笔记 - 字幕分析
- ✅ 图文笔记 - 风格检测 + AI分析

## 🔧 高级功能

### 限制处理数量

```
/analyze <链接> --count 10
```

### 选择分析模式

```
/analyze <链接> --mode subtitle  # 字幕分析
/analyze <链接> --mode video     # 视频分析
```

## 📊 输出格式

分析结果会生成：
- Markdown报告（知识库型笔记）
- CSV数据表（视频列表）
- JSON元数据

结果保存在 `output/bot/` 目录。

## 🐛 故障排除

### 问题1: Bot无响应

**检查**:
1. Bot Token是否正确
2. 网络连接是否正常
3. 是否需要代理

**解决**:
```bash
# 测试Bot Token
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### 问题2: 分析失败

**检查**:
1. Gemini API Key是否配置
2. 链接是否有效
3. 是否有足够的权限

**解决**:
```bash
# 检查环境变量
echo $GEMINI_API_KEY

# 测试统一分析入口
python utils/unified_content_analyzer.py --url "测试链接"
```

### 问题3: 依赖缺失

**错误**: `ModuleNotFoundError: No module named 'telegram'`

**解决**:
```bash
pip install python-telegram-bot
```

## 📝 开发说明

### 文件结构

```
bot/
├── multi_platform_bot.py      # 多平台Bot（新建）
├── video_bot.py                # 原始Bot（保留）
├── cookie_manager.py           # Cookie管理

config/
├── bot_config.json             # Bot配置（需创建）
└── bot_config.template.json    # 配置模板

start_bot.py                    # 快速启动脚本
```

### 扩展Bot

如需添加新平台支持：

1. 在 `detect_platform_and_type()` 添加检测逻辑
2. 在 `UnifiedAnalyzerCaller` 添加处理逻辑
3. 更新帮助信息

## 🔐 安全建议

1. **不要提交配置文件**
   - 将 `config/bot_config.json` 添加到 `.gitignore`

2. **限制用户访问**（可选）
   ```json
   {
     "allowed_users": [123456789, 987654321]
   }
   ```

3. **使用代理**（如需要）
   ```json
   {
     "proxy_url": "http://proxy.example.com:8080"
   }
   ```

## 📚 相关文档

- [统一分析入口](../utils/unified_content_analyzer.py)
- [P0使用指南](P0_IMPLEMENTATION_GUIDE.md)
- [Bot集成计划](BOT_INTEGRATION_PLAN.md)

---

**创建时间**: 2026-02-23
**状态**: ✅ 可用
