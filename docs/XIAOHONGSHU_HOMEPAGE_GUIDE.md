# 小红书首页刷取功能使用指南

## 🎯 功能概述

`ai_xiaohongshu_homepage.py` 是一个自动化工具，可以帮你：

1. **自动刷小红书推荐页** - 模拟真实用户行为
2. **采集推荐内容** - 获取视频/图文、作者信息、点赞数等
3. **导出CSV数据** - 结构化的数据便于分析
4. **AI智能分析** - 自动生成趋势报告和推荐

## 🚀 快速开始

### 方法1：命令行使用

```bash
# 默认配置（刷新3次，最多50个笔记）
python ai_xiaohongshu_homepage.py

# 自定义配置
python ai_xiaohongshu_homepage.py --refresh-count 5 --max-notes 100 --mode full
```

### 方法2：Bot使用

```bash
# 启动Bot
python bot/video_summary_bot.py

# 在Telegram中
/scrape_xiaohongshu 3 50
```

## 📋 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--refresh-count` | 刷新次数 | 3 |
| `--max-notes` | 最多采集笔记数 | 50 |
| `--mode` | 模式（scrape=仅采集，full=采集+AI） | full |
| `--model` | Gemini模型（flash-lite, flash, pro） | flash-lite |

## 🔧 配置要求

### 1. 安装依赖

```bash
pip install playwright beautifulsoup4 httpx google-generativeai
playwright install chromium
```

### 2. 配置小红书Cookie

**步骤**：
1. 在浏览器中登录小红书（https://www.xiaohongshu.com）
2. 按F12打开开发者工具
3. 切换到"Network"标签
4. 刷新页面，找到任意请求
5. 在"Headers"中找到Cookie
6. 复制Cookie内容到 `config/cookies.txt`

**Cookie内容示例**：
```
a1=xxx; xhs_uid=xxx; webId=xxx; ...
```

### 3. 配置Gemini API（AI分析功能）

```bash
# 设置环境变量
set GEMINI_API_KEY=your_api_key_here

# 或在系统环境变量中设置
```

## 🎮 使用流程

### 命令行模式

```
运行脚本
    ↓
打开浏览器窗口（非无头模式）
    ↓
如果Cookie无效，手动登录小红书
    ↓
自动刷新推荐页（N次）
    ↓
采集推荐内容（视频/图文）
    ↓
导出CSV文件
    ↓
（可选）AI生成趋势报告
    ↓
完成！
```

### Bot模式

```
Telegram发送命令
    ↓
Bot调用后台脚本
    ↓
后台执行采集和分析
    ↓
实时更新状态
    ↓
完成后发送摘要到Telegram
    ↓
下载完整报告（可选）
```

## 📂 输出文件

运行后，文件保存在 `output/xiaohongshu_homepage/` 目录：

### CSV数据文件
```
xiaohongshu_homepage_2026-02-23.csv
```

包含字段：
- 序号
- 标题
- 链接
- 笔记ID
- 作者
- 点赞数
- 类型（video/image）
- 采集时间

### AI分析报告
```
xiaohongshu_homepage_2026-02-23_AI总结.md
```

包含内容：
- 内容概览（视频/图文占比、平均点赞数）
- 热门主题Top 5
- 热门作者Top 5
- 趋势分析
- 值得关注的笔记推荐
- 内容质量评估

## 💡 使用技巧

### 1. 提高采集数量
```bash
# 刷新10次，最多200个笔记
python ai_xiaohongshu_homepage.py --refresh-count 10 --max-notes 200
```

### 2. 仅采集，不分析（更快）
```bash
python ai_xiaohongshu_homepage.py --mode scrape
```

### 3. 使用更强大的AI模型
```bash
python ai_xiaohongshu_homepage.py --mode full --model pro
```

### 4. 定时任务（Windows任务计划程序）
创建批处理文件 `auto_scrape_xhs.bat`:
```batch
@echo off
cd /d "d:\桌面\biliSub"
python ai_xiaohongshu_homepage.py --refresh-count 5 --max-notes 100
```

然后在Windows任务计划程序中设置每天自动运行。

## ⚠️ 常见问题

### 1. 浏览器卡住不动

**原因**：Cookie过期或无效

**解决**：
- 在浏览器窗口中手动登录小红书
- 等待30秒让脚本继续
- 或更新Cookie文件

### 2. 采集到的笔记很少

**原因**：小红书推荐算法调整

**解决**：
- 增加刷新次数 `--refresh-count`
- 先多浏览一些内容，让推荐更丰富
- 尝试不同时间段运行

### 3. AI分析失败

**原因**：Gemini API未配置

**解决**：
```bash
# 检查环境变量
echo %GEMINI_API_KEY%

# 如果为空，设置环境变量
set GEMINI_API_KEY=your_api_key
```

### 4. Bot调用失败

**原因**：脚本路径或依赖问题

**解决**：
```bash
# 手动测试脚本
python ai_xiaohongshu_homepage.py --refresh-count 1 --max-notes 5

# 如果手动运行成功，检查Bot的Python路径
```

## 🔍 验证安装

运行测试脚本：
```bash
python test_xhs_homepage.py
```

这会检查：
- ✅ 脚本文件存在
- ✅ 脚本语法正确
- ✅ Cookie配置正确
- ✅ 输出目录就绪

## 📊 数据分析示例

使用Python分析采集的CSV：

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取CSV
df = pd.read_csv('output/xiaohongshu_homepage/xiaohongshu_homepage_2026-02-23.csv')

# 查看数据
print(df.head())

# 统计类型分布
type_counts = df['类型'].value_counts()
print(type_counts)

# 绘制图表
type_counts.plot(kind='pie')
plt.savefig('type_distribution.png')
```

## 🎉 完整示例

### 命令行 - 完整流程
```bash
# 1. 测试配置
python test_xhs_homepage.py

# 2. 运行采集+AI分析
python ai_xiaohongshu_homepage.py --refresh-count 5 --max-notes 100 --mode full

# 3. 查看结果
# CSV: output/xiaohongshu_homepage/xiaohongshu_homepage_2026-02-23.csv
# AI报告: output/xiaohongshu_homepage/xiaohongshu_homepage_2026-02-23_AI总结.md
```

### Bot - 完整流程
```bash
# 1. 启动Bot
python bot/video_summary_bot.py

# 2. 在Telegram中
/scrape_xiaohongshu 5 100

# 3. 等待完成并查看摘要

# 4. 如果需要，查看完整报告
# 报告路径会在Telegram消息中显示
```

## 📚 相关文档

- [Bot使用指南](MULTI_PLATFORM_BOT_GUIDE.md)
- [小红书集成完成总结](XHS_INTEGRATION_COMPLETE.md)
- [B站首页刷取指南](../README.md)

## 🤝 反馈

如有问题或建议，请：
1. 检查控制台日志
2. 运行测试脚本验证配置
3. 查看相关文档

---

**创建时间**: 2026-02-23
**最后更新**: 2026-02-23
