# B站UP主监控系统使用指南

## 简介

这是一个自动化的B站UP主监控系统，可以定时检查指定UP主是否发布了新视频，发现后自动提取字幕、生成AI摘要，并通过Telegram发送通知。

## 功能特点

- ✅ 自动监控多个UP主
- ✅ 定时检查新视频（默认5分钟）
- ✅ 自动提取字幕并生成AI摘要
- ✅ Telegram实时通知
- ✅ 数据库记录所有视频和分析状态
- ✅ 支持systemd服务部署

## 快速开始

### 1. 初始化配置文件

```bash
python bots/bili_upstream_monitor.py --init
```

### 2. 编辑配置文件

打开 `config/bili_monitor.json`，添加要监控的UP主信息：

```json
{
  "creators": [
    {
      "uid": "UP主的UID",
      "name": "UP主名称",
      "category": "分类（如：新闻、知识、娱乐）",
      "enabled": true
    }
  ],
  "monitor": {
    "interval": 300,        // 检查间隔（秒），默认5分钟
    "check_limit": 50,       // 每次最多检查的视频数
    "timeout": 15           // 请求超时（秒）
  },
  "analysis": {
    "auto_analyze": true,    // 是否自动分析
    "model": "flash-lite",   // Gemini模型：flash, flash-lite, pro
    "mode": "knowledge"      // 分析模式：simple, knowledge, detailed
  },
  "notifications": {
    "enabled": true,
    "telegram": {
      "send_summary": true,     // 是否发送AI摘要
      "summary_length": 300      // 摘要长度限制
    }
  }
}
```

### 3. 确保依赖配置正确

- **B站Cookie**: 确保 `config/cookies.txt` 中包含有效的B站Cookie
- **Telegram配置**: 确保 `config/telegram_config.json` 中包含有效的Bot Token和Chat ID
- **Gemini API**: 确保 `config/config_api.py` 中配置了Gemini API密钥

### 4. 运行测试

```bash
# 单次检查
python bots/bili_upstream_monitor.py --once

# 持续监控（测试3次）
python bots/bili_upstream_monitor.py --loop --max-iterations 3
```

## 命令行参数

```bash
python bots/bili_upstream_monitor.py [选项]

选项:
  --init              初始化配置文件
  --config PATH       指定配置文件路径
  --once              运行一次检查
  --loop              持续监控
  --interval SECONDS   检查间隔（秒）
  --max-iterations N  最大迭代次数
```

## 部署方式

### Windows

使用任务计划程序后台运行：

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器：启动时
4. 设置操作：启动程序
   - 程序：`python.exe`
   - 参数：`bots/bili_upstream_monitor.py --loop`
   - 起始于：项目根目录

### Linux/Mac（systemd服务）

1. 复制服务文件：

```bash
sudo cp systemd/bili-monitor.service /etc/systemd/system/
```

2. 编辑服务文件，修改以下内容：

```ini
User=your_username                    # 你的用户名
WorkingDirectory=/path/to/biliSub     # 项目路径
Environment=PATH=/path/to/conda/envs/bilisub/bin  # Conda环境路径
ExecStart=/path/to/conda/envs/bilisub/bin/python bots/bili_upstream_monitor.py --loop
```

3. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start bili-monitor
sudo systemctl enable bili-monitor  # 开机自启
sudo systemctl status bili-monitor  # 查看状态
```

4. 查看日志：

```bash
sudo journalctl -u bili-monitor -f
```

### Linux/Mac（Screen）

```bash
screen -S bili_monitor
python bots/bili_upstream_monitor.py --loop

# Ctrl+A+D 分离会话
# screen -r bili_monitor 重新连接
```

## 文件结构

```
biliSub/
├── bots/
│   └── bili_upstream_monitor.py  # 主监控脚本
├── config/
│   ├── bili_monitor.json          # 监控配置文件
│   ├── cookies.txt                # B站Cookie
│   ├── telegram_config.json       # Telegram配置
│   └── config_api.py             # API密钥配置
├── data/
│   └── second_brain.db           # 数据库
├── output/
│   └── subtitles/               # 字幕和摘要输出目录
└── systemd/
    └── bili-monitor.service      # systemd服务配置
```

## 如何获取UP主的UID

1. 访问UP主的主页：`https://space.bilibili.com/UID`
2. URL中的数字部分就是UID

例如：`https://space.bilibili.com/3546607314274766` 的UID是 `3546607314274766`

## 数据库查询

```bash
# 查看所有已记录的视频
sqlite3 data/second_brain.db "SELECT * FROM videos ORDER BY id DESC LIMIT 10;"

# 查看所有UP主
sqlite3 data/second_brain.db "SELECT * FROM creators;"

# 查看今日视频
sqlite3 data/second_brain.db "SELECT * FROM videos WHERE date(published_at) = date('now');"

# 查看分析状态
sqlite3 data/second_brain.db "SELECT * FROM analysis_status ORDER BY id DESC LIMIT 10;"

# 查看监控日志
sqlite3 data/second_brain.db "SELECT * FROM monitor_logs ORDER BY id DESC LIMIT 20;"
```

## 通知格式

### Telegram通知示例

```
🔔 B站UP主新视频通知

📅 时间: 2026-02-25 14:30

👤 UP主: 卢克文工作室
📂 分类: 新闻
🎬 视频: 国际形势分析_2024-02-25

🔗 观看视频

📝 AI摘要:
视频分析了当前国际形势，主要讨论了...
```

## 故障排查

### 1. Cookie无效

**问题**：无法获取UP主信息或视频列表

**解决**：
- 检查 `config/cookies.txt` 是否包含有效的B站Cookie
- 更新Cookie：登录B站后，从浏览器开发者工具复制Cookie

### 2. Telegram通知失败

**问题**：没有收到Telegram通知

**解决**：
- 检查 `config/telegram_config.json` 中的Bot Token和Chat ID
- 测试Telegram连接：`python bots/bili_upstream_monitor.py --test-telegram`

### 3. AI分析失败

**问题**：视频字幕提取成功，但AI摘要生成失败

**解决**：
- 检查 `config/config_api.py` 中的Gemini API密钥
- 检查API额度是否用完
- 查看错误日志

### 4. 视频重复通知

**问题**：同一视频收到多次通知

**解决**：
- 数据库可能损坏，删除 `data/second_brain.db` 重新开始
- 检查 `video_id` 是否正确

## 高级配置

### 自定义分析提示词

修改 `analysis/subtitle_analyzer.py` 中的 `ANALYSIS_PROMPTS` 字典来自定义分析模式。

### 调整监控频率

修改 `config/bili_monitor.json` 中的 `monitor.interval`：

- 300秒 = 5分钟（默认）
- 600秒 = 10分钟
- 1800秒 = 30分钟

### 批量添加UP主

```json
{
  "creators": [
    {"uid": "UID1", "name": "UP主1", "category": "新闻", "enabled": true},
    {"uid": "UID2", "name": "UP主2", "category": "科技", "enabled": true},
    {"uid": "UID3", "name": "UP主3", "category": "知识", "enabled": false}
  ]
}
```

## 注意事项

1. **API限制**：Gemini API有速率限制，监控间隔建议≥5分钟
2. **磁盘空间**：长期运行会积累大量字幕和摘要文件，建议定期清理
3. **Cookie过期**：B站Cookie会过期，需要定期更新
4. **网络稳定**：确保服务器网络稳定，避免频繁重试

## 许可证

本项目基于现有代码库开发，遵循原项目的许可证。

## 技术支持

如有问题，请检查：
1. 配置文件是否正确
2. 依赖是否安装完整
3. 日志文件中的错误信息
