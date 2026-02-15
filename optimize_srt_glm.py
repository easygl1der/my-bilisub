#!/usr/bin/env python3
"""
SRT字幕优化工具 - 使用智谱GLM API

功能:
1. 读取Whisper生成的SRT文件
2. 使用智谱GLM API优化文本
3. 保持时间轴不变
4. 生成优化后的SRT文件

优化内容:
- 修正错别字
- 改善语句通顺度
- 添加标点符号
- 优化断句
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from typing import List, Dict

import requests

# ==================== 配置 ====================
OUTPUT_DIR = Path("output/optimized_srt")
BATCH_SIZE = 5  # 默认批处理大小
DEFAULT_PROMPT = "optimization"  # optimization, simple, tech, interview, vlog
# ==============================================

# 导入prompts
try:
    from srt_prompts import (
        OPTIMIZATION_PROMPT,
        SIMPLE_PROMPT,
        CONSERVATIVE_PROMPT,
        AGGRESSIVE_PROMPT,
        TECH_PROMPT,
        INTERVIEW_PROMPT,
        VLOG_PROMPT
    )
except ImportError:
    # 如果prompts文件不存在，使用默认prompt
    OPTIMIZATION_PROMPT = ""  # 将在下面定义
    SIMPLE_PROMPT = ""


def parse_srt(srt_path: str) -> List[Dict]:
    """解析SRT文件"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\n*$)'
    matches = re.findall(pattern, content, re.DOTALL)

    segments = []
    for match in matches:
        segments.append({
            'index': int(match[0]),
            'start': match[1],
            'end': match[2],
            'text': match[3].strip()
        })

    return segments


def format_srt(segments: List[Dict]) -> str:
    """格式化为SRT字符串"""
    output = []
    for seg in segments:
        output.append(f"{seg['index']}")
        output.append(f"{seg['start']} --> {seg['end']}")
        output.append(seg['text'])
        output.append("")  # 空行
    return '\n'.join(output)


def load_api_config():
    """加载API配置"""
    try:
        from config_api import API_CONFIG
        return API_CONFIG['zhipu']
    except ImportError:
        print("❌ 未找到 config_api.py 文件")
        print("   请创建 config_api.py 并添加API密钥")
        return None


def get_prompt(prompt_type: str = "optimization") -> str:
    """获取指定类型的prompt"""
    prompt_map = {
        "optimization": OPTIMIZATION_PROMPT,
        "simple": SIMPLE_PROMPT,
        "conservative": CONSERVATIVE_PROMPT,
        "aggressive": AGGRESSIVE_PROMPT,
        "tech": TECH_PROMPT,
        "interview": INTERVIEW_PROMPT,
        "vlog": VLOG_PROMPT,
    }

    prompt = prompt_map.get(prompt_type.lower(), OPTIMIZATION_PROMPT)

    # 如果prompt为空，使用默认
    if not prompt or prompt.strip() == "":
        prompt = """请优化以下视频字幕文本：

1. 修正错别字
2. 添加标点符号
3. 改善语句流畅度
4. 保持原意，不添加新内容

原文（{count}行）：
{text}

优化后（{count}行，每行一个）："""

    return prompt


def optimize_text_batch(text: str, config: Dict, prompt_type: str = "optimization") -> str:
    """批量优化文本"""
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }

    # 获取prompt
    prompt_template = get_prompt(prompt_type)

    # 计算行数
    lines = text.split('\n')
    line_count = len(lines)

    # 格式化prompt
    prompt = prompt_template.format(
        text=text,
        count=line_count
    )

    payload = {
        "model": config['model'],
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": config.get('temperature', 0.3),
        "top_p": config.get('top_p', 0.7),
        "max_tokens": config.get('max_tokens', 2000)
    }

    try:
        response = requests.post(config['api_url'], headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        optimized_text = result['choices'][0]['message']['content'].strip()

        return optimized_text

    except Exception as e:
        print(f"⚠️  API调用失败: {e}")
        return text  # 返回原文


def optimize_text_segments(segments: List[Dict], config: Dict, batch_size: int = 5, prompt_type: str = "optimization") -> List[Dict]:
    """分段优化文本"""
    print(f"📝 开始优化 {len(segments)} 个字幕段落...")
    print(f"📦 批处理大小: {batch_size}")
    print(f"🎯 Prompt模式: {prompt_type}")

    optimized_segments = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(segments) + batch_size - 1) // batch_size

        print(f"\n处理批次 [{batch_num}/{total_batches}] (段落 {i+1}-{min(i+batch_size, len(segments))})...")

        # 合并批次中的文本
        combined_text = '\n'.join([seg['text'] for seg in batch])

        # 优化
        start_time = time.time()
        optimized_combined = optimize_text_batch(combined_text, config, prompt_type)
        elapsed = time.time() - start_time

        # 分割回段落
        optimized_lines = optimized_combined.split('\n')

        for j, seg in enumerate(batch):
            if j < len(optimized_lines):
                optimized_segments.append({
                    **seg,
                    'text': optimized_lines[j].strip()
                })
            else:
                optimized_segments.append(seg)  # 保持原文

        print(f"   ✓ 完成 (耗时: {elapsed:.2f}秒)")

    return optimized_segments


