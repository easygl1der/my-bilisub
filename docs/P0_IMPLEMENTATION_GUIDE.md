# P0 核心功能使用指南

## 📋 概述

P0阶段实现了多平台内容分析系统的基础功能：
- ✅ B站视频分析（复用现有工作流）
- ✅ 小红书视频/图文爬取（基础功能）
- ✅ 统一分析入口（URL自动路由）

## 🚀 快速开始

### 环境准备

确保你在正确的conda环境中：

```bash
conda activate bilisub
```

### 1. 测试B站工作流（已可用）

```bash
# 进入项目目录
cd d:\桌面\biliSub

# 使用统一入口分析B站用户
python utils/unified_content_analyzer.py --url "https://space.bilibili.com/3546607314274766" --count 5
```

**预期结果**：
- 自动检测为B站平台
- 调用现有的B站工作流
- 完成视频列表爬取、字幕下载、AI分析

### 2. 测试小红书视频爬取

```bash
# 爬取小红书用户视频列表
python utils/fetch_xhs_videos.py --url "小红书用户主页链接" --count 10
```

**注意**：由于MediaCrawler的复杂性，当前版本提供简化功能。完整集成需要额外配置。

**输出**：
- CSV文件：`output/xhs_videos/xhs_videos_{user_id}_{timestamp}.csv`
- Markdown文件：`output/xhs_videos/xhs_videos_{user_id}_{timestamp}.md`

### 3. 测试小红书图文爬取

```bash
# 爬取小红书用户图文笔记
python utils/fetch_xhs_image_notes.py --url "小红书用户主页链接" --count 10
```

**输出**：
- CSV文件：`output/xhs_images/xhs_images_{user_id}_{timestamp}.csv`
- Markdown文件：`output/xhs_images/xhs_images_{user_id}_{timestamp}.md`

### 4. 测试统一入口（自动检测）

```bash
# B站链接
python utils/unified_content_analyzer.py --url "https://space.bilibili.com/3546607314274766"

# 小红书链接（视频）
python utils/unified_content_analyzer.py --url "小红书用户主页链接" --type video

# 小红书链接（图文）
python utils/unified_content_analyzer.py --url "小红书用户主页链接" --type image
```

## 📁 文件结构

### 新建的文件

```
utils/
├── fetch_xhs_videos.py              # 小红书视频爬取工具
├── fetch_xhs_image_notes.py         # 小红书图文爬取工具
└── unified_content_analyzer.py      # 统一分析入口
```

### 复用的文件

```
utils/
└── auto_bili_workflow.py            # B站工作流（已存在）

analysis/
├── gemini_subtitle_summary.py      # 字幕分析（已存在）
└── xhs_image_analysis.py           # 图文分析（已存在）

MediaCrawler/
└── media_platform/xhs/             # 小红书爬虫API（已存在）
```

## 🔧 配置要求

### Cookie配置

**B站**：
- 已有配置：`config/cookies_bilibili_api.txt`
- 无需额外配置

**小红书**：
- 需要创建：`config/cookies.txt`
- 格式：Netscape Cookie File 或 key=value格式

### Gemini API配置

确保 `config_api.py` 中配置了Gemini API Key：

```python
API_CONFIG = {
    'gemini': {
        'api_key': 'your-gemini-api-key'
    }
}
```

## 🎯 当前功能状态

| 功能 | 状态 | 说明 |
|------|------|------|
| B站视频分析 | ✅ 完整 | 复用现有工作流 |
| 小红书视频爬取 | ⚠️  基础 | 可爬取列表，待集成完整分析 |
| 小红书图文爬取 | ⚠️  基础 | 可爬取列表，待集成完整分析 |
| URL自动路由 | ✅ 完整 | 自动检测平台和类型 |
| 统一命令行接口 | ✅ 完整 | 统一的参数格式 |

## 🔍 下一步计划

### P0剩余工作

1. **小红书视频字幕分析工作流** (`utils/auto_xhs_subtitle_workflow.py`)
   - 集成Whisper音频转录
   - 集成Gemini字幕分析
   - 生成知识库型报告

2. **小红书图文分析工作流** (`utils/auto_xhs_image_workflow.py`)
   - 调用 `analysis/xhs_image_analysis.py`
   - 批量处理图文笔记
   - 生成风格化报告

### P1阶段计划

1. 小红书视频直接分析（上传视频到Gemini）
2. 增强命令行工具
3. Bot多平台支持

## 📝 使用示例

### 示例1: 分析B站UP主

```bash
python utils/unified_content_analyzer.py \
    --url "https://space.bilibili.com/3546607314274766" \
    --count 10 \
    --model flash-lite
```

### 示例2: 爬取小红书视频列表

```bash
python utils/fetch_xhs_videos.py \
    --url "https://www.xiaohongshu.com/user/profile/5f3e2c1d2e3a4b5c" \
    --count 20
```

### 示例3: 爬取小红书图文列表

```bash
python utils/fetch_xhs_image_notes.py \
    --url "https://www.xiaohongshu.com/user/profile/5f3e2c1d2e3a4b5c" \
    --count 30
```

## 🐛 已知问题

1. **MediaCrawler集成**
   - 当前提供简化版本
   - 完整集成需要额外配置和测试
   - 建议先使用手动提供CSV的方式

2. **小红书Cookie**
   - 可能需要定期更新
   - 某些功能可能需要登录状态

3. **Whisper转录**
   - 需要安装 `openai-whisper`
   - 转录速度较慢
   - 建议使用GPU加速

## 💡 故障排除

### 问题1: 无法导入MediaCrawler模块

**解决方案**：
```bash
# 确保MediaCrawler子模块已初始化
cd MediaCrawler
pip install -r requirements.txt
```

### 问题2: Cookie无效

**解决方案**：
1. 更新 `config/cookies.txt`
2. 或使用 `--no-cookie` 跳过检查（功能受限）

### 问题3: Gemini API配额不足

**解决方案**：
1. 切换到 `flash-lite` 模型（免费额度更高）
2. 或等待配额重置

## 📚 相关文档

- [完整实施计划](.claude/plans/refactored-pondering-phoenix.md)
- [项目README](README.md)
- [CLAUDE使用指南](CLAUDE.md)

---

**创建时间**: 2026-02-23
**最后更新**: 2026-02-23
