# 批量视频处理完整指南

## 功能说明

`batch_process_videos.py` 是一个完整的批量处理工具，可以自动完成以下流程：

1. **视频下载**：自动下载B站/小红书视频
2. **Whisper识别**：使用指定模型生成字幕
3. **GLM优化**：使用智谱API优化字幕质量
4. **生成报告**：详细的处理报告和统计

## 快速开始

### 1. 准备视频URL列表

创建一个文本文件（如 `my_videos.txt`），每行一个URL：

```txt
# B站技术视频
https://www.bilibili.com/video/BV1uH4y1H7JN/

# 小红书视频
https://www.xiaohongshu.com/explore/123456789

# 更多视频...
https://www.bilibili.com/video/BVxxxxxx/
```

或者使用CSV文件（第一列为URL）：

```csv
URL,标题,备注
https://www.bilibili.com/video/BV1uH4y1H7JN/,技术教程,重要
https://www.bilibili.com/video/BVxxxxxx/,访谈记录,
```

### 2. 运行批量处理

```bash
# 基本用法（使用默认配置）
python batch_process_videos.py my_videos.txt

# 指定Whisper模型
python batch_process_videos.py my_videos.txt -m small

# 指定GLM优化模式
python batch_process_videos.py my_videos.txt -p tech

# 完整配置
python batch_process_videos.py my_videos.txt -m medium -f srt,txt,json -p optimization

# 使用CSV文件
python batch_process_videos.py videos.csv -m medium -p tech

# 自定义报告文件名
python batch_process_videos.py my_videos.txt -o my_report.json
```

## 命令行参数

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `input_file` | URL列表文件 | 必填 | .txt 或 .csv |
| `-m, --model` | Whisper模型 | medium | tiny/base/small/medium/large |
| `-f, --formats` | 输出格式 | srt | srt,txt,json |
| `-p, --prompt` | GLM优化模式 | optimization | optimization/simple/conservative/aggressive/tech/interview/vlog |
| `-o, --output` | 报告文件名 | batch_report.json | 自定义文件名 |

## 处理流程

### 单个视频的处理步骤：

```
1. 视频下载和音频提取
   └─> yt-dlp下载视频
   └─> FFmpeg提取音频

2. Whisper语音识别
   └─> 加载指定模型
   └─> 识别并生成字幕
   └─> 保存为SRT/TXT/JSON

3. GLM字幕优化
   └─> 读取SRT文件
   └─> 批量调用GLM API
   └─> 修正错误和优化表达
   └─> 生成优化报告

4. 完成并记录结果
   └─> 保存文件路径
   └─> 记录耗时和状态
```

## 输出文件结构

处理后会生成以下文件：

```
biliSub/
├── batch_report.json          # 批量处理报告（JSON格式）
├── batch_report.md            # 批量处理报告（Markdown格式）
│
└── output/
    ├── transcripts/           # Whisper生成的字幕
    │   ├── 视频1.srt
    │   ├── 视频2.srt
    │   └── ...
    │
    ├── optimized_srt/         # GLM优化后的字幕
    │   ├── 视频1_optimized.srt
    │   ├── 视频1_comparison.json
    │   ├── 视频1_report.md
    │   ├── 视频2_optimized.srt
    │   └── ...
    │
    └── xiaohongshu/          # 小红书视频文件
        └── ...
```

## 报告内容

### JSON报告 (`batch_report.json`)

```json
{
  "timestamp": "2025-02-15 12:30:45",
  "total_videos": 10,
  "successful": 9,
  "failed": 1,
  "total_time": 3600.5,
  "results": [
    {
      "url": "https://www.bilibili.com/video/BV1uH4y1H7JN/",
      "platform": "bilibili",
      "success": true,
      "error": null,
      "transcribe_time": 245.3,
      "optimize_time": 42.1,
      "total_time": 287.4,
      "srt_path": "output/transcripts/视频.srt",
      "optimized_path": "output/optimized_srt/视频_optimized.srt"
    }
  ]
}
```

### Markdown报告 (`batch_report.md`)

人类可读的报告，包含：
- 总体统计（总数、成功、失败、耗时）
- 每个视频的详细结果
- 文件路径和错误信息

## 使用场景

### 场景1：批量处理B站技术教程

```bash
# 创建文件 tech_videos.txt
echo "https://www.bilibili.com/video/BV1uH4y1H7JN/" > tech_videos.txt
echo "https://www.bilibili.com/video/BVxxxxxx/" >> tech_videos.txt

# 使用tech模式批量处理
python batch_process_videos.py tech_videos.txt -m medium -p tech
```

### 场景2：处理访谈/对话视频

```bash
# 使用interview模式，适合对话内容
python batch_process_videos.py interviews.txt -p interview -f srt,txt
```

### 场景3：快速批量处理（使用小模型）

```bash
# 使用small模型加快速度，simple模式快速优化
python batch_process_videos.py large_batch.txt -m small -p simple
```

### 场景4：高质量处理（大模型）

