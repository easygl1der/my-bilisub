# 批量视频处理 - 快速开始

## 三种使用方式

### 方式1：单个视频（最快）

```bash
python batch_process_videos.py -u "视频URL"
```

**示例**：
```bash
python batch_process_videos.py -u "https://www.bilibili.com/video/BV1uH4y1H7JN/"
```

### 方式2：多个视频（直接传参数）

```bash
python batch_process_videos.py -u "url1" "url2" "url3"
```

**示例**：
```bash
python batch_process_videos.py -u \
    "https://www.bilibili.com/video/BV1xx/" \
    "https://www.bilibili.com/video/BV2xx/" \
    "https://www.bilibili.com/video/BV3xx/"
```

### 方式3：从文件读取（批量）

```bash
# 创建文本文件，每行一个URL
cat > videos.txt << EOF
https://www.bilibili.com/video/BV1xx/
https://www.bilibili.com/video/BV2xx/
https://www.bilibili.com/video/BV3xx/
EOF

# 批量处理
python batch_process_videos.py -i videos.txt
```

## 常用参数

```bash
# 指定Whisper模型
python batch_process_videos.py -u "url" -m small

# 指定优化模式
python batch_process_videos.py -u "url" -p tech

# 指定输出格式
python batch_process_videos.py -u "url" -f srt,txt,json

# 组合使用
python batch_process_videos.py -u "url" -m medium -p tech -f srt
```

## 参数说明

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `-u` | 直接提供URL（单个或多个） | - | 一个或多个URL |
| `-i` | 从文件读取URL列表 | - | .txt 或 .csv 文件 |
| `-m` | Whisper模型 | medium | tiny/base/small/medium/large |
| `-p` | GLM优化模式 | optimization | optimization/simple/tech/interview等 |
| `-f` | 输出格式 | srt | srt,txt,json |
| `-o` | 报告文件名 | batch_report.json | 自定义 |

## 推荐配置

### 快速处理（测试用）
```bash
python batch_process_videos.py -u "url" -m small -p simple
```

### 技术教程（推荐）
```bash
python batch_process_videos.py -u "url" -m medium -p tech
```

### 高质量处理
```bash
python batch_process_videos.py -u "url" -m large -p aggressive
```

### 批量处理课程
```bash
python batch_process_videos.py -i course.txt -m medium -p tech
```

## 处理流程

每个视频会自动完成：

1. ✅ 下载视频
2. ✅ 提取音频
3. ✅ Whisper识别生成字幕
4. ✅ GLM优化字幕质量
5. ✅ 生成优化报告

## 查看结果

处理完成后会生成：

```
batch_report.json     # 详细数据报告
batch_report.md       # 人类可读报告
```

查看报告：
```bash
cat batch_report.md
```

## 完整示例

```bash
# 处理B站技术教程
python batch_process_videos.py \
    -u "https://www.bilibili.com/video/BV1uH4y1H7JN/" \
    -m medium \
    -p tech \
    -f srt,txt \
    -o my_video_report.json

# 处理完成后查看报告
cat my_video_report.md
```

---

**就这么简单！** 🎉
