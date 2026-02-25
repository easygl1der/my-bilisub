#!/usr/bin/env python3
"""
简化的字幕分析工具
功能：
1. 读取字幕文件
2. 生成书面文稿
3. 提取论点论据（非新闻类）或新闻要点（新闻类）
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Dict


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


def get_api_key() -> str:
    """获取 Gemini API Key (优先级: 配置文件 > 环境变量)"""
    # 1. 优先从配置文件读取
    try:
        # 获取项目根目录 (analysis/ 的父目录)
        project_root = Path(__file__).parent.parent
        config_path = project_root / 'config'
        sys.path.insert(0, str(config_path))
        from config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except (ImportError, FileNotFoundError):
        pass

    # 2. 其次从环境变量读取
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    return None


class GeminiClient:
    """Gemini API 客户端（兼容新旧 SDK）"""

    def __init__(self, model: str = 'flash-lite', api_key: str = None):
        self.api_key = api_key or get_api_key()
        self.model_name = {
            'flash-lite': 'gemini-2.5-flash-lite',
            'flash': 'gemini-2.5-flash',
            'pro': 'gemini-2.5-pro',
        }.get(model, 'gemini-2.5-flash-lite')

        if not self.api_key:
            raise ValueError("未找到 Gemini API Key")

        if self.use_new_sdk:
            # 新 SDK
            self.client = genai.Client(api_key=self.api_key)
        else:
            # 旧 SDK
            import google.generativeai as genai_old
            genai_old.configure(api_key=self.api_key)

    @property
    def use_new_sdk(self):
        return USE_NEW_SDK

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


def detect_video_style(text: str, title: str = "") -> str:
    """
    检测视频风格类型

    Args:
        text: 字幕文本
        title: 视频标题

    Returns:
        视频风格类型 ('news' 或 'non_news')
    """
    # 新闻类关键词
    news_keywords = ['新闻', '报道', '事件', '时事', '热点', '突发', '最新', '消息', '通报']

    text_lower = text.lower()
    title_lower = title.lower() if title else ''

    # 检查关键词
    for keyword in news_keywords:
        if keyword in text_lower or keyword in title_lower:
            return 'news'

    return 'non_news'


def generate_summary(text: str, title: str = "", model: str = 'flash-lite') -> Dict:
    """
    生成视频摘要（简化版本，用于兼容旧代码）

    Args:
        text: 字幕文本或原始SRT内容
        title: 视频标题
        model: Gemini 模型

    Returns:
        {'summary': '摘要内容', 'tokens': int, 'input_tokens': int, 'output_tokens': int, 'success': bool}
    """
    client = GeminiClient(model=model)

    # 检测风格
    video_style = detect_video_style(text, title)

    # 检测是否为对话式
    is_dialogue = ('说' in text and '问' in text) or ('回答' in text) or ('采访' in title)

    # 判断是否为 SRT 格式（包含时间戳）
    is_srt = '-->' in text

    # 如果是 SRT 格式，先解析成纯文本
    if is_srt:
        # 简单去除时间戳和序号
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            # 跳过时间戳行和序号行
            if '-->' in line or line.strip().isdigit():
                continue
            # 跳过空行
            if not line.strip():
                continue
            clean_lines.append(line.strip())
        text = ' '.join(clean_lines)

    # 生成分析提示词
    if video_style == 'news':
        prompt = f"""请分析以下视频内容（新闻类），生成简洁的摘要。

视频标题：{title if title else "无标题"}

字幕内容：
{text[:10000]}

【重要输出要求】
1. 严格按照以下格式输出，不要添加任何其他内容
2. 不要输出任何开场白、结束语或解释性文字
3. 直接输出markdown格式的内容
4. 新闻要点必须按照固定格式列出

输出格式：

# 视频摘要

## 📋 核心内容
[用100-200字概括新闻的核心事件]

## 📰 主要新闻要点
1. **事件**: [事件名称] - **关键信息**: [简要说明]
2. **事件**: [事件名称] - **关键信息**: [简要说明]

---
（根据实际内容列出所有要点，每点一行）"""
    else:
        prompt = f"""请分析以下视频内容，生成结构化摘要。

