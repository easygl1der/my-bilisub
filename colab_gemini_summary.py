#!/usr/bin/env python3
"""
在 Google Colab 上运行的 Gemini 字幕摘要生成器

使用方法：
1. 在 Colab 中创建新笔记本
2. 复制此代码到一个单元格
3. 运行并按提示操作
"""

import os
import time
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
from google.colab import files, output

# ==================== 配置区 ====================

# 请在这里填入你的 Gemini API Key
GEMINI_API_KEY = ""  # 或者运行后手动输入

# 字幕文件夹路径（Colab 中建议上传到 /content/subtitles/）
SUBTITLE_DIR = "/content/subtitles"

# 并发数（建议 3-5）
MAX_WORKERS = 3

# 模型选择
MODEL = 'gemini-2.5-flash-lite'  # 或 'gemini-2.5-flash', 'gemini-2.5-pro'

# ==================== 安装依赖 ====================

def install_dependencies():
    """安装必要的依赖"""
    print("📦 安装依赖...")
    !pip install -q google-generativeai

# ==================== Gemini API ====================

def setup_gemini(api_key: str):
    """设置 Gemini API"""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai

# ==================== SRT 处理 ====================

def parse_srt(srt_path: Path) -> List[Dict]:
    """解析 SRT 文件"""
    import re
    entries = []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n\d+\n|$)'
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        index, start, end, text = match
        entries.append({
            'index': int(index),
            'start': start,
            'end': end,
            'text': text.strip().replace('\n', ' ')
        })

    return entries


def srt_to_text(srt_path: Path, max_length: int = 15000) -> str:
    """将 SRT 转换为纯文本"""
    entries = parse_srt(srt_path)
    full_text = ' '.join([e['text'] for e in entries])

    if len(full_text) > max_length:
        full_text = full_text[:int(max_length * 0.8)] + '\n\n[内容过长，已截断...]'

    return full_text


# ==================== 摘要生成 ====================

KNOWLEDGE_PROMPT = """你是一个专业的视频内容分析师，擅长将视频字幕内容转化为结构化的知识库笔记。请详细分析以下视频字幕，输出用于构建"第二大脑"的笔记。

# {title}

## 📋 视频基本信息
- **核心主题**: [一句话概括]
- **内容结构**: [流水账式/观点论证式/新闻汇总式/故事叙述式]

## 📖 视频大意（100-200字）
[用精炼的书面语言概括视频核心内容，去除冗余的前情提要和无关信息]

## 🎯 核心观点（三段论）
[如果视频有明确论点，用三段论形式呈现]
- **大前提**: [普遍性前提或背景]
- **小前提**: [具体情境或条件]
- **结论**: [最终观点或主张]

[如果是新闻分享类，则列出]
- **新闻条目1**: [标题 + 关键信息]
- **新闻条目2**: [标题 + 关键信息]

## 📊 论点论据结构
1. **主要论点**
   - 论述内容: [详细说明]
   - 支持论据: [数据、案例、逻辑推理]
   - 可信度评估: [高/中/低，说明理由]

2. **次要论点**（如有）
   - 论述内容: [详细说明]
   - 支持论据: [数据、案例、逻辑推理]

## 💎 金句/好词好句提取
[请提取以下类型的句子]

### 1. 引经据典
- 原句: "..."

### 2. 故事/案例
- 原句/描述: "..."

### 3. 精辟论据
- 原句: "..."

### 4. 深刻观点
- 原句: "..."

### 5. 好词好句
- 原句: "..."

## 📝 书面文稿
[将字幕内容整理成精炼的书面表达文稿，要求：
- 去除所有口语化冗余（如"那个"、"就是"、"然后"等）
- 使用正式、结构化的书面语言
- 保留核心信息和逻辑链条
- 适合作为模型训练的语言材料
- 字数控制在原文的30%-50%]

## ⚠️ 内容质量分析
### 情绪操控检测
- **制造焦虑/FOMO情绪**: [是/否]
- **分析**: [如果有，说明使用了什么手法]

### 信息可靠性
- **信息源可信度**: [高/中/低]
- **事实核查**: [有哪些可验证的事实]
- **潜在偏见**: [是否存在明显偏见]

### 知识价值评估
- **新颖性**: [★★★★★]
- **实用性**: [★★★★★]
- **深度**: [★★★★★]
- **推荐收藏**: [是/否]

---
请确保输出结构完整，每个部分都要有实质内容。如果某部分确实不适用，请标注"[不适用]"并说明原因。

---

## 字幕内容

{text}"""

