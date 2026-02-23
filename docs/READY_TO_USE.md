# Bot 使用指南 - 快速开始

## 📋 当前状态

✅ **已完成功能：**
- Bot 框架完整
- B站视频分析（字幕提取 + AI总结）
- 小红书笔记分析（通过 unified_content_analyzer）
- B站首页刷取（自动采集 + AI分析）
- 小红书推荐刷取（自动采集 + AI分析）
- 多种分析模式切换
- 链接自动识别

✅ **测试通过：**
- Bot 配置完整性测试 ✅
- 链接识别测试 ✅
- 小红书采集功能 ✅

---

## 🚀 快速启动

### 方法1：使用启动脚本（推荐）

双击运行 `start_bot.bat`，然后：
1. 选择 Python 解释器：
   - 选择 **[2] 系统 Python** 以支持 AI 分析功能
   - 选择 **[1] Anaconda** 也可以，但可能缺少部分依赖

2. 脚本会自动检查并安装所需依赖

3. Bot 启动后，在 Telegram 中找到 `@MyVideoAnalysis_bot`

### 方法2：命令行启动

```bash
# 使用系统 Python（推荐）
C:\Users\28024\AppData\Local\Microsoft\WindowsApps\python.exe bot\video_summary_bot.py

# 或使用 Anaconda Python
E:\Anaconda\python.exe bot\video_summary_bot.py
```

---

## 📖 使用方法

### 1. 分析视频/笔记

直接发送链接给 Bot：
- B站视频：`https://www.bilibili.com/video/BVxxxxxx`
- 小红书笔记：`https://www.xiaohongshu.com/explore/xxxxxx`

### 2. 刷主页推荐

```
/scrape_bilibili 3 50
# 刷新3次，最多50个视频

/scrape_xiaohongshu 3 50
# 刷新3次，最多50个笔记
```

### 3. 切换分析模式

```
/mode
# 然后选择：
# - 📝 简洁版
# - 📚 知识库版（默认）
# - 📊 详细版
# - 📄 转录版
```

### 4. 其他命令

```
/start - 开始使用
/help - 查看帮助
/stop - 停止当前分析
```

---

## ⚙️ 配置文件

### Bot 配置

文件：`config/telegram_config.json`

```json
{
  "bot_token": "你的Bot_Token",
  "allowed_users": [],
  "proxy_url": null
}
```

### Cookie 配置

文件：`config/cookies.txt`

```
[bilibili]
SESSDATA=你的SESSDATA
bili_jct=你的bili_jct
DedeUserID=你的DedeUserID

[xiaohongshu]
a1=你的a1值
web_session=你的web_session
webId=你的webId
```

### Gemini API 配置

方式1：环境变量
```bash
set GEMINI_API_KEY=你的API_Key
```

方式2：配置文件（需要在 bot/video_summary_bot.py 中添加代码读取）

---

## 📁 输出文件

### B站首页刷取
- CSV：`MediaCrawler/bilibili_subtitles/homepage_YYYY-MM-DD.csv`
- AI报告：`MediaCrawler/bilibili_subtitles/homepage_YYYY-MM-DD_AI总结.md`

### 小红书推荐刷取
- CSV：`output/xiaohongshu_homepage/xiaohongshu_homepage_YYYY-MM-DD.csv`
- AI报告：`output/xiaohongshu_homepage/xiaohongshu_homepage_YYYY-MM-DD_AI报告.md`

---

## 🐛 常见问题

### Q: Bot 不回复消息？
A: 确保 Bot 正在运行（窗口保持打开）

### Q: 提取字幕失败？
A: 检查 B站 Cookie 是否有效，更新 `config/cookies.txt`

### Q: 小红书刷取失败？
A: 检查小红书 Cookie 是否有效，确保网络连接正常

### Q: AI 分析失败？
A: 检查 GEMINI_API_KEY 环境变量是否设置

### Q: 如何获取 Bot Token？
A:
1. 在 Telegram 中找到 @BotFather
2. 发送 /newbot 创建 Bot
3. 复制 Bot Token

---

## 📝 完整文档

详细文档请查看：`docs/BOT_COMPLETE_GUIDE.md`

---

## ✅ 测试验证

运行测试脚本验证功能：

```bash
python test_bot_functionality.py
```

应该看到：
```
✅ Bot文件存在
✅ Bot文件语法正确
✅ 配置文件存在
✅ 依赖脚本存在
✅ Cookie配置正确
✅ 链接识别正常

🎉 所有测试通过！Bot已准备就绪。
```

---

**最后更新**: 2026-02-23