def compare_srt(original_segments: List[Dict], optimized_segments: List[Dict]) -> Dict:
    """对比原始和优化后的SRT"""
    original_text = '\n'.join([seg['text'] for seg in original_segments])
    optimized_text = '\n'.join([seg['text'] for seg in optimized_segments])

    changes = []

    for i, (orig, opt) in enumerate(zip(original_segments, optimized_segments)):
        if orig['text'] != opt['text']:
            changes.append({
                'index': i + 1,
                'original': orig['text'],
                'optimized': opt['text'],
                'timestamp': f"{orig['start']} --> {orig['end']}"
            })

    return {
        'total_segments': len(original_segments),
        'changed_segments': len(changes),
        'original_length': len(original_text),
        'optimized_length': len(optimized_text),
        'changes': changes[:10]  # 只显示前10个变化
    }


def save_comparison(original_segments: List[Dict], optimized_segments: List[Dict], comparison: Dict, base_name: str, output_dir: Path):
    """保存对比结果"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存优化后的SRT
    srt_path = output_dir / f"{base_name}_optimized.srt"
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(format_srt(optimized_segments))

    # 保存对比报告
    json_path = output_dir / f"{base_name}_comparison.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'base_name': base_name,
            'comparison': comparison,
            'changes': comparison['changes']
        }, f, ensure_ascii=False, indent=2)

    # 保存优化报告（Markdown）
    md_path = output_dir / f"{base_name}_report.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# 字幕优化报告\n\n")
        f.write(f"**文件:** {base_name}\n\n")
        f.write(f"## 📊 统计\n\n")
        f.write(f"- 总段落数: {comparison['total_segments']}\n")
        f.write(f"- 修改段落数: {comparison['changed_segments']}\n")
        f.write(f"- 原始长度: {comparison['original_length']} 字符\n")
        f.write(f"- 优化长度: {comparison['optimized_length']} 字符\n")
        f.write(f"## 📝 主要修改\n\n")

        for change in comparison['changes']:
            f.write(f"### 段落 {change['index']}\n")
            f.write(f"**时间:** {change['timestamp']}\n\n")
            f.write(f"**原文:**\n```\n{change['original']}\n```\n\n")
            f.write(f"**优化:**\n```\n{change['optimized']}\n```\n\n")

    print(f"\n✅ 输出文件:")
    print(f"   📄 {srt_path.name}")
    print(f"   📊 {json_path.name}")
    print(f"   📝 {md_path.name}")


def optimize_srt_file(srt_path: str, config: Dict, batch_size: int = 5, prompt_type: str = "optimization"):
    """优化SRT文件"""
    start_time = time.time()

    print("=" * 70)
    print("🎙️ SRT字幕优化工具 - 智谱GLM")
    print("=" * 70)
    print(f"📄 文件: {Path(srt_path).name}")
    print(f"🤖 模型: {config['model']}")
    print(f"📦 批大小: {batch_size}")
    print(f"🎯 Prompt: {prompt_type}")
    print()

    # 解析SRT
    print("📖 解析SRT文件...")
    segments = parse_srt(srt_path)
    print(f"✅ 解析完成: {len(segments)} 个段落")

    # 优化
    optimized_segments = optimize_text_segments(segments, config, batch_size, prompt_type)

    # 对比
    print(f"\n📊 对比分析...")
    comparison = compare_srt(segments, optimized_segments)

    print(f"   总段落: {comparison['total_segments']}")
    print(f"   修改: {comparison['changed_segments']} 段落")
    print(f"   原文长度: {comparison['original_length']} 字符")
    print(f"   优化后: {comparison['optimized_length']} 字符")

    # 显示部分修改示例
    if comparison['changes']:
        print(f"\n📝 修改示例（前3个）:")
        for change in comparison['changes'][:3]:
            print(f"\n   [{change['index']}] {change['timestamp']}")
            print(f"   原文: {change['original'][:50]}...")
            print(f"   优化: {change['optimized'][:50]}...")

    # 保存结果
    base_name = Path(srt_path).stem
    save_comparison(segments, optimized_segments, comparison, base_name, OUTPUT_DIR)

    total_time = time.time() - start_time

    print(f"\n⏱️  总耗时: {total_time:.2f}秒")
    print("=" * 70)


def main():
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # 加载API配置
    config = load_api_config()
    if not config:
        return

    import argparse
    parser = argparse.ArgumentParser(description="SRT字幕优化工具 - 智谱GLM")
    parser.add_argument("-s", "--srt", help="SRT文件路径")
    parser.add_argument("-b", "--batch-size", type=int, default=BATCH_SIZE, help="批处理大小")
    parser.add_argument("-d", "--dir", help="处理整个目录", default=None)
    parser.add_argument("-p", "--prompt", default=DEFAULT_PROMPT,
                       choices=["optimization", "simple", "conservative", "aggressive", "tech", "interview", "vlog"],
                       help="Prompt类型 (默认: optimization)")

    args = parser.parse_args()

    if args.dir:
        # 批量处理目录
        dir_path = Path(args.dir)
        srt_files = list(dir_path.glob("*.srt"))

        print(f"📁 批量处理模式: {len(srt_files)} 个文件\n")

        for i, srt_file in enumerate(srt_files, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{len(srt_files)}] {srt_file.name}")
            print(f"{'='*70}")

            try:
                optimize_srt_file(str(srt_file), config, args.batch_size, args.prompt)
            except Exception as e:
                print(f"❌ 失败: {e}")

    elif args.srt:
        # 单文件处理
        optimize_srt_file(args.srt, config, args.batch_size, args.prompt)

    else:
        # 交互模式
        srt_path = input("请输入SRT文件路径: ").strip()
        if srt_path:
            optimize_srt_file(srt_path, config, args.batch_size, args.prompt)


if __name__ == "__main__":
    main()