def generate_summary(genai, srt_path: Path, model: str, index: int, total: int) -> Dict:
    """生成单个视频的摘要"""
    start_time = time.time()
    title = srt_path.stem

    print(f"\n[{index}/{total}] 处理: {title}")

    try:
        # 转换 SRT 为文本
        srt_text = srt_to_text(srt_path)
        print(f"  文本长度: {len(srt_text):,} 字符")

        # 调用 Gemini API
        prompt = KNOWLEDGE_PROMPT.format(title=title, text=srt_text)
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(prompt)

        elapsed = time.time() - start_time

        # 获取 token 信息
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        print(f"  ✅ 成功! Tokens: {input_tokens + output_tokens:,} | 耗时: {elapsed:.2f}秒")

        return {
            'title': title,
            'summary': response.text.strip(),
            'file': srt_path.name,
            'index': index,
            'success': True,
            'tokens': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 失败: {str(e)} | 耗时: {elapsed:.2f}秒")

        return {
            'title': title,
            'summary': f"**处理失败**: {str(e)}",
            'file': srt_path.name,
            'index': index,
            'success': False,
            'failed': True,
            'error': str(e)
        }


# ==================== 主处理函数 ====================

def process_subtitles_colab(api_key: str, subtitle_dir: str, model: str, max_workers: int = 3):
    """在 Colab 中处理字幕"""
    import google.generativeai as genai

    # 设置 API
    genai.configure(api_key=api_key)

    subtitle_path = Path(subtitle_dir)

    if not subtitle_path.exists():
        print(f"❌ 目录不存在: {subtitle_path}")
        print(f"\n请先上传字幕文件到 {subtitle_dir}")
        print(f"可以使用以下代码创建目录并上传:")
        print(f"  !mkdir -p {subtitle_dir}")
        print(f"  然后在左侧文件面板中上传 SRT 文件")
        return

    # 获取所有 SRT 文件
    srt_files = list(subtitle_path.glob("*.srt"))

    if not srt_files:
        print(f"❌ 未找到 SRT 文件")
        return

    author_name = subtitle_path.name
    print(f"📂 作者: {author_name}")
    print(f"📄 找到 {len(srt_files)} 个字幕文件")
    print(f"⚡ 并发数: {max_workers}")
    print(f"🤖 模型: {model}")
    print("=" * 60)

    start_time = time.time()
    all_results = []

    # 并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(generate_summary, genai, srt_file, model, i, len(srt_files))
            for i, srt_file in enumerate(srt_files, 1)
        ]

        for future in futures:
            result = future.result()
            all_results.append(result)

    # 按原始顺序排序
    all_results.sort(key=lambda x: x['index'])

    # 统计
    summaries = []
    success_count = 0
    fail_count = 0
    total_tokens = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for r in all_results:
        summaries.append(r)
        if r['success']:
            success_count += 1
            total_tokens += r.get('tokens', 0)
            total_input_tokens += r.get('input_tokens', 0)
            total_output_tokens += r.get('output_tokens', 0)
        else:
            fail_count += 1

    # 生成报告
    report_path = Path(subtitle_dir).parent / f"{author_name}_AI总结.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# {author_name} 视频内容分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**视频数量**: {len(srt_files)}\n\n")
        f.write(f"**成功处理**: {success_count}\n\n")
        f.write(f"**Token 统计**: 输入 {total_input_tokens:,} | 输出 {total_output_tokens:,} | 总计 {total_tokens:,}\n\n")
        f.write("---\n\n")
        f.write("## 各视频摘要\n\n")

        for item in summaries:
            f.write(f"### {item['title']}\n\n")
            f.write(f"{item['summary']}\n\n")
            f.write(f"*来源文件: {item['file']}*\n\n")

    total_elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"📊 处理完成!")
    print(f"  成功: {success_count} | 失败: {fail_count}")
    print(f"  总耗时: {total_elapsed:.2f}秒")
    print(f"  平均每视频: {total_elapsed/len(srt_files):.2f}秒")
    print(f"📊 Token 统计:")
    print(f"  输入: {total_input_tokens:,} | 输出: {total_output_tokens:,} | 总计: {total_tokens:,}")
    print(f"\n✅ 报告已保存: {report_path}")

    # 下载报告
    print(f"\n📥 正在下载报告...")
    files.download(str(report_path))


# ==================== 入口函数 ====================

def main():
    """主函数 - 在 Colab 中运行"""

    # 安装依赖
    install_dependencies()

    # 获取 API Key
    api_key = GEMINI_API_KEY
    if not api_key:
        print("请输入你的 Gemini API Key:")
        api_key = input().strip()

    if not api_key:
        print("❌ 未提供 API Key")
        return

    # 检查目录
    subtitle_dir = SUBTITLE_DIR
    subtitle_path = Path(subtitle_dir)

    if not subtitle_path.exists():
        print(f"\n⚠️ 目录 {subtitle_dir} 不存在")
        print("正在创建目录...")
        subtitle_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 目录已创建: {subtitle_dir}")
        print("\n请在左侧文件面板中上传 SRT 字幕文件到该目录，然后重新运行此单元格")
        return

    # 确认运行
    print(f"\n📂 字幕目录: {subtitle_dir}")
    print(f"⚡ 并发数: {MAX_WORKERS}")
    print(f"🤖 模型: {MODEL}")

    response = input("\n开始处理? (y/n): ").strip().lower()
    if response != 'y':
        print("已取消")
        return

    # 处理
    process_subtitles_colab(api_key, subtitle_dir, MODEL, MAX_WORKERS)


# 运行
if __name__ == "__main__":
    main()
