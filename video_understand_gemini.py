#!/usr/bin/env python3
"""
使用 Gemini API 进行视频内容理解

功能：
1. 上传视频到 Gemini Files API
2. 等待视频处理完成
3. 使用 Gemini 2.5 Flash/Pro/Lite 进行视频内容分析
4. 支持模型自动切换（当配额不足时）

使用示例:
    # 分析单个视频（默认使用knowledge模式，输出知识库型笔记）
    python video_understand_gemini.py -video "path/to/video.mp4"

    # 批量分析目录下的视频
    python video_understand_gemini.py -dir "downloaded_videos"

    # 指定模型
    python video_understand_gemini.py -video "video.mp4" --model flash-lite

    # 使用自定义提示词
    python video_understand_gemini.py -video "video.mp4" -p "请总结这个视频的核心观点"

    # 使用其他模式
    python video_understand_gemini.py -video "video.mp4" -m brief      # 简洁总结
    python video_understand_gemini.py -video "video.mp4" -m detailed   # 详细分析
    python video_understand_gemini.py -video "video.mp4" -m transcript # 提取对话
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    import google.generativeai as genai
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
except ImportError:
    # 尝试使用新库
    try:
        from google import genai
        USE_NEW_API = True
    except ImportError:
        print("❌ 未安装 google-generativeai 库")
        print("请运行: pip install google-generativeai")
        sys.exit(1)

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 配置 ====================

# Gemini 模型配置（按免费额度排序）
GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',   # 15 RPM, 1000 RPD
    'flash': 'gemini-2.5-flash',             # 5 RPM, 100 RPD
    'pro': 'gemini-2.5-pro',                 # 10 RPM, 100 RPD
}

# 默认提示词模板
DEFAULT_PROMPTS = {
    'summary': """请用中文详细总结这个视频的主要内容，包括：
1. 视频的主题和核心观点
2. 主要讨论的问题或话题
3. 关键信息和亮点
4. 任何值得注意的细节""",

    'brief': """请用中文简洁总结这个视频的核心内容（200字以内）。""",

    'detailed': """请用中文详细分析这个视频，包括：
1. 视频主题和类型
2. 核心观点和论据
3. 主要内容结构
4. 关键信息和数据
5. 视频的风格特点
6. 目标受众分析
7. 总结评价""",

    'transcript': """请尽可能详细地提取这个视频中的对话和解说内容。""",

    'knowledge': """你是一个专业的视频内容分析师，擅长将视频内容转化为结构化的知识库笔记。请详细分析这个视频，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 视频基本信息
- **视频类型**: [教育课程/知识科普/新闻评论/产品测评/其他]
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
[请提取以下类型的句子，并标注出现的大致时间点]

### 1. 引经据典
- 原句: "..."
- 时间点: MM:SS
- 价值: [为什么值得记录]

### 2. 故事/案例
- 原句/描述: "..."
- 时间点: MM:SS
- 价值: [可学习的表达方式]

### 3. 精辟论据
- 原句: "..."
- 时间点: MM:SS
- 说服力: [为什么有说服力]

### 4. 深刻观点
- 原句: "..."
- 时间点: MM:SS
- 启发性: [带来的思考]

### 5. 好词好句
- 原句: "..."
- 时间点: MM:SS
- 亮点: [表达技巧]

