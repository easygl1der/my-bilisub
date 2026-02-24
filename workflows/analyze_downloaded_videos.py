#!/usr/bin/env python3
"""
分析已下载的视频文件

直接分析本地视频文件夹中的视频，不需要重新下载

使用示例:
    # 分析整个文件夹
    python analyze_downloaded_videos.py --dir "downloaded_videos"

    # 分析单个视频
    python analyze_downloaded_videos.py --video "video.mp4"

    # 不生成 SRT（更快）
    python analyze_downloaded_videos.py --dir "downloaded_videos" --no-srt
"""

import os
import sys
import re
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def sanitize_filename(name: str) -> str:
    """清理文件名"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:200]


def get_api_key() -> str:
    """获取 Gemini API Key"""
    # 1. 环境变量
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    # 2. config_api.py
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from config.config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


class VideoAnalyzer:
    """视频分析器"""

    GEMINI_MODELS = {
        'flash-lite': 'gemini-2.5-flash-lite',
        'flash': 'gemini-2.5-flash',
        'pro': 'gemini-2.5-pro',
    }

    def __init__(self, api_key: str, model: str = 'flash-lite'):
        self.api_key = api_key

        try:
            import google.generativeai as genai
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
            genai.configure(api_key=api_key)
            self.genai = genai
            self.model_name = self.GEMINI_MODELS.get(model, self.GEMINI_MODELS['flash-lite'])
        except ImportError:
            print("❌ 未安装 google-generativeai 库")
            raise

    def analyze_video(self, video_path: Path, mode: str = 'knowledge') -> bool:
        """
        分析视频

        Args:
            video_path: 视频文件路径
            mode: 分析模式

        Returns:
            是否成功
        """
        print(f"\n{'='*60}")
        print(f"分析: {video_path.name}")
        print(f"{'='*60}")

        # 检查文件大小
        file_size_mb = video_path.stat().st_size / 1024 / 1024
        print(f"   └─ 大小: {file_size_mb:.1f}MB")

        if file_size_mb > 2000:
            print(f"   └─ ❌ 文件过大 (最大 2GB)")
            return False

        # 上传视频
        print(f"   └─ 📤 上传到 Gemini...")
        try:
            video_file = self.genai.upload_file(path=str(video_path))

            # 等待处理
            print(f"   └─ ⏳ 等待视频处理...")
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = self.genai.get_file(video_file.name)

            if video_file.state.name != "ACTIVE":
                print(f"   └─ ❌ 视频处理失败: {video_file.state.name}")
                self.genai.delete_file(video_file.name)
                return False

            # 分析
            print(f"   └─ 🔄 分析中...")
            model = self.genai.GenerativeModel(self.model_name)
            prompt = self._get_prompt(mode)
            response = model.generate_content([video_file, prompt])

            # 删除上传的文件
            self.genai.delete_file(video_file.name)

            # 保存结果
            output_file = video_path.parent / "analysis.md"
            self._save_result(output_file, video_path.stem, response.text, mode)

            print(f"   └─ ✅ 分析完成")
            return True

        except Exception as e:
            print(f"   └─ ❌ 分析失败: {e}")
            return False

    def transcribe_video(self, video_path: Path, model_size: str = 'base') -> bool:
        """
        转录视频生成 SRT

        Args:
            video_path: 视频文件路径
            model_size: Whisper 模型大小

        Returns:
            是否成功
        """
        try:
            import whisper
        except ImportError:
            print(f"   └─ ❌ 未安装 whisper")
            return False

        print(f"   └─ 🎙️  Whisper 转录... (模型: {model_size})")

        try:
            model = whisper.load_model(model_size)
            result = model.transcribe(str(video_path), language='zh')

            srt_path = video_path.parent / "subtitle.srt"

            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(result['segments'], 1):
                    start_time = timedelta(seconds=segment['start'])
                    end_time = timedelta(seconds=segment['end'])
                    text = segment['text'].strip()

                    f.write(f"{i}\n")
                    f.write(f"{self._format_timedelta(start_time)} --> {self._format_timedelta(end_time)}\n")
                    f.write(f"{text}\n\n")

            print(f"   └─ ✅ 字幕生成完成")
            return True

        except Exception as e:
            print(f"   └─ ❌ 转录失败: {e}")
            return False

    def _format_timedelta(self, td: timedelta) -> str:
        """格式化时间为 SRT 格式"""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def _get_prompt(self, mode: str) -> str:
        """获取分析提示词"""
        if mode == 'knowledge':
            return """你是一个专业的视频内容分析师，擅长将视频内容转化为结构化的知识库笔记。请详细分析这个视频，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 视频基本信息
- **视频类型**: [教育课程/知识科普/新闻评论/产品测评/生活分享/其他]
- **核心主题**: [一句话概括]
- **内容风格**: [干货教程/种草推荐/日常生活/观点分享]

