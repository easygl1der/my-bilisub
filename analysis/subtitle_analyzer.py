#!/usr/bin/env python3
"""
使用 Gemini API 批量生成字幕摘要和汇总报告（支持并发处理）

方案2：分批摘要再汇总
1. 读取作者文件夹下所有 SRT 文件
2. 每个 SRT 发给 Gemini → 生成知识库型摘要（基于 knowledge 模式）
3. 把所有摘要合并发给 Gemini → 生成总报告
4. 保存到 {作者名}_AI总结.md

使用示例:
    # 处理指定作者的字幕文件夹
    python gemini_subtitle_summary.py "output/subtitles/小天fotos"

    # 指定并发数（默认3）
    python gemini_subtitle_summary.py "output/subtitles/小天fotos" -j 5

    # 指定Gemini模型
    python gemini_subtitle_summary.py "output/subtitles/小天fotos" --model flash-lite
"""

import asyncio
import os
import sys
import time
import json
import argparse
import re
import threading
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

# 优先使用新 SDK
try:
    from google import genai
    USE_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as genai
        USE_NEW_SDK = False
    except ImportError:
        print("未安装 google-genai 或 google-generativeai 库")
        print("请运行: pip install google-genai")
        sys.exit(1)



# 线程安全的打印锁
print_lock = threading.Lock()


# ==================== 配置 ====================

GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',
    'flash': 'gemini-2.5-flash',
    'pro': 'gemini-2.5-pro',
}


def get_api_key() -> str:
    """获取 Gemini API Key"""
    # 1. 环境变量
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # 2. 配置文件
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from config.config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