视频标题：{title if title else "无标题"}
{'内容类型: 对话式' if is_dialogue else '内容类型: 叙述式'}

字幕内容：
{text[:10000]}

【重要输出要求】
1. 严格按照以下格式输出，不要添加任何其他内容
2. 不要输出任何开场白、结束语或解释性文字
3. 直接输出markdown格式的内容
4. 观点必须按照固定格式列出

输出格式：

# 视频摘要

## 📖 核心主题
[一句话概括视频的核心内容]

## 🎯 主要观点
1. **观点**: [核心观点]
   - **论据**: [支持论据]
2. **观点**: [核心观点]
   - **论据**: [支持论据]

---
（根据实际内容列出所有观点，每点一行）

## 💎 金句
- [精彩句子1]
- [精彩句子2]
- [精彩句子3]"""

    result = client.generate_content(prompt)

    if result['success']:
        return {
            'summary': result['text'],
            'tokens': result['tokens'],
            'input_tokens': result['input_tokens'],
            'output_tokens': result['output_tokens'],
            'success': True
        }
    else:
        return {
            'summary': f"生成失败: {result.get('error', '未知错误')}",
            'tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'success': False,
            'error': result.get('error', '未知错误')
        }


# 为了兼容旧代码，创建一个 GeminiSummarizer 类
class GeminiSummarizer:
    """
    兼容类，用于保持与旧代码的兼容性
    """
    def __init__(self, model: str = 'flash-lite'):
        self.model = model
        self.client = GeminiClient(model=model)

    def generate_summary(self, text: str, title: str = "") -> Dict:
        """调用全局 generate_summary 函数"""
        return generate_summary(text, title, self.model)


def generate_written_script(text: str, title: str = "", is_dialogue: bool = False) -> str:
    """
    生成书面文稿

    Args:
        text: 字幕文本
        title: 视频标题
        is_dialogue: 是否是对话式

    Returns:
        书面文稿
    """
    if is_dialogue:
        # 对话式：提取人物对话
        prompt = f"""请将以下字幕内容整理成结构化的对话记录，提取人物并标记对话内容。

视频标题：{title if title else "无标题"}

字幕内容：
{text}

【重要输出要求】
1. 严格按照以下格式输出，不要添加任何其他内容
2. 不要输出开场白、结束语或解释性文字
3. 识别并提取不同人物的对话
4. 保持对话的完整性
5. 去除重复的对话
6. 使用简洁的语言表达

输出格式：

## 对话记录

### 人物A
[对话内容1]

[对话内容2]

### 人物B
[对话内容1]

[对话内容2]

---
（根据实际内容列出所有人物对话）"""
    else:
        # 非对话式：生成标准的书面文稿
        prompt = f"""请将以下字幕内容整理成精炼的书面表达文稿。

视频标题：{title if title else "无标题"}

字幕内容：
{text}

【重要输出要求】
1. 去除所有口语化冗余（如"那个"、"就是"、"然后"等）
2. 使用正式、结构化的书面语言
3. 保留核心信息和逻辑链条
4. 适合作为模型训练的语言材料
5. 字数控制在原文的30%-50%
6. 保持内容的完整性和准确性
7. 按照段落组织内容，使用适当的连接词
8. 不要添加任何开场白或结束语，直接输出文稿内容