```bash
# 使用large模型获得最佳质量
python batch_process_videos.py important_videos.txt -m large -p aggressive
```

## 性能参考

基于实测数据（5分钟视频）：

| 配置 | Whisper时间 | GLM时间 | 总时间/视频 |
|------|------------|---------|------------|
| small + simple | ~2分钟 | ~30秒 | ~2.5分钟 |
| medium + optimization | ~4分钟 | ~40秒 | ~4.5分钟 |
| large + aggressive | ~8分钟 | ~50秒 | ~9分钟 |

**批量处理示例**：
- 10个视频（medium模型）：约45分钟
- 20个视频（small模型）：约50分钟

## 错误处理

### 部分失败不影响整体

如果某个视频处理失败，会继续处理下一个：

```bash
📊 处理总结:
   总数: 10
   成功: 9
   失败: 1
   总耗时: 3600秒
```

### 常见错误和解决

1. **视频下载失败**
   - 检查网络连接
   - 确认视频URL有效
   - 某些视频可能需要登录或已删除

2. **Whisper超时**
   - 使用更小的模型（-m small）
   - 检查视频时长是否过长

3. **GLM API失败**
   - 检查API密钥配置
   - 检查网络连接
   - 程序会保留原始字幕继续

4. **内存不足**
   - 使用small或base模型
   - 避免同时处理多个视频

## 最佳实践

### 1. 分批处理大量视频

```bash
# 将100个视频分成多个批次
head -20 videos.txt > batch1.txt
head -40 videos.txt | tail -20 > batch2.txt
# 依此类推...

# 分别处理
python batch_process_videos.py batch1.txt -o report1.json
python batch_process_videos.py batch2.txt -o report2.json
```

### 2. 根据视频类型选择模式

```bash
# 技术教程
python batch_process_videos.py tech_videos.txt -p tech

# 访谈对话
python batch_process_videos.py talks.txt -p interview

# Vlog日常
python batch_process_videos.py vlogs.txt -p vlog
```

### 3. 测试后再批量处理

```bash
# 先用1-2个视频测试
python batch_process_videos.py test_urls.txt -m small

# 确认无误后再处理全部
python batch_process_videos.py all_urls.txt -m medium
```

### 4. 定期检查中间结果

```bash
# 查看已生成的字幕文件
ls -lh output/transcripts/

# 查看最新的优化报告
ls -lh output/optimized_srt/*_report.md
```

## 完整示例

### 示例：处理一个课程的所有视频

```bash
# 1. 创建课程视频列表
cat > course_videos.txt << EOF
# 第1课
https://www.bilibili.com/video/BV1xx1/
# 第2课
https://www.bilibili.com/video/BV1xx2/
# 第3课
https://www.bilibili.com/video/BV1xx3/
EOF

# 2. 批量处理（技术课程，使用medium模型和tech优化）
python batch_process_videos.py course_videos.txt \
    -m medium \
    -p tech \
    -f srt,txt \
    -o course_report.json

# 3. 查看报告
cat course_report.md

# 4. 检查输出文件
ls output/transcripts/
ls output/optimized_srt/
```

## 高级技巧

### 1. 结合之前的数据

如果已经有CSV文件包含更多信息：

```csv
URL,分类,优先级,备注
https://www.bilibili.com/video/BV1xx/,技术,高,重要教程
https://www.bilibili.com/video/BV2xx/,访谈,中,嘉宾采访
```

程序会自动读取第一列的URL。

### 2. 使用注释组织视频列表

```txt
# ========== 第一部分：基础教程 ==========
https://www.bilibili.com/video/BV1xx1/
https://www.bilibili.com/video/BV1xx2/

# ========== 第二部分：进阶内容 ==========
https://www.bilibili.com/video/BV2xx1/
https://www.bilibili.com/video/BV2xx2/

# ========== 第三部分：实战项目 ==========
https://www.bilibili.com/video/BV3xx1/
```

### 3. 后台运行大批量任务

```bash
# Linux/Mac: 使用nohup
nohup python batch_process_videos.py large_list.txt > process.log 2>&1 &

# Windows: 使用start
start /B python batch_process_videos.py large_list.txt > process.log 2>&1
```

## 故障排除

### 问题1：程序卡住不动

**解决**：
- 检查网络连接
- 查看是否有进程占用CPU
- 重启程序

### 问题2：大量视频失败

**解决**：
- 检查URL是否有效
- 测试单个URL是否可处理
- 查看详细错误信息

### 问题3：处理速度太慢

**解决**：
- 使用small模型
- 使用simple优化模式
- 分批处理

## 总结

批量处理工具的核心优势：

1. ✅ **全自动化**：下载 → 识别 → 优化 一键完成
2. ✅ **批量处理**：一次处理数十个视频
3. ✅ **智能容错**：部分失败不影响整体
4. ✅ **详细报告**：完整的处理记录和统计
5. ✅ **灵活配置**：支持多种模型和优化模式

现在你可以把一堆视频链接丢给工具，自动完成所有处理！