## 📝 书面文稿
[将视频内容整理成精炼的书面表达文稿，要求：
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

## 🔗 相关延伸
[基于视频内容，推荐值得深入了解的相关话题、资料或思考方向]

---
请确保输出结构完整，每个部分都要有实质内容。如果某部分确实不适用，请标注"[不适用]"并说明原因。
""",
}


# ==================== API 配置 ====================

def get_api_key() -> str:
    """
    获取 Gemini API Key

    优先级:
    1. 环境变量 GEMINI_API_KEY
    2. config_api.py 配置文件
    """
    # 1. 尝试从环境变量获取
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # 2. 尝试从 config_api.py 获取
    try:
        from config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


def configure_gemini(api_key: str = None) -> bool:
    """配置 Gemini API"""
    if not api_key:
        api_key = get_api_key()

    if not api_key:
        print("❌ 未找到 Gemini API Key")
        print("\n请通过以下方式之一配置 API Key:")
        print("1. 设置环境变量: export GEMINI_API_KEY='your-key'")
        print("2. 在 config_api.py 中添加:")
        print('   API_CONFIG = {"gemini": {"api_key": "your-key"}}')
        return False

    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"❌ Gemini API 配置失败: {e}")
        return False


# ==================== 视频处理 ====================

class VideoProcessor:
    """Gemini 视频处理器"""

    def __init__(self, model: str = 'flash', api_key: str = None):
        """
        初始化处理器

        Args:
            model: 模型类型 (flash/flash-lite/pro)
            api_key: Gemini API Key
        """
        self.api_key = api_key or get_api_key()
        self.model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash'])
        self.model = model
        self.current_model_name = self.model_name

        if not configure_gemini(self.api_key):
            raise ValueError("无法配置 Gemini API")

    def _switch_model(self) -> bool:
        """切换到下一个可用模型"""
        models = list(GEMINI_MODELS.keys())
        current_idx = models.index(self.model) if self.model in models else 0

        # 尝试切换到下一个模型
        for i in range(current_idx + 1, len(models)):
            new_model = models[i]
            print(f"   └─ 🔄 尝试切换到模型: {GEMINI_MODELS[new_model]}")
            self.current_model_name = GEMINI_MODELS[new_model]
            return True

        return False

    def upload_video(self, video_path: str, timeout: int = 300) -> object:
        """
        上传视频到 Gemini Files API

        Args:
            video_path: 视频文件路径
            timeout: 上传超时时间（秒）

        Returns:
            上传的文件对象，失败返回 None
        """
        video_path = Path(video_path)

        if not video_path.exists():
            print(f"❌ 文件不存在: {video_path}")
            return None

        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"📹 视频文件: {video_path.name}")
        print(f"   └─ 大小: {file_size_mb:.2f} MB")

        # Gemini 文件大小限制
        if file_size_mb > 2000:  # 2GB limit
            print(f"❌ 文件过大 (最大 2GB)")
            return None

        print(f"   └─ 上传中...")

        start_time = time.time()

        try:
            video_file = genai.upload_file(
                path=str(video_path),
                display_name=video_path.name
            )

            elapsed = time.time() - start_time
            print(f"   └─ ✅ 上传完成! ({elapsed:.1f}秒)")
            print(f"   └─ 文件URI: {video_file.uri}")

            return video_file

        except Exception as e:
            print(f"   └─ ❌ 上传失败: {e}")
            return None

    def wait_for_processing(self, video_file: object, check_interval: int = 5, timeout: int = 600) -> bool:
        """
        等待视频处理完成

        Args:
            video_file: Gemini 文件对象
            check_interval: 检查间隔（秒）
            timeout: 超时时间（秒）

        Returns:
            处理成功返回 True，失败返回 False
        """
        print(f"   └─ 等待视频处理...")

        start_time = time.time()

        while True:
            # 获取最新状态
            video_file = genai.get_file(video_file.name)
            state = video_file.state.name

            # 检查超时
            if time.time() - start_time > timeout:
                print(f"   └─ ❌ 处理超时 ({timeout}秒)")
                return False

            if state == "PROCESSING":
                elapsed = time.time() - start_time
                print(f"   └─ ⏳ 处理中... ({elapsed:.0f}秒)", end='\r')
                time.sleep(check_interval)

            elif state == "FAILED":
                print(f"   └─ ❌ 视频处理失败")
                return False

            elif state == "ACTIVE":
                elapsed = time.time() - start_time
                print(f"   └─ ✅ 处理完成! ({elapsed:.1f}秒)")
                return True

    def analyze_video(self, video_file: object, prompt: str, max_retries: int = 2) -> str:
        """
        分析视频内容

        Args:
            video_file: Gemini 文件对象
            prompt: 分析提示词
            max_retries: 最大重试次数（用于模型切换）

        Returns:
            分析结果文本
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"   └─ 🔄 重试 {attempt}/{max_retries}...")

            try:
                print(f"   └─ 使用模型: {self.current_model_name}")
                model = genai.GenerativeModel(self.current_model_name)

                print(f"   └─ 分析中...")

                response = model.generate_content([
                    video_file,
                    prompt
                ])

                return response.text

            except Exception as e:
                error_msg = str(e)

                # 检查是否是配额/限制错误
                if any(keyword in error_msg.lower() for keyword in ['quota', 'limit', 'rate', '429']):
                    print(f"   └─ ⚠️  配额不足或请求受限")

                    if attempt < max_retries and self._switch_model():
                        continue
                    else:
                        return f"❌ 所有模型配额均不足或请求失败: {error_msg}"

                return f"❌ 分析失败: {error_msg}"

        return "❌ 分析失败: 达到最大重试次数"

    def delete_file(self, video_file: object):
        """删除已上传的文件"""
        try:
            genai.delete_file(video_file.name)
            print(f"   └─ 🗑️  已删除上传的文件")
        except Exception as e:
            print(f"   └─ ⚠️  删除文件失败: {e}")