请直接输出书面文稿："""

    return prompt


def generate_analysis(prompt: str, client: GeminiClient) -> Dict:
    """
    使用 Gemini 进行分析

    Args:
        prompt: 分析提示词
        client: Gemini 客户端

    Returns:
        分析结果
    """
    result = client.generate_content(prompt)

    if result['success']:
        return {
            'content': result['text'],
            'tokens': result['tokens'],
            'input_tokens': result['input_tokens'],
            'output_tokens': result['output_tokens'],
            'success': True
        }
    else:
        return {
            'content': f"分析失败: {result.get('error', '未知错误')}",
            'tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'success': False,
            'error': result.get('error', '未知错误')
        }


def analyze_subtitle_file(srt_file: Path, output_dir: Path, model: str = 'flash-lite') -> Dict:
    """
    分析单个字幕文件

    Args:
        srt_file: SRT 文件路径
        output_dir: 输出目录
        model: 使用的模型

    Returns:
        分析结果
    """
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 提取标题
    title = srt_file.stem

    # 检测视频风格
    srt_text = srt_to_text(srt_file)
    video_style = detect_video_style(srt_text, title)
    print(f"📄 文件: {title}")
    print(f"🎭 风格: {'新闻类' if video_style == 'news' else '非新闻类'}")

    # 判断是否为对话式
    is_dialogue = ('说' in srt_text and '问' in srt_text) or ('回答' in srt_text) or ('采访' in title)

    # 创建 Gemini 客户端
    client = GeminiClient(model=model)

    # 生成书面文稿
    print(f"📝 生成书面文稿...")
    written_script_prompt = generate_written_script(srt_text, title, is_dialogue)
    written_script_result = generate_analysis(written_script_prompt, client)

    if not written_script_result['success']:
        return {
            'title': title,
            'srt_file': srt_file.name,
            'error': written_script_result.get('error', '书面文稿生成失败'),
            'style': video_style,
            'dialogue': is_dialogue
        }

    # 生成分析内容
    if video_style == 'news':
        # 新闻类：提取新闻要点
        analysis_prompt = f"""请分析以下书面文稿，提取所有新闻要点。

视频标题：{title}

书面文稿：
{written_script_result['content']}

【重要输出要求】
1. 严格按照以下格式输出，不要添加任何其他内容
2. 不要输出开场白、结束语或解释性文字
3. 列出所有识别到的新闻要点，要点之间不要重复
4. 每个要点包含6个要素，提取完整信息不要遗漏
5. 使用markdown格式输出

输出格式：

## 新闻要点

### 要点 1
- **事件**: [事件名称]
- **时间**: [发生时间]
- **地点**: [事件地点]
- **涉及人物/机构**: [相关方]
- **关键信息**: [最重要的信息]
- **影响/结果**: [产生的影响或结果]

### 要点 2
- **事件**: [事件名称]
- **时间**: [发生时间]
- **地点**: [事件地点]
- **涉及人物/机构**: [相关方]
- **关键信息**: [最重要的信息]
- **影响/结果**: [产生的影响或结果]

---
（根据实际内容列出所有新闻要点，每点一个二级标题）"""
    else:
        # 非新闻类：提取论点论据
        analysis_prompt = f"""请分析以下书面文稿，提取所有论点和论据。

视频标题：{title}

书面文稿：
{written_script_result['content']}

【重要输出要求】
1. 严格按照以下格式输出，不要添加任何其他内容
2. 不要输出开场白、结束语或解释性文字
3. 列出所有识别到的论点，每个论点至少列出一个论据
4. 论据之间不要重复
5. 对论据的可信度进行评估
6. 使用markdown格式输出

输出格式：

## 论点与论据

### 论点 1
- **论点**: [核心观点]
- **论据1**: [支持论据1]
- **论据2**: [支持论据2]
- **论据3**: [支持论据3（如有）]
- **可信度**: [高/中/低]

### 论点 2
- **论点**: [核心观点]
- **论据1**: [支持论据1]
- **论据2**: [支持论据2]
- **论据3**: [支持论据3（如有）]
- **可信度**: [高/中/低]