## 📖 视频大意（100-200字）
[用精炼的书面语言概括视频核心内容]

## 🎯 核心观点
[如果视频有明确观点，列出主要论点]

## 💡 亮点与价值
### 独特之处
[这个视频与众不同的地方]

### 实用价值
- **参考性**: [高/中/低] - [说明]

## 🔗 相关延伸
[基于视频内容，推荐值得深入了解的相关话题]

请确保输出结构完整，每个部分都要有实质内容。"""
        else:
            return """请用中文详细总结这个视频的主要内容，包括：
1. 视频的主题和核心观点
2. 主要讨论的问题或话题
3. 关键信息和亮点
4. 任何值得注意的细节"""

    def _save_result(self, output_file: Path, title: str, result: str, mode: str):
        """保存分析结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title} - Gemini 视频分析\n\n")
            f.write(f"## 📌 元信息\n\n")
            f.write(f"| 项目 | 内容 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| **视频文件** | {title} |\n")
            f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
            f.write(f"| **使用模型** | {self.model_name} |\n")
            f.write(f"| **分析模式** | {mode} |\n")
            f.write(f"\n---\n\n")
            f.write(f"## 🤖 AI 分析结果\n\n")
            f.write(result)


def find_videos(directory: Path) -> list:
    """查找目录中的所有视频文件"""
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv']
    videos = []

    for ext in video_extensions:
        videos.extend(directory.rglob(f"*{ext}"))
        videos.extend(directory.rglob(f"*{ext.upper()}"))

    return sorted(list(set(videos)))


def main():
    parser = argparse.ArgumentParser(
        description="分析已下载的视频文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析整个文件夹:
   python analyze_downloaded_videos.py --dir "downloaded_videos"

2. 分析单个视频:
   python analyze_downloaded_videos.py --video "video.mp4"

3. 不生成 SRT:
   python analyze_downloaded_videos.py --dir "videos" --no-srt

4. 限制数量:
   python analyze_downloaded_videos.py --dir "videos" --limit 3
        """
    )

    parser.add_argument('--dir', help='视频文件夹路径')
    parser.add_argument('--video', help='单个视频文件路径')
    parser.add_argument('--no-srt', action='store_true', help='不生成 SRT 字幕')
    parser.add_argument('--analysis-mode', choices=['knowledge', 'summary'],
                       default='knowledge', help='Gemini 分析模式')
    parser.add_argument('--gemini-model', choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite', help='Gemini 模型')
    parser.add_argument('--whisper-model', choices=['tiny', 'base', 'small', 'medium', 'large'],
                       default='base', help='Whisper 模型')
    parser.add_argument('--limit', type=int, help='限制处理数量')

    args = parser.parse_args()

    # 检查 API Key
    api_key = get_api_key()
    if not api_key:
        print("❌ 未配置 Gemini API Key")
        print("\n请通过以下方式之一配置 API Key:")
        print("1. 设置环境变量: export GEMINI_API_KEY='your-key'")
        print("2. 在 config_api.py 中添加:")
        print('   API_CONFIG = {"gemini": {"api_key": "your-key"}}')
        return

    # 初始化分析器
    try:
        analyzer = VideoAnalyzer(api_key, args.gemini_model)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    # 获取视频列表
    videos = []

    if args.video:
        video_path = Path(args.video)
        if video_path.exists():
            videos = [video_path]
        else:
            print(f"❌ 文件不存在: {args.video}")
            return

    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            print(f"❌ 目录不存在: {args.dir}")
            return

        videos = find_videos(dir_path)

    else:
        parser.print_help()
        return

    if not videos:
        print("❌ 未找到视频文件")
        return

    # 限制数量
    if args.limit and args.limit < len(videos):
        videos = videos[:args.limit]
        print(f"⚠️  限制处理数量: {args.limit}")

    print(f"\n📋 找到 {len(videos)} 个视频文件")

    # 处理每个视频
    success = 0
    failed = 0

    for i, video_path in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] ", end='')

        # 检查是否已分析
        analysis_file = video_path.parent / "analysis.md"
        if analysis_file.exists():
            print(f"⏭️  已跳过（已有分析文件）")
            success += 1
            continue

        # Gemini 分析
        if analyzer.analyze_video(video_path, args.analysis_mode):
            success += 1

            # Whisper 转录
            if not args.no_srt:
                analyzer.transcribe_video(video_path, args.whisper_model)
        else:
            failed += 1

        # 避免请求过快
        if i < len(videos):
            time.sleep(2)

    # 总结
    print(f"\n{'='*60}")
    print(f"📊 处理完成")
    print(f"{'='*60}")
    print(f"总计: {len(videos)} | 成功: {success} | 失败: {failed}")


if __name__ == "__main__":
    main()