# ==================== 提示词管理 ====================

def get_prompt(mode: str = 'summary', custom_prompt: str = None) -> str:
    """
    获取分析提示词

    Args:
        mode: 预设模式 (summary/brief/detailed/transcript)
        custom_prompt: 自定义提示词

    Returns:
        提示词字符串
    """
    if custom_prompt:
        return custom_prompt

    return DEFAULT_PROMPTS.get(mode, DEFAULT_PROMPTS['summary'])


def list_prompt_modes():
    """列出所有提示词模式"""
    print("\n📝 可用的提示词模式:")
    for mode, prompt in DEFAULT_PROMPTS.items():
        print(f"   - {mode}: {prompt.split(chr(10))[0][:50]}...")


# ==================== 输出管理 ====================

def save_result(video_path: str, result: str, prompt: str, model: str, output_dir: str = "gemini_analysis"):
    """
    保存分析结果

    Args:
        video_path: 视频文件路径
        result: 分析结果
        prompt: 使用的提示词
        model: 使用的模型
        output_dir: 输出目录
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    video_name = Path(video_path).stem
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    result_file = output_path / f"{video_name}_{timestamp}.txt"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f"Gemini 视频分析结果\n")
        f.write(f"{'='*60}\n")
        f.write(f"视频文件: {Path(video_path).name}\n")
        f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"使用模型: {model}\n")
        f.write(f"{'='*60}\n\n")

        f.write(f"提示词:\n{prompt}\n\n")
        f.write(f"{'='*60}\n\n")

        f.write(f"分析结果:\n\n{result}\n")

    return result_file


# ==================== 批量处理 ====================

def batch_analyze(video_dir: str, processor: VideoProcessor, prompt: str,
                  pattern: str = "*.mp4", keep_files: bool = False,
                  output_dir: str = "gemini_analysis"):
    """
    批量分析目录下的视频

    Args:
        video_dir: 视频目录
        processor: VideoProcessor 实例
        prompt: 分析提示词
        pattern: 文件匹配模式
        keep_files: 是否保留上传的文件
        output_dir: 输出目录
    """
    video_dir = Path(video_dir)

    if not video_dir.is_dir():
        print(f"❌ 目录不存在: {video_dir}")
        return

    videos = list(video_dir.rglob(pattern))
    videos += list(video_dir.rglob("*.mov"))
    videos += list(video_dir.rglob("*.avi"))
    videos += list(video_dir.rglob("*.mkv"))
    videos = list(set(videos))  # 去重

    if not videos:
        print(f"❌ 未找到视频文件 ({pattern})")
        return

    print(f"\n📂 找到 {len(videos)} 个视频文件")

    results = []
    success_count = 0
    fail_count = 0

    for i, video_path in enumerate(videos, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(videos)}] 处理: {video_path.name}")
        print(f"{'='*80}")

        result = process_video(str(video_path), processor, prompt, keep_files, output_dir)

        if result and not result.startswith("❌"):
            success_count += 1
        else:
            fail_count += 1

        results.append({
            'video': str(video_path),
            'result': result
        })

        # 避免请求过快
        if i < len(videos):
            time.sleep(2)

    # 打印总结
    print(f"\n{'='*80}")
    print(f"📊 批量处理完成")
    print(f"{'='*80}")
    print(f"总计: {len(videos)} | 成功: {success_count} | 失败: {fail_count}")


def process_video(video_path: str, processor: VideoProcessor, prompt: str,
                  keep_files: bool = False, output_dir: str = "gemini_analysis") -> str:
    """
    处理单个视频

    Args:
        video_path: 视频文件路径
        processor: VideoProcessor 实例
        prompt: 分析提示词
        keep_files: 是否保留上传的文件
        output_dir: 输出目录

    Returns:
        分析结果
    """
    # 上传视频
    video_file = processor.upload_video(video_path)
    if not video_file:
        return None

    # 等待处理
    if not processor.wait_for_processing(video_file):
        processor.delete_file(video_file)
        return None

    # 分析视频
    result = processor.analyze_video(video_file, prompt)

    # 删除上传的文件
    if not keep_files:
        processor.delete_file(video_file)
    else:
        print(f"   └─ 📁 保留上传的文件: {video_file.name}")

    # 保存结果
    if result and not result.startswith("❌"):
        result_file = save_result(video_path, result, prompt, processor.current_model_name, output_dir)
        print(f"   └─ 💾 结果已保存: {result_file.name}")

    return result


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="使用 Gemini API 进行视频内容理解",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析单个视频（默认knowledge模式，输出知识库型笔记）:
   python video_understand_gemini.py -video "path/to/video.mp4"

2. 批量分析目录:
   python video_understand_gemini.py -dir "downloaded_videos"

3. 指定模型:
   python video_understand_gemini.py -video "video.mp4" --model flash-lite

4. 使用不同模式:
   python video_understand_gemini.py -video "video.mp4" -m brief      # 简洁总结
   python video_understand_gemini.py -video "video.mp4" -m detailed   # 详细分析
   python video_understand_gemini.py -video "video.mp4" -m transcript # 提取对话
   python video_understand_gemini.py -video "video.mp4" -m knowledge  # 知识库型（默认）

5. 自定义提示词:
   python video_understand_gemini.py -video "video.mp4" -p "请提取视频中所有人物对话"

6. 保留上传的文件:
   python video_understand_gemini.py -video "video.mp4" --keep
        """
    )

    parser.add_argument('-video', '--video-file', help='视频文件路径')
    parser.add_argument('-dir', '--directory', help='视频文件目录（批量处理）')
    parser.add_argument('-m', '--mode', choices=['summary', 'brief', 'detailed', 'transcript', 'knowledge'],
                        default='summary', help='提示词模式（默认: summary）')
    parser.add_argument('-p', '--prompt', help='自定义提示词（覆盖模式选择）')
    parser.add_argument('--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('-o', '--output', default='gemini_analysis',
                        help='输出目录（默认: gemini_analysis）')
    parser.add_argument('--keep', action='store_true',
                        help='保留上传到 Gemini 的文件')
    parser.add_argument('--list-modes', action='store_true',
                        help='列出所有提示词模式')
    parser.add_argument('--api-key', help='Gemini API Key（覆盖配置文件）')

    args = parser.parse_args()

    # 列出模式
    if args.list_modes:
        list_prompt_modes()
        return

    # 确定处理模式
    if not args.video_file and not args.directory:
        parser.print_help()
        return

    # 初始化处理器
    try:
        processor = VideoProcessor(model=args.model, api_key=args.api_key)
    except ValueError as e:
        print(f"❌ {e}")
        return

    # 获取提示词
    prompt = get_prompt(args.mode, args.prompt)
    print(f"📝 提示词模式: {args.mode}")

    # 处理视频
    if args.video_file:
        print(f"\n{'='*80}")
        print(f"🎬 单视频分析模式")
        print(f"{'='*80}")
        process_video(args.video_file, processor, prompt, args.keep, args.output)

    elif args.directory:
        print(f"\n{'='*80}")
        print(f"📂 批量分析模式")
        print(f"{'='*80}")
        batch_analyze(args.directory, processor, prompt, keep_files=args.keep, output_dir=args.output)

    print(f"\n✅ 完成!")


if __name__ == "__main__":
    main()
