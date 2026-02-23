# 多平台内容分析Bot - 快速开始

## 🎯 30秒快速启动

### 前提条件
- ✅ 已有 `config/bot_config.json` 配置文件
- ✅ 已安装Python 3.8+

### 一键启动
```bash
start_multi_platform_bot.bat
```

就这么简单！Bot会自动：
1. 验证配置
2. 安装依赖
3. 启动服务

---

## 📱 在Telegram中使用

### 1. 找到你的Bot
启动脚本会显示Bot用户名，例如：
```
Bot用户名: @MyVideoAnalysis_bot
```

在Telegram中搜索这个用户名并开始对话。

### 2. 基本命令
```
/start - 开始使用
/help  - 查看帮助
```

### 3. 分析内容
直接发送链接即可：
```
https://www.bilibili.com/video/BV1xx411c7mD
https://www.xiaohongshu.com/explore/12345
```

Bot会自动识别平台并开始分析。

---

## 🔧 如果遇到问题

### 问题1: Bot无法启动

**快速检查**：
```bash
python test_multi_platform_bot.py
```

这会检查：
- 配置文件是否正确
- Bot Token是否有效
- Gemini API Key是否配置

### 问题2: python-telegram-bot未安装

**手动安装**：
```bash
pip install python-telegram-bot
```

### 问题3: conda环境DLL错误

**解决方案**：使用系统Python而不是conda

---

## 📋 支持的链接格式

### B站
- 视频: `https://www.bilibili.com/video/BV号`
- 用户: `https://space.bilibili.com/用户ID`

### 小红书
- 笔记: `https://www.xiaohongshu.com/explore/笔记ID`
- 用户: `https://www.xiaohongshu.com/user/profile/用户ID`
- 短链接: `https://xhslink.com/...`

---

## 📂 查看分析结果

分析完成后，报告保存在：

```
output/
├── bilibili/          # B站分析结果
├── xiaohongshu/       # 小红书分析结果
└── learning_notes/    # 知识库笔记
```

每个分析都会生成：
- **Markdown报告**: 详细的分析内容
- **CSV数据表**: 结构化的数据
- **JSON元数据**: 原始数据

---

## 🎨 工作原理

```
发送链接
   ↓
Bot识别平台（B站/小红书）
   ↓
自动选择分析模式
   ↓
调用AI分析（Gemini API）
   ↓
生成报告
   ↓
保存到output/目录
```

### B站视频分析
1. 下载视频字幕
2. Gemini AI分析内容
3. 生成知识库笔记

### 小红书视频分析
1. 下载音频
2. Whisper语音转文字
3. Gemini AI分析内容
4. 生成知识库笔记

### 小红书图文分析
1. 下载图片和文案
2. 自动检测内容风格
3. Gemini AI分析内容
4. 生成风格化报告

---

## 📖 详细文档

- **完整使用指南**: [docs/MULTI_PLATFORM_BOT_GUIDE.md](docs/MULTI_PLATFORM_BOT_GUIDE.md)
- **实现总结**: [docs/BOT_IMPLEMENTATION_SUMMARY.md](docs/BOT_IMPLEMENTATION_SUMMARY.md)
- **项目说明**: [README.md](README.md)

---

## 🆘 获取帮助

### 1. 测试配置
```bash
python test_multi_platform_bot.py
```

### 2. 查看日志
Bot运行时会在控制台显示详细日志，包括：
- 收到的消息
- 识别的平台和类型
- 分析进度
- 错误信息

### 3. 手动测试分析
```bash
python utils/unified_content_analyzer.py --url "测试链接"
```

---

## ✅ 验证清单

启动前确认：
- [ ] `config/bot_config.json` 存在且配置正确
- [ ] 已安装Python 3.8+
- [ ] 网络连接正常

启动后确认：
- [ ] Bot成功连接到Telegram
- [ ] `/start` 命令有响应
- [ ] `/help` 命令显示帮助

测试分析：
- [ ] 发送B站链接能识别
- [ ] 发送小红书链接能识别
- [ ] 分析能正常完成

---

## 🎉 开始使用

```bash
# 就这么简单！
start_multi_platform_bot.bat
```

然后在Telegram中找到你的Bot，发送第一个链接开始分析吧！

---

**提示**: 首次使用建议先测试单个链接，熟悉流程后再批量处理。

**需要帮助?** 查看 [docs/MULTI_PLATFORM_BOT_GUIDE.md](docs/MULTI_PLATFORM_BOT_GUIDE.md) 的详细故障排查指南。
