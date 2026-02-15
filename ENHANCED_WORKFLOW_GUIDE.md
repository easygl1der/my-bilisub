# 增强型工作流使用指南

## 🎯 核心功能

增强型工作流整合了**MediaCrawler数据提取**和**视频批量处理**两大功能，实现完全自动化的端到端处理。

---

## 📊 三种输入模式对比

### 模式1：MediaCrawler直接处理（推荐）

```bash
python enhanced_workflow.py --mediacrawler
```

**工作流程**：
```
MediaCrawler数据
    ↓
自动提取链接
    ↓
创建临时CSV
    ↓
批量处理视频
    ↓
生成报告
```

**优势**：
- ✅ 无需手动准备CSV
- ✅ 直接从爬虫数据提取
- ✅ 完全自动化

**适用场景**：
- 刚用MediaCrawler爬取完数据
- 想要快速批量处理

---

### 模式2：MediaCrawler导出CSV

```bash
python enhanced_workflow.py --mediacrawler --export-crawled my_videos.csv
```

**工作流程**：
```
MediaCrawler数据
    ↓
提取链接
    ↓
保存为CSV文件 ←（你可以查看、编辑）
    ↓
返回（不处理）
```

**后续使用**：
```bash
# 然后可以正常处理这个CSV
python enhanced_workflow.py --csv my_videos.csv
```

**优势**：
- ✅ 可以查看和编辑视频列表
- ✅ 可以手动筛选视频
- ✅ 可以分批处理

**适用场景**：
- 想要先检查视频列表
- 需要手动筛选部分视频
- 分多次处理

---

### 模式3：处理已有CSV

```bash
python enhanced_workflow.py --csv videos.csv
```

**工作流程**：
```
已有CSV文件
    ↓
读取视频列表
    ↓
批量处理
    ↓
更新CSV状态
    ↓
生成报告
```

**优势**：
- ✅ 支持之前的数据
- ✅ 状态过滤（success/fail）
- ✅ 更新处理状态

**适用场景**：
- 有历史CSV数据
- 需要重新处理失败的视频
- 验证已成功的视频

---

## 🚀 快速开始

### 场景1：完整的自动化流程

```bash
# 1. 使用MediaCrawler爬取视频（已完成的步骤）
# cd MediaCrawler
# python main.py

# 2. 回到biliSub目录，一键处理
cd D:\桌面\biliSub
python enhanced_workflow.py --mediacrawler

# 完成！自动生成报告和优化后的字幕
```

**生成文件**：
```
temp_mediacrawler_20260215_220000.csv          # 临时CSV
temp_mediacrawler_*_workflow_report.json      # JSON报告
temp_mediacrawler_*_workflow_report.md        # Markdown报告
temp_mediacrawler_*_processed.csv             # 更新状态的CSV
output/transcripts/*.srt                       # Whisper原始字幕
output/optimized_srt/*_optimized.srt          # GLM优化字幕
```

---

### 场景2：先导出检查，再分批处理

```bash
# 步骤1: 从MediaCrawler提取链接
python enhanced_workflow.py --mediacrawler --export-crawled all_videos.csv

# 步骤2: 检查CSV文件
# 你可以用Excel或其他工具查看all_videos.csv
# 手动删除不想处理的视频

# 步骤3: 处理前10个视频（测试）
python enhanced_workflow.py --csv all_videos.csv --limit 10

# 步骤4: 如果一切正常，处理剩下的
python enhanced_workflow.py --csv all_videos.csv --filter all
```

---

### 场景3：重新处理失败的视频

```bash
# 假设之前处理过，有些失败了
python enhanced_workflow.py --csv videos_processed.csv --filter fail

# 只会处理之前失败的视频
```

---

## 📋 参数详解

### 输入源参数（必选其一）

| 参数 | 说明 | 示例 |
|------|------|------|
| `--mediacrawler` | 从MediaCrawler数据提取 | `--mediacrawler` |
| `--csv FILE` | 从CSV文件读取 | `--csv videos.csv` |

### MediaCrawler相关参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--data-dir` | 数据目录 | data/xhs | `--data-dir data/xhs` |
| `--export-crawled` | 导出CSV文件名 | 无 | `--export-crawled my.csv` |

### 过滤和处理参数

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `--filter` | 状态过滤 | all | all/success/fail |
| `--limit` | 限制处理数量 | 0(全部) | 数字 |
| `--model` | Whisper模型 | medium | tiny/base/small/medium/large |
| `--prompt` | GLM优化模式 | optimization | optimization/simple/tech等 |
| `--no-update` | 不更新CSV | 自动更新 | 标志位 |

---

## 🎨 实用技巧

### 技巧1：分批处理大量视频

```bash
# 导出视频列表
python enhanced_workflow.py --mediacrawler --export-crawled all.csv

# 分批处理（每批10个）
python enhanced_workflow.py --csv all.csv --limit 10 --prompt simple
python enhanced_workflow.py --csv all.csv --limit 10 --filter fail
# ... 继续下一批
```

### 技巧2：对比不同优化模式