class GeminiClient:
    """Gemini API 客户端（兼容新旧 SDK）"""

    def __init__(self, model: str = 'flash-lite', api_key: str = None):
        self.api_key = api_key or get_api_key()
        self.model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash-lite'])
        self.use_new_sdk = USE_NEW_SDK

        if not self.api_key:
            raise ValueError("未找到 Gemini API Key")

        if self.use_new_sdk:
            # 新 SDK
            self.client = genai.Client(api_key=self.api_key)
        else:
            # 旧 SDK
            import google.generativeai as genai_old
            genai_old.configure(api_key=self.api_key)

    def generate_content(self, prompt: str) -> Dict:
        """
        生成内容

        Returns:
            {'text': '生成内容', 'tokens': int, 'input_tokens': int, 'output_tokens': int,
             'success': bool, 'error': str}
        """
        try:
            if self.use_new_sdk:
                # 新 SDK
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                text = response.text
                # 新 SDK token 信息
                input_tokens = 0
                output_tokens = 0
                total_tokens = 0
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    metadata = response.usage_metadata
                    input_tokens = getattr(metadata, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(metadata, 'candidates_token_count', 0) or 0
                    total_tokens = getattr(metadata, 'total_token_count', 0) or 0
            else:
                # 旧 SDK
                import google.generativeai as genai_old
                model = genai_old.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                text = response.text
                input_tokens = 0
                output_tokens = 0
                total_tokens = 0
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    metadata = response.usage_metadata
                    input_tokens = getattr(metadata, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(metadata, 'candidates_token_count', 0) or 0
                    total_tokens = getattr(metadata, 'total_token_count', 0) or 0

            return {
                'text': text.strip() if text else '',
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'success': True
            }

        except Exception as e:
            return {
                'text': '',
                'tokens': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'success': False,
                'error': str(e)
            }


# ==================== MD 汇总文件读取 ====================

def parse_summary_md(md_path: Path) -> Dict[str, Dict]:
    """
    从汇总 MD 文件解析视频信息表格

    Returns:
        {标题: {序号, 标题, 链接, BV号, 时长, 播放量, 评论数, 发布时间}}
    """
    videos = {}

    if not md_path.exists():
        return videos

    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取表格数据
        in_table = False
        for line in content.split('\n'):
            # 跳过表头分隔线
            if line.startswith('|:----'):
                in_table = True
                continue

            # 检测表格结束
            if in_table and not line.startswith('|'):
                break

            # 解析表格行
            if in_table and line.startswith('|'):
                parts = [p.strip() for p in line.split('|')[1:-1]]  # 去掉首尾空元素
                if len(parts) >= 8:
                    try:
                        seq = parts[0]
                        title = parts[1]
                        link = parts[2]
                        # 从链接中提取纯URL
                        if '[' in link and '](' in link:
                            link = link.split('](')[1].rstrip(')')
                        bvid = parts[3]
                        duration = parts[4]
                        views = parts[5]
                        comments = parts[6]
                        pub_time = parts[7]

                        # 用标题作为key
                        videos[title] = {
                            '序号': seq,
                            '标题': title,
                            '链接': link,
                            'BV号': bvid,
                            '时长': duration,
                            '播放量': views,
                            '评论数': comments,
                            '发布时间': pub_time,
                        }
                    except (ValueError, IndexError):
                        continue

    except Exception as e:
        print(f"⚠️ 读取 MD 汇总文件失败: {e}")

    return videos


def find_summary_md(subtitle_dir: Path) -> Optional[Path]:
    """
    查找对应的汇总 MD 文件
    """
    author_name = subtitle_dir.name
    possible_paths = [
        subtitle_dir.parent / f"{author_name}_汇总.md",
        subtitle_dir / f"{author_name}_汇总.md",
        subtitle_dir.parent / "output" / "subtitles" / f"{author_name}_汇总.md",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # 在同级目录搜索
    for md_file in subtitle_dir.parent.glob("*_汇总.md"):
        if author_name in md_file.stem:
            return md_file

    return None


def parse_existing_report_results(report_path: Path) -> List[Dict]:
    """从现有报告中解析已有的结果（用于追加模式）"""
    results = []
    if not report_path.exists():
        return results

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 简单解析：提取 ### 标题和后面的内容
        lines = content.split('\n')
        current_title = None
        current_content = []

        for line in lines:
            if line.strip().startswith('### ') and not line.strip().startswith('### 📹'):
                # 保存上一个
                if current_title:
                    results.append({
                        'title': current_title,
                        'summary': '\n'.join(current_content).strip(),
                        'file': f'{current_title}.srt',
                        'success': True
                    })
                # 开始新的
                current_title = line.strip()[4:].strip()
                current_content = []
            elif current_title:
                current_content.append(line)

        # 保存最后一个
        if current_title:
            results.append({
                'title': current_title,
                'summary': '\n'.join(current_content).strip(),
                'file': f'{current_title}.srt',
                'success': True
            })

    except Exception as e:
        print(f"⚠️ 解析现有报告失败: {e}")

    return results


def format_video_info_header(video_info: Dict, srt_filename: str) -> str:
    """
    格式化视频基本信息头部
    """
    if not video_info:
        return f"> **视频文件**: {srt_filename}\n\n"

    info_lines = [
        "## 📹 视频信息",
        f"| 项目 | 内容 |",
        f"|------|------|",
    ]

    # 按顺序添加信息
    order = ['序号', '标题', '链接', 'BV号', '时长', '播放量', '评论数', '发布时间']
    for key in order:
        value = video_info.get(key, '')
        if value:
            if key == '链接':
                info_lines.append(f"| **{key}** | [{value}]({value}) |")
            elif key == '标题':
                info_lines.append(f"| **{key}** | {value} |")
            else:
                info_lines.append(f"| **{key}** | {value} |")

    return '\n'.join(info_lines) + '\n\n---\n\n'


# ==================== SRT 处理 ====================

def parse_srt(srt_path: Path) -> List[Dict]:
    """
    解析 SRT 文件，返回字幕条目列表

    Returns:
        [
            {'index': 1, 'start': '00:00:01,000', 'end': '00:00:04,000', 'text': '字幕内容'},
            ...
        ]
    """
    entries = []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT 格式解析
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
    """
    将 SRT 转换为纯文本，控制长度避免超限

    Args:
        srt_path: SRT 文件路径
        max_length: 最大文本长度（字符数）

    Returns:
        字幕文本内容
    """
    entries = parse_srt(srt_path)

    # 合并所有字幕文本
    full_text = ' '.join([e['text'] for e in entries])

    # 如果超过长度限制，截断并保留前80%
    if len(full_text) > max_length:
        full_text = full_text[:int(max_length * 0.8)] + '\n\n[内容过长，已截断...]'

    return full_text


# ==================== Gemini 调用 ====================

class GeminiSummarizer:
    """Gemini 字幕摘要生成器"""

    def __init__(self, model: str = 'flash-lite', api_key: str = None):
        self.client = GeminiClient(model=model, api_key=api_key)
        self.model_name = self.client.model_name

    def generate_summary(self, text: str, title: str = "") -> Dict:
        """
        为单个字幕生成知识库型摘要（基于 knowledge 模式）

        Args:
            text: 字幕文本
            title: 视频标题

        Returns:
            {'summary': '摘要内容', 'tokens': int}
        """
        prompt = f"""你是一个专业的视频内容分析师，擅长将视频字幕内容转化为结构化的知识库笔记。请详细分析以下视频字幕，输出用于构建"第二大脑"的笔记。

{'# ' + title if title else ''}

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

        result = self.client.generate_content(prompt)

        if result['success']:
            return {
                'summary': result['text'],
                'tokens': result['tokens'],
                'success': True
            }
        else:
            return {
                'summary': f"生成失败: {result.get('error', '未知错误')}",
                'tokens': 0,
                'success': False,
                'error': result.get('error', '未知错误')
            }

    def generate_final_summary(self, summaries: List[Dict], author_name: str,
                               custom_prompt: str = None) -> Dict:
        """
        生成最终汇总报告（知识库型）

        Args:
            summaries: 摘要列表 [{'title': '', 'summary': ''}, ...]
            author_name: 作者名称
            custom_prompt: 自定义汇总提示词

        Returns:
            {'report': '汇总报告', 'tokens': int}
        """
        # 构建摘要汇总文本
        summaries_text = ""
        for i, item in enumerate(summaries, 1):
            summaries_text += f"\n## 视频 {i}: {item['title']}\n{item['summary']}\n"

        default_prompt = f"""你是专业的视频内容分析师，擅长将多个视频内容转化为结构化的知识库笔记。请基于以下视频字幕的知识库笔记，生成一份全面的作者内容分析报告。

作者: {author_name}
视频数量: {len(summaries)}

## 各视频知识库笔记

{summaries_text}

---

请严格按照以下结构生成分析报告（使用 Markdown 格式）：

# {author_name} 视频内容分析报告

## 📋 作者概述
- **内容领域/主题**: [作者主要关注的内容领域]
- **创作风格特点**: [叙述方式、表达风格、视频节奏等]
- **目标受众分析**: [主要面向哪类人群]
- **内容更新频率**: [从视频数量推断更新规律]

## 🎯 核心主题汇总
列出作者最常讨论的3-5个核心主题，每个主题包括：
- **主题名称**: [主题]
- **讨论频次**: [高/中/低]
- **代表性观点**: [作者在该主题上的核心立场]
- **相关视频**: [涉及该主题的视频]

## 💡 观点倾向与思维方式
- **主要观点和立场**: [作者的核心信念和价值取向]
- **论证风格**: [数据驱动/经验分享/理论分析/情感共鸣]
- **独特见解**: [作者区别于他人的独特视角]
- **可能的认知偏差**: [客观分析作者可能存在的偏见]

## 📊 内容特色分析
### 标题风格
- 命名规律: [如：设问式/数字式/热点式]
- 关键词偏好: [常使用的关键词类型]

### 叙述方式
- 开头风格: [如何引入话题]
- 结构模式: [层层递进/并列式/故事型]
- 结尾风格: [总结升华/留白思考/行动号召]

### 个性化元素
- 口头禅/标志性表达
- 常用案例/类比
- 个性化视觉/音频元素（如有提及）

## 🌟 代表性内容提炼
### 高价值视频（2-3个）
- **视频标题**: [标题]
  - 核心价值: [为什么值得看]
  - 关键收获: [观众能获得什么]
  - 推荐指数: ★★★★★

### 金句/观点汇总（跨视频）
[从所有视频中提取出的最值得记录的句子和观点]

## 📈 内容趋势分析
- **内容演进**: [作者的内容风格/主题随时间的变化]
- **当前热点**: [作者最近关注的话题]
- **未来展望**: [基于内容趋势的预测]

## 🎓 学习价值评估
- **新颖性**: ★★★★★ (内容是否独特新颖)
- **实用性**: ★★★★★ (是否可落地应用)
- **深度**: ★★★★★ (思考深度如何)
- **系统性**: ★★★★★ (知识体系是否完整)
- **推荐收藏**: [是/否]

## 👥 适合人群
[列出最适合观看/学习这个UP主内容的人群类型]

## 📚 延伸学习建议
基于作者的内容，推荐：
- 相关主题的深入学习方向
- 可以互补的其他作者/资源
- 实践建议

---
请确保报告内容详实、结构清晰，每个部分都有实质内容。尽量引用具体视频中的例子来支撑分析。"""

        prompt = custom_prompt or default_prompt
        result = self.client.generate_content(prompt)

        if result['success']:
            return {
                'report': result['text'],
                'tokens': result['tokens'],
                'success': True
            }
        else:
            return {
                'report': f"生成失败: {result.get('error', '未知错误')}",
                'tokens': 0,
                'success': False,
                'error': result.get('error', '未知错误')
            }


# ==================== 主处理逻辑 ====================

def process_video_analysis_file(video_analysis_file: Path, index: int, total: int,
                                 csv_data: Dict[str, Dict] = None) -> Dict:
    """
    处理视频分析文件（直接读取已有的分析结果，无需再次调用 Gemini）

    Args:
        video_analysis_file: 视频分析 markdown 文件路径
        index: 当前索引
        total: 总数
        csv_data: CSV 数据字典

    Returns:
        处理结果字典
    """
    result = {
        'index': index,
        'title': '',
        'success': False,
        'summary': '',
        'error': None,
        'is_video_analysis': True  # 标记为视频分析类型
    }

    try:
        # 提取标题
        title = video_analysis_file.stem.replace('_视频分析', '')
        result['title'] = title

        with print_lock:
            print(f"[{index}/{total}] 📖 读取视频分析: {title[:50]}")

        # 读取文件内容
        with open(video_analysis_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content:
            result['error'] = '文件内容为空'
            return result

        # 视频分析文件已经是完整的 Markdown 格式，直接作为摘要
        result['summary'] = content
        result['success'] = True

        with print_lock:
            print(f"   └─ ✅ 成功")

    except Exception as e:
        result['error'] = str(e)
        with print_lock:
            print(f"   └─ ❌ 失败: {str(e)[:50]}")

    return result


def process_single_video(srt_file: Path, index: int, total: int, model: str, api_key: str,
                        csv_data: Dict[str, Dict] = None) -> Dict:
    """
    处理单个视频字幕（线程安全，用于并发）

    Returns:
        处理结果字典
    """
    video_start_time = time.time()
    title = srt_file.stem

    # 线程安全的打印
    with print_lock:
        print(f"\n{'='*60}")
        print(f"[线程 {threading.current_thread().name}] [{index}/{total}] 处理: {title}")
        print(f"{'='*60}")

    try:
        # 转换 SRT 为文本
        srt_text = srt_to_text(srt_file)

        with print_lock:
            print(f"📄 文本长度: {len(srt_text):,} 字符")
            print(f"🤖 正在调用 Gemini API...")

        # 每个线程创建自己的客户端
        summarizer = GeminiSummarizer(model=model, api_key=api_key)
        result = summarizer.generate_summary(srt_text, title)

        video_elapsed = time.time() - video_start_time

        if result['success']:
            input_tokens = result.get('input_tokens', 0)
            output_tokens = result.get('output_tokens', 0)
            total_tokens_used = result['tokens']

            with print_lock:
                print(f"  ✅ 成功!")
                print(f"  📊 Tokens: 输入 {input_tokens:,} | 输出 {output_tokens:,} | 总计 {total_tokens_used:,}")
                print(f"  📝 摘要长度: {len(result['summary']):,} 字符")
                print(f"  ⏱️  耗时: {video_elapsed:.2f}秒")

            return {
                'title': title,
                'summary': result['summary'],
                'file': srt_file.name,
                'index': index,
                'success': True,
                'tokens': total_tokens_used,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
        else:
            with print_lock:
                print(f"  ❌ 失败: {result.get('error', '未知错误')}")
                print(f"  ⏱️  耗时: {video_elapsed:.2f}秒")

            return {
                'title': title,
                'summary': f"**处理失败**: {result.get('error', '未知错误')}",
                'file': srt_file.name,
                'index': index,
                'success': False,
                'failed': True,
                'error': result.get('error', '未知错误')
            }

    except Exception as e:
        video_elapsed = time.time() - video_start_time
        with print_lock:
            print(f"  ❌ 异常: {str(e)}")
            print(f"  ⏱️  耗时: {video_elapsed:.2f}秒")

        return {
            'title': title,
            'summary': f"**处理异常**: {str(e)}",
            'file': srt_file.name,
            'index': index,
            'success': False,
            'failed': True,
            'error': str(e)
        }


def load_existing_results(report_path: Path) -> set:
    """从现有报告中加载已处理的视频标题"""
    processed_titles = set()
    if not report_path.exists():
        return processed_titles

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 查找所有 ### 标题（视频标题）
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('### ') and not line.startswith('### 📹'):
                    title = line[4:].strip()
                    processed_titles.add(title)
    except Exception as e:
        print(f"⚠️ 读取现有报告失败: {e}")

    return processed_titles


def process_subtitles(subtitle_dir: str, model: str = 'flash-lite',
                      custom_prompt: str = None, max_workers: int = 3,
                      incremental: bool = False, append: bool = False) -> tuple:
    """
    处理字幕文件夹，生成摘要和汇总报告（支持并发）

    Args:
        subtitle_dir: 字幕文件夹路径
        model: Gemini 模型
        custom_prompt: 自定义汇总提示词
        max_workers: 最大并发数（默认3）
        incremental: 增量模式，跳过已处理的视频
        append: 追加模式，保留已有结果

    Returns:
        (成功数量, 失败数量, 汇总报告路径)
    """
    subtitle_path = Path(subtitle_dir)

    if not subtitle_path.is_dir():
        print(f"❌ 目录不存在: {subtitle_path}")
        return 0, 0, None

    # 获取作者名
    author_name = subtitle_path.name
    print(f"📂 作者: {author_name}")
    print(f"📁 目录: {subtitle_path}")

    # 查找并读取汇总 MD 文件中的视频信息
    summary_md_path = find_summary_md(subtitle_path)
    video_info_map = {}
    if summary_md_path:
        print(f"📋 读取视频信息: {summary_md_path.name}")
        video_info_map = parse_summary_md(summary_md_path)
        print(f"   找到 {len(video_info_map)} 个视频信息")
    else:
        print(f"⚠️  未找到汇总 MD 文件，将不显示视频详细信息")

    # 查找所有 SRT 文件和视频分析文件
    all_srt_files = list(subtitle_path.glob("*.srt"))
    video_analysis_files = list(subtitle_path.glob("*_视频分析.md"))

    if not all_srt_files and not video_analysis_files:
        print(f"❌ 未找到 SRT 文件或视频分析文件")
        return 0, 0, None

    # 统计文件类型
    file_count = len(all_srt_files) + len(video_analysis_files)
    if all_srt_files:
        print(f"📄 找到 {len(all_srt_files)} 个字幕文件")
    if video_analysis_files:
        print(f"🎬 找到 {len(video_analysis_files)} 个视频分析文件")
    print(f"📊 共计 {file_count} 个文件需要处理")

    # 报告文件路径
    output_dir = subtitle_path.parent
    report_path = output_dir / f"{author_name}_AI总结.md"

    # 增量模式：跳过已处理的视频
    srt_files = all_srt_files
    existing_results = []

    if incremental or append:
        processed_titles = load_existing_results(report_path)
        if processed_titles:
            print(f"📋 已处理 {len(processed_titles)} 个视频（增量模式）")

            # 过滤掉已处理的 SRT 文件
            new_srt_files = []
            for srt_file in all_srt_files:
                title = srt_file.stem
                if title not in processed_titles:
                    new_srt_files.append(srt_file)
                else:
                    print(f"   ⏭️  跳过 SRT: {title}")

            srt_files = new_srt_files

            # 过滤掉已处理的视频分析文件
            new_video_files = []
            for video_file in video_analysis_files:
                title = video_file.stem.replace('_视频分析', '')
                if title not in processed_titles:
                    new_video_files.append(video_file)
                else:
                    print(f"   ⏭️  跳过视频分析: {title}")

            video_analysis_files = new_video_files

            if append and report_path.exists():
                # 读取已有结果用于追加
                existing_results = parse_existing_report_results(report_path)

    # 合并所有待处理文件
    all_files = srt_files + video_analysis_files

    if not all_files:
        print("ℹ️ 没有需要处理的新视频")
        if append and existing_results:
            print(f"   保留已有的 {len(existing_results)} 个结果")
        return 0, 0, report_path

    print(f"📄 待处理 {len(all_files)} 个文件（SRT: {len(srt_files)}, 视频分析: {len(video_analysis_files)}）")
    print(f"⚡ 并发模式: {max_workers} 个线程同时处理")
    print("=" * 60)

    # 获取 API Key
    api_key = get_api_key()
    if not api_key:
        print("❌ 未找到 API Key")
        return 0, 0, None

    # 开始计时
    start_time = time.time()

    # 线程安全的结果存储
    results_lock = threading.Lock()
    all_results = []

    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Worker") as executor:
        # 提交所有任务
        futures = []
        for i, file_path in enumerate(all_files, 1):
            # 判断文件类型
            is_video_analysis = file_path.suffix == '.md' and '_视频分析' in file_path.stem

            if is_video_analysis:
                # 视频分析文件：直接读取内容，无需再次调用 Gemini
                future = executor.submit(process_video_analysis_file, file_path, i, len(all_files), video_info_map)
            else:
                # SRT 文件：调用 Gemini 生成摘要
                future = executor.submit(process_single_video, file_path, i, len(all_files), model, api_key, video_info_map)
            futures.append(future)

        # 收集结果
        for future in futures:
            result = future.result()
            with results_lock:
                all_results.append(result)
            # 每处理完一个就保存进度
            with results_lock:
                temp_results = list(all_results)
            _save_progress(report_path, author_name, all_files, temp_results, video_info_map, existing_results)

    # 按原始顺序排序结果
    all_results.sort(key=lambda x: x['index'])

    # 合并已有结果（追加模式）
    all_summaries = existing_results + all_results

    # 统计结果
    summaries = []
    success_count = 0
    fail_count = 0
    total_tokens = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for r in all_summaries:
        summaries.append(r)
        if r.get('success'):
            success_count += 1
            total_tokens += r.get('tokens', 0)
            total_input_tokens += r.get('input_tokens', 0)
            total_output_tokens += r.get('output_tokens', 0)
        else:
            fail_count += 1

    # 生成最终汇总报告
    print("\n" + "=" * 60)
    print(f"📝 生成最终汇总报告...")

    # 创建 summarizer 用于生成总报告
    summarizer = GeminiSummarizer(model=model, api_key=api_key)

    # 过滤出成功的摘要用于生成总报告
    successful_summaries = [s for s in summaries if not s.get('failed')]
    final_result = summarizer.generate_final_summary(successful_summaries, author_name, custom_prompt)

    # 保存最终报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# {author_name} 视频内容分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**视频数量**: {len(all_summaries)}\n\n")
        f.write(f"**成功处理**: {success_count}\n\n")
        f.write(f"**使用模型**: {summarizer.model_name}\n\n")
        f.write(f"**SDK 版本**: {'新版 google.genai' if USE_NEW_SDK else '旧版 google.generativeai'}\n\n")
        f.write(f"**Token 统计**: 输入 {total_input_tokens:,} | 输出 {total_output_tokens:,} | 总计 {total_tokens:,}\n\n")
        f.write("---\n\n")

        if final_result['success']:
            f.write(final_result['report'])
        else:
            f.write(f"❌ 报告生成失败: {final_result.get('error', '未知错误')}")

        f.write("\n\n---\n\n")
        f.write("## 附录: 各视频摘要\n\n")

        for item in summaries:
            # 添加视频信息头部
            title = item['title']
            video_info = None
            if video_info_map:
                # 尝试匹配视频信息
                for info_title, info in video_info_map.items():
                    if title in info_title or info_title in title:
                        video_info = info
                        break

            if video_info:
                f.write(format_video_info_header(video_info, item['file']))

            # 标记分析类型
            if item.get('is_video_analysis'):
                f.write(f"### {title} 🎬\n\n")
                f.write(f"*📌 来源: Gemini 视频分析（无字幕备选方案）*\n\n")
            else:
                f.write(f"### {title}\n\n")

            f.write(f"{item['summary']}\n\n")
            f.write(f"*来源文件: {item['file']}*\n\n")

    print(f"✅ 最终报告已保存: {report_path}")

    # 最终统计
    total_elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"📊 处理完成!")
    print(f"  成功: {success_count} | 失败: {fail_count} | 总计: {len(all_summaries)}")
    if existing_results:
        print(f"  (已有: {len(existing_results)} | 新处理: {len(all_results)})")
    print(f"  总耗时: {total_elapsed:.2f}秒")
    if len(all_summaries) > 0:
        print(f"  平均每视频: {total_elapsed/len(all_summaries):.2f}秒")
    print(f"📊 Token 统计:")
    print(f"  输入 Tokens: {total_input_tokens:,}")
    print(f"  输出 Tokens: {total_output_tokens:,}")
    print(f"  总计 Tokens: {total_tokens:,}")

    return success_count, fail_count, report_path


def _save_progress(report_path: Path, author_name: str, srt_files: list, results: list,
                   video_info_map: dict = None, existing_results: list = None):
    """保存当前进度到文件"""
    all_results = (existing_results or []) + results

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# {author_name} 视频内容分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**视频数量**: {len(all_results)}\n\n")

        # 统计当前进度
        current_success = sum(1 for r in all_results if r.get('success'))
        current_fail = sum(1 for r in all_results if not r.get('success'))
        current_tokens = sum(r.get('tokens', 0) for r in all_results if r.get('success'))
        current_input = sum(r.get('input_tokens', 0) for r in all_results if r.get('success'))
        current_output = sum(r.get('output_tokens', 0) for r in all_results if r.get('success'))

        f.write(f"**已处理**: {len(all_results)}\n\n")
        f.write(f"**成功**: {current_success} | **失败**: {current_fail}\n\n")
        f.write(f"**Token**: 输入 {current_input:,} | 输出 {current_output:,} | 总计 {current_tokens:,}\n\n")
        f.write("---\n\n")
        f.write("## 各视频摘要（按处理顺序）\n\n")

        for item in all_results:
            # 添加视频信息头部
            title = item['title']
            video_info = None
            if video_info_map:
                # 尝试匹配视频信息
                for info_title, info in video_info_map.items():
                    if title in info_title or info_title in title:
                        video_info = info
                        break

            if video_info:
                f.write(format_video_info_header(video_info, item['file']))

            f.write(f"### {title}\n\n")
            f.write(f"{item['summary']}\n\n")
            f.write(f"*来源文件: {item['file']}*\n\n")

        if current_fail > 0:
            f.write("---\n\n")
            f.write("## 失败列表\n\n")
            for item in results:
                if item.get('failed'):
                    f.write(f"- **{item['title']}**: {item.get('error', '未知错误')}\n")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="使用 Gemini API 批量生成字幕摘要和汇总报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 处理指定作者的字幕文件夹
    python gemini_subtitle_summary.py "output/subtitles/小天fotos"

    # 指定并发数（默认3）
    python gemini_subtitle_summary.py "output/subtitles/小天fotos" -j 5

    # 指定Gemini模型
    python gemini_subtitle_summary.py "output/subtitles/小天fotos" --model flash-lite
        """
    )

    parser.add_argument('subtitle_dir', help='字幕文件夹路径（作者文件夹）')
    parser.add_argument('-m', '--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('-j', '--jobs', type=int, default=3,
                        help='并发处理数（默认: 3）')
    parser.add_argument('-p', '--prompt', help='自定义汇总提示词')
    parser.add_argument('--api-key', help='Gemini API Key（覆盖配置文件）')
    parser.add_argument('-i', '--incremental', action='store_true',
                        help='增量模式：跳过已处理的视频')
    parser.add_argument('-a', '--append', action='store_true',
                        help='追加模式：保留已有结果，只处理新视频')

    args = parser.parse_args()

    # 处理字幕
    process_subtitles(args.subtitle_dir, args.model, args.prompt, args.jobs,
                     incremental=args.incremental, append=args.append)


if __name__ == "__main__":
    main()
