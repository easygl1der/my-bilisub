# 🎓 如何使用 - 从零开始

## 📋 快速导航

根据你的情况选择：
- [情况1：我刚用MediaCrawler爬取了数据](#情况1我刚用mediacrawler爬取了数据)
- [情况2：我有几个视频链接想处理](#情况2我有几个视频链接想处理)
- [情况3：我有一个CSV文件](#情况3我有一个csv文件)

---

## 情况1：我刚用MediaCrawler爬取了数据

### 第一步：确认数据位置

确保你的MediaCrawler数据在这里：
```
D:\桌面\biliSub\MediaCrawler\data\xhs\xhs_notes_*.csv
```

检查方法：
```bash
ls MediaCrawler/data/xhs/*.csv
```

### 第二步：进入biliSub目录

```bash
cd D:\桌面\biliSub
```

### 第三步：一条命令处理

```bash
python enhanced_workflow.py --mediacrawler
```

等待完成，你会看到：
```
✅ 提取到 X 个视频链接
✅ 处理完成!
✅ 生成报告
```

### 第四步：查看结果

```bash
# 查看处理报告
cat *workflow_report.md

# 查看优化后的字幕
ls output/optimized_srt/
```

**就这么简单！** ✅

---

## 情况2：我有几个视频链接想处理

### 方法A：单个视频

```bash
cd D:\桌面\biliSub

python batch_process_videos.py -u "你的视频URL"
```

**示例**：
```bash
python batch_process_videos.py -u "https://www.bilibili.com/video/BV1uH4y1H7JN/"
```

### 方法B：多个视频（一次处理）

```bash
python batch_process_videos.py -u \
    "https://www.bilibili.com/video/BV1xx1/" \
    "https://www.bilibili.com/video/BV1xx2/" \
    "https://www.bilibili.com/video/BV1xx3/"
```

### 方法C：创建URL列表文件

1. 创建一个文本文件 `my_videos.txt`：
```
https://www.bilibili.com/video/BV1xx1/
https://www.bilibili.com/video/BV1xx2/
https://www.xiaohongshu.com/explore/xxxxx/
```

2. 运行：
```bash
python batch_process_videos.py -i my_videos.txt
```

---

## 情况3：我有一个CSV文件

### 基本使用

```bash
cd D:\桌面\biliSub

python enhanced_workflow.py --csv your_file.csv
```

### 只处理成功的视频

```bash
python enhanced_workflow.py --csv your_file.csv --filter success
```

### 重新处理失败的视频

```bash
python enhanced_workflow.py --csv your_file.csv --filter fail
```

### 只处理前3个（测试）

```bash
python enhanced_workflow.py --csv your_file.csv --limit 3
```

---

## 🎯 推荐配置

### 配置1：快速测试（小模型）

```bash
python batch_process_videos.py -u "url" \
    --model small \
    --prompt simple
```
**速度**：每个视频约30-35秒

### 配置2：标准处理（推荐）

```bash
python batch_process_videos.py -u "url" \
    --model medium \
    --prompt optimization
```
**速度**：每个视频约45秒

### 配置3：技术视频（高质量）

```bash
python batch_process_videos.py -u "url" \
    --model medium \
    --prompt tech
```
**适合**：教程、技术讲解视频

---

## 📂 生成的文件在哪里？

处理完成后，你会得到：

### 1. 字幕文件

```
output/
├── transcripts/
│   └── 视频名.srt                    # Whisper原始字幕
└── optimized_srt/
    ├── 视频名_optimized.srt           # ⭐ 优化后的字幕（用这个）
    ├── 视频名_comparison.json         # 对比数据
    └── 视频名_report.md               # 优化报告
```

### 2. 处理报告

```
*_workflow_report.md      # ⭐ 人类可读的报告
*_workflow_report.json    # 机器可读的数据
*_processed.csv           # 更新状态的CSV（如果从CSV处理）
*_backup_*.csv           # 原文件备份
```

---

## ⚡ 实际例子

### 例子1：处理B站技术教程

```bash
python batch_process_videos.py \
    -u "https://www.bilibili.com/video/BV1uH4y1H7JN/" \
    --model medium \
    --prompt tech
```

**结果**：
- 45秒后完成
- 得到优化后的字幕
- 专业术语已规范化（Cloud Code, SRPK等）

### 例子2：批量处理小红书视频

```bash
# 先导出
python enhanced_workflow.py --mediacrawler --export-crawled xhs_videos.csv

# 检查xhs_videos.csv（用Excel）

# 处理前10个
python enhanced_workflow.py --csv xhs_videos.csv \
    --model medium \
    --prompt optimization \
    --limit 10
```

### 例子3：从CSV重新处理失败的视频

```bash
python enhanced_workflow.py \
    --csv already_processed.csv \
    --filter fail \
    --model medium
```

---

## 🔧 参数说明

### Whisper模型（--model）

| 模型 | 速度 | 准确度 | 内存 | 推荐用途 |
|------|------|--------|------|---------|
| tiny | 最快 | 最低 | ~1GB | 快速测试 |
| base | 快 | 中等 | ~1GB | 日常使用 |
| small | 中等 | 中等 | ~2GB | 平衡选择 |
| **medium** | **适中** | **高** | ~2GB | **⭐ 推荐** |
| large | 慢 | 最高 | ~4GB | 高质量需求 |

### GLM优化模式（--prompt）

| 模式 | 说明 | 推荐场景 |
|------|------|---------|
| optimization | 平衡模式，安全有效 | **⭐ 通用推荐** |
| simple | 快速模式，最小修改 | 批量处理 |
| tech | 技术术语严格规范 | **技术教程** |
| interview | 对话格式处理 | 访谈、对话 |
| vlog | 自然口语化 | Vlog、日常 |

---

## ❓ 常见问题

### Q1: 处理需要多长时间？

**A**：每个视频约45秒
- 1个视频：不到1分钟
- 10个视频：约8分钟
- 100个视频：约75分钟

### Q2: 可以同时处理多个视频吗？

**A**：目前是串行处理（一个接一个），但速度很快。每个视频间隔3秒。

### Q3: 处理失败怎么办？

**A**：
```bash
# 查看哪个失败了
cat *workflow_report.md

# 重新处理失败的
python enhanced_workflow.py --csv your_file.csv --filter fail
```

### Q4: 如何只处理部分视频？

**A**：
```bash
# 方法1：限制数量
python enhanced_workflow.py --csv your_file.csv --limit 5

# 方法2：导出后手动筛选
python enhanced_workflow.py --mediacrawler --export-crawled temp.csv
# 用Excel打开temp.csv，删除不需要的行
python enhanced_workflow.py --csv temp.csv
```

### Q5: 生成的字幕在哪里？

**A**：
```
output/optimized_srt/*_optimized.srt
```

这是优化后的字幕，可以直接使用。

### Q6: 会修改原文件吗？

**A**：
- CSV文件：会自动备份原文件
- 处理后生成新文件：`*_processed.csv`
- 原文件**不会**被修改或删除

### Q7: 如何查看处理进度？

**A**：屏幕会实时显示：
```
# 进度: [3/10]

🎬 处理视频: xxx
✅ Whisper完成 (耗时: 5.2秒)
✅ GLM优化完成 (耗时: 40秒)
```

---

## 💡 最佳实践

### 1. 测试优先

第一次使用时，先测试1-2个视频：
```bash
python enhanced_workflow.py --csv your_file.csv --limit 2
```

确认无误后再处理全部。

### 2. 分批处理

大量视频建议分批处理：
```bash
python enhanced_workflow.py --csv all.csv --limit 10
# 检查结果...
python enhanced_workflow.py --csv all_processed.csv --limit 10
# 继续下一批...
```

### 3. 选择合适的配置

- **测试/预览**：small + simple
- **日常使用**：medium + optimization
- **技术视频**：medium + tech
- **重要内容**：medium + aggressive

### 4. 定期检查

每处理几批后，检查一下报告：
```bash
cat *workflow_report.md
```

确保质量符合预期。

---

## 🎯 总结：最简单的使用流程

### 如果你刚爬取完数据

```bash
cd D:\桌面\biliSub
python enhanced_workflow.py --mediacrawler
# ✅ 完成！
```

### 如果你只有几个链接

```bash
cd D:\桌面\biliSub
python batch_process_videos.py -u "链接1" "链接2" "链接3"
# ✅ 完成！
```

### 如果你有一个CSV文件

```bash
cd D:\桌面\biliSub
python enhanced_workflow.py --csv your_file.csv
# ✅ 完成！
```

---

## 📞 需要帮助？

查看详细文档：
- `README_ENHANCED_WORKFLOW.md` - 完整使用指南
- `ENHANCED_WORKFLOW_GUIDE.md` - 详细参数说明
- `TEST_REPORT.md` - 测试报告

---

**就这么简单！现在就开始使用吧！** 🚀
