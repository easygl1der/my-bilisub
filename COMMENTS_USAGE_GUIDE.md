# 评论爬取和分析工具使用指南

## 功能概述

本工具集提供以下功能：

1. **B站评论爬取** - 爬取前500条评论（或全部评论）
2. **小红书评论爬取** - 支持多层回复识别
3. **对话链格式化** - 为AI分析准备数据
4. **Markdown格式化** - 为人工阅读准备数据
5. **Gemini观点提取** - 提取2-3个最有价值的评论观点

---

## 快速开始

### 1. 爬取B站评论

```bash
cd platforms/bilibili
python fetch_bili_comments.py "https://www.bilibili.com/video/BV1UPZtBiEFS" 500
```

输出文件：`bili_comments_output/bili_comments_BV1UPZtBiEFS_20260227_001621.json`

### 2. 格式化评论（对话链 + Markdown）

```bash
# 使用已有的测试脚本
python test_formatter.py

# 或直接使用命令行
python platforms/comments/comment_formatter.py "bili_comments_output/bili_comments_BV1UPZtBiEFS_20260227_001621.json"
```

输出文件：
- `*.conversation.md` - 对话链格式（适合AI分析）
- `*.readable.md` - Markdown可读格式
- `*.ai.json` - AI友好的JSON结构

### 3. 提取观点（使用Gemini）

```bash
# 获取Gemini API Key: https://makersuite.google.com/app/apikey
python test_gemini_extractor.py YOUR_GEMINI_API_KEY
```

输出文件：
- `*.viewpoints.json` - 观点提取结果（JSON格式）
- `*.viewpoints.md` - 观点总结（Markdown格式）

---

## 数据结构说明

### B站评论JSON结构

```json
{
  "video_id": "BV1UPZtBiEFS",
  "total_comments": 62,
  "comments": [
    {
      "comment_id": "评论ID",
      "content": "评论内容",
      "likes": 182,
      "author": "作者名",
      "create_time": 1234567890,
      "replies": [],  // 子评论列表
      "rcount": 0     // 子评论数量
    }
  ]
}
```

### Gemini观点提取结果结构

```json
{
  "viewpoints": [
    {
      "rank": 1,
      "title": "观点标题",
      "summary": "观点摘要（100字以内）",
      "supporting_comment": {
        "author": "作者名",
        "content": "完整评论内容",
        "likes": 182
      },
      "reasoning": "为什么这个观点有价值"
    }
  ],
  "overall_summary": "整体观点总结",
  "sentiment": "positive|neutral|negative",
  "extract_time": "2026-02-27 00:33:24",
  "model": "gemini-2.0-flash-exp"
}
```

---

## 使用场景

### 场景1：生成视频总结材料

```bash
# 1. 爬取评论
cd platforms/bilibili
python fetch_bili_comments.py "视频URL" 500

# 2. 提取观点
cd ../..
python test_gemini_extractor.py YOUR_API_KEY

# 3. 将生成的 *.viewpoints.md 内容复制到视频总结中
```

### 场景2：分析用户反馈

```bash
# 1. 爬取评论
python platforms/bilibili/fetch_bili_comments.py "视频URL" 500

# 2. 生成对话链格式
python platforms/comments/comment_formatter.py "output.json"

# 3. 使用对话链格式手动分析或发送给其他AI工具
```

### 场景3：小红书笔记分析

```bash
# 1. 爬取评论（需要Cookie）
cd platforms/xiaohongshu
# 修改脚本中的cookie变量
python fetch_xhs_comments.py "笔记URL"

# 2. 格式化和提取观点（与B站相同）
```

---

## 已知限制

### B站评论
- 子评论API受限制（`code=-412 request was banned`）
- 只能获取主评论API返回的前3条子评论
- 需要登录Cookie才能获取更多数据

### 小红书评论
- 需要登录Cookie
- DOM结构可能变化，需要定期维护

### Gemini API
- 需要Google API Key
- 有调用频率限制
- 免费版本可能有配额限制

---

## 获取API密钥

### Gemini API Key
1. 访问 https://makersuite.google.com/app/apikey
2. 创建新的API Key
3. 保存密钥并妥善保管
4. 使用 `python test_gemini_extractor.py YOUR_API_KEY` 测试

### 小红书Cookie
1. 登录小红书网页版
2. 打开开发者工具（F12）
3. 复制Cookie值
4. 修改 `platforms/xiaohongshu/fetch_xhs_comments.py` 中的cookie变量

---

## 文件说明

### 核心文件
- `platforms/bilibili/fetch_bili_comments.py` - B站评论爬取
- `platforms/xiaohongshu/fetch_xhs_comments.py` - 小红书评论爬取
- `platforms/comments/comment_formatter.py` - 评论格式化工具
- `platforms/comments/gemini_viewpoint_extractor.py` - Gemini观点提取

### 测试脚本
- `test_formatter.py` - 格式化工具测试
- `test_gemini_extractor.py` - Gemini提取器测试

---

## 故障排除

### 问题1：编码错误
**症状**：`UnicodeEncodeError: 'gbk' codec can't encode character`

**解决**：已修复，所有print语句已移除emoji表情

### 问题2：B站子评论获取失败
**症状**：`code=-412 request was banned`

**解决**：这是B站API限制，暂时只能获取主评论API返回的前3条子评论

### 问题3：Gemini API调用失败
**症状**：`API key not valid` 或 `Quota exceeded`

**解决**：
- 检查API Key是否正确
- 检查是否超出配额限制
- 查看Google Cloud Console中的使用情况

### 问题4：小红书爬取失败
**症状**：无法获取评论数据

**解决**：
- 确认Cookie有效
- 检查URL是否正确
- DOM结构可能变化，需要更新脚本

---

## 技术细节

### 对话链格式特点
- 按点赞数排序（热点优先）
- 包含主评论和所有回复
- 标注回复关系（@用户名）
- AI友好的结构化格式

### 观点提取标准
- 较高点赞数支持
- 内容有实质性和见解
- 代表社区共识或争议点
- 能够丰富视频总结的价值

---

## 许可和免责声明

本工具仅供学习和研究使用。请遵守相关平台的服务条款和API使用政策。