---
（根据实际内容列出所有论点，每点一个二级标题）"""

    analysis_result = generate_analysis(analysis_prompt, client)

    # 保存结果到文件
    output_file = output_dir / f"{title}_分析结果.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {title} 字幕分析报告\n\n")
        f.write(f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**视频风格**: {'新闻类' if video_style == 'news' else '非新闻类'}\n")
        f.write(f"**对话式**: {'是' if is_dialogue else '否'}\n")
        f.write(f"**使用模型**: {model}\n")
        f.write(f"**Token统计**: 输入 {written_script_result['input_tokens']:,} | 输出 {written_script_result['output_tokens']:,} | 总计 {written_script_result['tokens']:,}\n\n")
        f.write("---\n\n")

        # 书面文稿
        f.write("## 📝 书面文稿\n\n")
        f.write(written_script_result['content'])
        f.write("\n\n")

        # 分析结果
        f.write("## 📊 分析结果\n\n")
        if analysis_result['success']:
            f.write(analysis_result['content'])
            f.write(f"\n\n**Token统计**: 输入 {analysis_result['input_tokens']:,} | 输出 {analysis_result['output_tokens']:,} | 总计 {analysis_result['tokens']:,}")
        else:
            f.write(f"❌ 分析失败: {analysis_result.get('error', '未知错误')}")

        f.write("\n\n---\n\n")
        f.write(f"**源文件**: {srt_file.name}\n")

    print(f"  ✅ 分析完成，结果已保存到: {output_file}")
    print(f"  📊 Token使用: 输入 {written_script_result['input_tokens']:,} + {analysis_result['input_tokens']:,} = {written_script_result['input_tokens'] + analysis_result['input_tokens']:,}")
    print(f"  📝 Token输出: 输出 {written_script_result['output_tokens']:,} + {analysis_result['output_tokens']:,} = {written_script_result['output_tokens'] + analysis_result['output_tokens']:,}")

    return {
        'title': title,
        'srt_file': srt_file.name,
        'output_file': str(output_file),
        'style': video_style,
        'dialogue': is_dialogue,
        'success': True,
        'tokens': written_script_result['tokens'] + analysis_result['tokens']
    }


def main():
    parser = argparse.ArgumentParser(
        description="简化的字幕分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 分析单个字幕文件
    python subtitle_analyzer.py -i video.srt -o output/

    # 分析整个文件夹
    python subtitle_analyzer.py -d /path/to/subtitles -o output/

    # 指定模型
    python subtitle_analyzer.py -i video.srt -o output/ -m flash
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input', help='输入 SRT 文件路径')
    group.add_argument('-d', '--directory', help='输入字幕文件夹路径')

    parser.add_argument('-o', '--output', required=True, help='输出目录路径')
    parser.add_argument('-m', '--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output)

    if args.input:
        # 分析单个文件
        srt_file = Path(args.input)
        if not srt_file.exists():
            print(f"❌ 文件不存在: {srt_file}")
            return

        if not srt_file.suffix.lower() == '.srt':
            print(f"❌ 不支持的文件格式: {srt_file.suffix}，请使用 .srt 文件")
            return

        result = analyze_subtitle_file(srt_file, output_dir, args.model)

        print(f"\n{'='*60}")
        print(f"📊 分析完成!")
        print(f"  文件: {result['title']}")
        print(f"  状态: {'成功' if result['success'] else '失败'}")
        if result['success']:
            print(f"  输出: {result['output_file']}")
            print(f"  Token: {result['tokens']:,}")
        else:
            print(f"  错误: {result.get('error', '未知错误')}")

    elif args.directory:
        # 分析整个文件夹
        subtitle_dir = Path(args.directory)
        if not subtitle_dir.exists():
            print(f"❌ 文件夹不存在: {subtitle_dir}")
            return

        # 查找所有 SRT 文件
        srt_files = list(subtitle_dir.glob("*.srt"))

        if not srt_files:
            print(f"❌ 未找到 SRT 文件")
            return

        print(f"📁 找到 {len(srt_files)} 个字幕文件")

        # 统计
        success_count = 0
        fail_count = 0
        total_tokens = 0

        # 分析每个文件
        for srt_file in srt_files:
            print(f"\n{'='*60}")
            result = analyze_subtitle_file(srt_file, output_dir, args.model)

            if result['success']:
                success_count += 1
                total_tokens += result['tokens']
            else:
                fail_count += 1

        # 最终统计
        print(f"\n{'='*60}")
        print(f"📊 所有文件分析完成!")
        print(f"  总计: {len(srt_files)}")
        print(f"  成功: {success_count}")
        print(f"  失败: {fail_count}")
        if success_count > 0:
            print(f"  总Token: {total_tokens:,}")
            print(f"  平均Token: {total_tokens//success_count:,}")


if __name__ == "__main__":
    main()