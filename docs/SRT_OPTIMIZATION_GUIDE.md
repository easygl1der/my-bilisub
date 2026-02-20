# SRT字幕优化工具使用指南

## 功能概述

`optimize_srt_glm.py` 是一个使用智谱GLM API优化Whisper生成的SRT字幕的工具。它可以：
- 修正ASR识别错误（如同音字错误）
- 添加标点符号
- 改善语句流畅度
- 规范专业术语大小写
- 生成优化报告

## 配置要求

### 1. API配置

创建 `config_api.py` 文件（已添加到.gitignore）：

```python
API_CONFIG = {
    "zhipu": {
        "api_key": "your_api_key_here",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "temperature": 0.3,
        "top_p": 0.7,
        "max_tokens": 2000
    }
}
```

### 2. 安装依赖

```bash
pip install requests
```

## 使用方法

### 基本用法

```bash
# 单文件优化（使用默认optimization模式）
python optimize_srt_glm.py -s input.srt

# 指定prompt类型
python optimize_srt_glm.py -s input.srt -p tech

# 调整批处理大小
python optimize_srt_glm.py -s input.srt -b 10

# 批量处理目录
python optimize_srt_glm.py -d ./srt_files -p optimization
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --srt` | SRT文件路径 | - |
| `-b, --batch-size` | 批处理大小 | 5 |
| `-d, --dir` | 处理整个目录 | - |
| `-p, --prompt` | Prompt类型 | optimization |

## Prompt类型说明

### 1. optimization（推荐）
- 平衡模式，适合大多数视频
- 修正错误 + 添加标点 + 适度优化
- 安全且效果好

### 2. simple
- 快速模式，处理大量字幕
- 只处理明显问题
- 速度更快，适合批量处理

### 3. conservative
- 严格保守模式
- 最小化修正，只处理明显错误
- 不改变句子结构，不合并或拆分

### 4. aggressive
- 深度优化模式
- 合并碎片化短句，构建完整句子
- 口语转书面化，提升专业度

### 5. tech（技术视频）
- 专门针对技术教学视频
- 严格规范专业术语（Cloud Code, API, SDK等）
- 代码和命令保持原样

### 6. interview（访谈对话）
- 访谈或对话视频专用
- 识别说话人，使用冒号和引号标记
- 删除口头禅，保留自然对话感

### 7. vlog（生活类）
- Vlog或生活类视频
- 保持轻松自然的表达风格
- 适度的语气词和感叹词

## 输出文件

优化后会生成三个文件：

```
output/optimized_srt/
├── {filename}_optimized.srt      # 优化后的字幕文件
├── {filename}_comparison.json    # 详细的对比数据
└── {filename}_report.md          # 优化报告（Markdown格式）
```

### 1. 优化后的SRT文件
可直接用于视频字幕，包含所有优化内容。

### 2. JSON对比文件
包含详细的修改记录：
```json
{
  "base_name": "filename",
  "comparison": {
    "total_segments": 58,
    "changed_segments": 52,
    "original_length": 793,
    "optimized_length": 844
  },
  "changes": [
    {
      "index": 1,
      "original": "原文",
      "optimized": "优化后",
      "timestamp": "00:00:00,000 --> 00:00:02,360"
    }
  ]
}
```

### 3. Markdown报告
人类可读的优化报告，包含：
- 统计信息
- 主要修改示例
- 修改前后的对比

## 优化效果示例

### 示例1：专业术语规范化
```
原文: 一份引爆全网的cloud code调教指南
优化: 一份引爆全网的Cloud Code调教指南，
```

### 示例2：标点符号添加
```
原文: 全是干货
优化: 全是干货！
```

### 示例3：错别字修正
```
原文: 作者趁在srpk举办的编程大赛中
优化: 作者趁在SRPK举办的编程大赛中，
```

### 示例4：语句流畅度改善
```
原文: 别再重复下指令了
优化: 告别重复指令，利用Cloud Code Scales
```

## 性能参考

基于实测数据（58个字幕段落）：

| Prompt类型 | 处理时间 | 修改段落数 | 特点 |
|-----------|---------|----------|------|
| optimization | ~40秒 | 52/58 | 平衡 |
| tech | ~44秒 | 56/58 | 技术术语更规范 |
| simple | ~42秒 | 33/58 | 保守 |

**注**：实际时间受网络状况和API响应速度影响。

## 常见问题

### Q1: 为什么有些段落后显示为空？
**A**: GLM模型可能认为某些原文已经很完美，或者无法理解上下文，因此返回空。系统会自动保持原文。

### Q2: 如何选择合适的prompt类型？
**A**:
- 技术教程 → tech
- 访谈对话 → interview
- Vlog/日常 → vlog
- 其他 → optimization（默认）

### Q3: 批处理大小如何设置？
**A**:
- 小批次（3-5）：更精确，但API调用次数多
- 大批次（8-10）：更快，但可能精度略降
- 推荐：5（默认）

### Q4: 如何处理超大字幕文件？
**A**:
1. 增加批处理大小（-b 10）
2. 使用simple模式快速处理
3. 考虑分段处理

## 集成到工作流

### 完整的视频转字幕工作流：

```bash
# 1. 下载视频并提取音频
python ultimate_transcribe.py -u "video_url" -a

# 2. 使用Whisper生成字幕
python ultimate_transcribe.py -u "video_url" -m medium -f srt

# 3. 优化生成的字幕
python optimize_srt_glm.py -s output/transcripts/video.srt -p tech

# 4. 检查优化结果
cat output/optimized_srt/video_report.md
```

## 注意事项

1. **API费用**：使用智谱GLM API会产生费用，注意控制使用量
2. **网络稳定性**：确保网络连接稳定，避免中断
3. **备份原文件**：优化前保留原始SRT文件
4. **人工校对**：AI优化后建议人工校对关键内容
5. **隐私保护**：不要上传敏感或私密内容到API

## 技术细节

### 批处理机制
- 将N个字幕段落合并为一个批次
- 一次性发送给GLM API处理
- API返回优化结果后再拆分回独立段落

### 格式保持
- 严格保持每行对应一个时间戳
- 不修改时间轴信息
- 保持原有的段落结构

### 错误处理
- API调用失败时保持原文
- 网络超时自动重试
- 输出行数不匹配时用原文填充

## 更新日志

### v1.0 (2025-02)
- 初始版本
- 支持7种prompt类型
- 批处理机制
- 详细的报告生成
- 支持单文件和批量处理

## 相关文件

- `optimize_srt_glm.py` - 主程序
- `srt_prompts.py` - Prompt定义文件
- `config_api.py` - API配置文件（需自行创建）