```bash
# 用tech模式处理前3个
python enhanced_workflow.py --csv test.csv --limit 3 --prompt tech -o tech_result.csv

# 用optimization模式处理前3个
python enhanced_workflow.py --csv test.csv --limit 3 --prompt optimization -o opt_result.csv

# 对比两种模式的效果
```

### 技巧3：快速测试

```bash
# 使用small模型 + simple模式，快速测试
python enhanced_workflow.py --mediacrawler --model small --prompt simple --limit 2
```

### 技巧4：只验证不更新

```bash
# 处理但不更新原CSV文件
python enhanced_workflow.py --csv videos.csv --no-update
```

---

## 📂 文件结构说明

### MediaCrawler数据结构

```
MediaCrawler/
└── data/
    └── xhs/
        ├── xhs_notes_20250215_120000.csv  ← 爬取的数据
        └── xhs_notes_20250215_130000.json
```

### 输出文件结构

```
biliSub/
├── temp_mediacrawler_*.csv              # 临时CSV（MediaCrawler模式）
├── *_workflow_report.json               # JSON报告
├── *_workflow_report.md                 # Markdown报告
├── *_backup_*.csv                       # 原文件备份
└── *_processed.csv                      # 更新后的CSV

output/
├── transcripts/                         # Whisper原始字幕
│   └── *.srt
└── optimized_srt/                       # GLM优化字幕
    ├── *_optimized.srt
    ├── *_comparison.json
    └── *_report.md
```

---

## 🔄 完整工作流程示例

### 示例：处理小红书脑科学视频

```bash
# ============ 第一步：爬取数据（MediaCrawler） ============
# 假设你已经运行过MediaCrawler
# cd MediaCrawler
# python main.py

# ============ 第二步：提取并处理 ============
cd D:\桌面\biliSub

# 2.1 提取链接并保存为CSV（可选，便于检查）
python enhanced_workflow.py --mediacrawler --export-crawled brain_science.csv

# 2.2 查看文件（可选）
# brain_science.csv 包含所有视频链接

# 2.3 处理前5个视频（测试）
python enhanced_workflow.py --csv brain_science.csv \
    --model medium \
    --prompt tech \
    --limit 5

# ============ 第三步：查看结果 ============
# 查看报告
cat brain_science_workflow_report.md

# 查看优化后的字幕
ls output/optimized_srt/

# ============ 第四步：处理全部 ============
python enhanced_workflow.py --csv brain_science.csv \
    --model medium \
    --prompt tech

# ============ 第五步：检查失败的视频（如果有） ============
python enhanced_workflow.py --csv brain_science_processed.csv \
    --filter fail
```

---

## 💡 高级用法

### 1. 自定义数据目录

如果你的MediaCrawler数据在其他位置：

```bash
python enhanced_workflow.py --mediacrawler --data-dir /path/to/data
```

### 2. 链式处理

```bash
# 先用tech模式处理技术类视频
python enhanced_workflow.py --csv tech_videos.csv --prompt tech

# 再用vlog模式处理生活类视频
python enhanced_workflow.py --csv vlog_videos.csv --prompt vlog
```

### 3. 增量更新

```bash
# 处理一批
python enhanced_workflow.py --csv all.csv --limit 10

# 处理结果会保存到 all_processed.csv

# 下次继续处理（使用processed文件）
python enhanced_workflow.py --csv all_processed.csv --filter fail
```

---

## ⚠️ 注意事项

### 1. MediaCrawler数据格式

确保数据文件包含必要字段：
- CSV格式：`note_id`, `title`, `type`
- JSON格式：数组中的每个对象包含这些字段

### 2. 文件编码

- CSV文件必须是UTF-8-BOM编码
- 如果有乱码，用Excel另存为UTF-8格式

### 3. 处理时间

- 每个视频约40-50秒
- 10个视频约8分钟
- 建议分批处理大量视频

### 4. API限制

- GLM API有调用频率限制
- 建议：处理3-5个视频后等待几秒
- 工具已自动添加3秒间隔

---

## 🆚 对比原版工具

| 功能 | 原版 | 增强版 |
|------|------|--------|
| 从CSV读取 | ✅ | ✅ |
| MediaCrawler集成 | ❌ | ✅ |
| 自动提取链接 | ❌ | ✅ |
| 导出CSV | ❌ | ✅ |
| 状态过滤 | ✅ | ✅ |
| 批量处理 | ✅ | ✅ |
| 更新CSV | ✅ | ✅ |

---

## 🎯 总结

**增强型工作流的三大优势**：

1. **完全自动化**：从爬虫数据到优化字幕，一键完成
2. **灵活可扩展**：支持多种输入和过滤方式
3. **安全可靠**：自动备份、错误处理、状态更新

**最佳实践**：

```bash
# 🌟 推荐流程
python enhanced_workflow.py --mediacrawler --export-crawled check.csv
# 检查check.csv，手动筛选
python enhanced_workflow.py --csv check.csv --model medium --prompt tech
# 完成！
```

现在你可以从MediaCrawler爬虫直接到优化字幕，完全无需手动操作！🎉
