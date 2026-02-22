#!/usr/bin/env python3
"""
小红书图文笔记分析工具 - 简化版

功能：
1. 上传图片到 Gemini
2. 使用一个通用提示词，让 AI 自动识别风格并分析
3. 输出结构化的 Markdown 报告

使用示例:
    python xhs_simple_analysis.py --dir "xhs_images/用户名/笔记标题"
    python xhs_simple_analysis.py --user-dir "xhs_images/用户名"
"""

import os
import sys
import time
from pathlib import Path
from typing import List

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import google.generativeai as genai
except ImportError:
    print("❌ 未安装 google-generativeai 库")
    print("请运行: pip install google-generativeai")
    sys.exit(1)


# ==================== 通用提示词 ====================

UNIVERSAL_PROMPT = """你是一个专业的小红书图文笔记分析师。请分析这组图文笔记，输出结构化的分析报告。

## 第一步：识别笔记类型

请首先判断这组笔记属于哪种类型：
- **生活记录**: 日常生活、心情随想、vlog、外出记录
- **金句道理**: 以文字为主，分享人生感悟、道理、语录、文案
- **新闻科普**: 新闻事件、科普知识、行业动态
- **穿搭美妆**: 服装搭配、美妆教程、OOTD、颜值分享
- **美食探店**: 餐厅探店、美食制作、食谱分享
- **旅行攻略**: 旅行攻略、景点推荐、行程分享
- **数码测评**: 数码产品测评、开箱、使用体验
- **学习笔记**: 学习笔记、教程、干货分享
- **健身运动**: 健身教程、运动打卡、减肥塑形
- **情感关系**: 恋爱感悟、情感分析、关系建议

## 第二步：根据类型输出对应分析

请严格按照以下结构输出（保持所有标题和符号）：

## 📋 笔记基本信息
- **笔记类型**: [识别出的类型]
- **核心主题**: [一句话概括主题]
- **作者**: [如果有作者信息]

## 📖 内容概要（150-250字）
[结合图片和文字，用精炼的语言概括笔记核心内容]

## 🎯 核心信息提取
根据笔记类型，提取对应的关键信息：

### 如果是生活记录：
- **场景**: [记录的场景/环境]
- **情绪**: [作者的情绪状态]
- **生活细节**: [关键元素、事件]

### 如果是金句道理：
- **核心观点**: [主要论点]
- **金句提取**: [值得引用的句子]
- **使用建议**: [适用场景]

### 如果是穿搭美妆：
- **单品清单**: [上装/下装/鞋子/配饰]
- **搭配技巧**: [色彩/层次/比例]
- **适合人群**: [体型/肤色/风格]

### 如果是美食探店：
- **店铺信息**: [店名/位置/人均]
- **菜品测评**: [推荐菜品/口味评价]
- **体验感受**: [环境/服务/性价比]

### 如果是旅行攻略：
- **目的地**: [地点]
- **行程建议**: [景点/路线/时间]
- **实用信息**: [交通/住宿/注意事项]

### 如果是数码测评：
- **产品信息**: [名称/型号/价格]
- **优缺点**: [优点和缺点]
- **购买建议**: [是否推荐、适合人群]

### 如果是学习笔记：
- **知识点**: [核心知识要点]
- **方法技巧**: [具体的学习方法]
- **适用人群**: [适合什么人]

### 如果是健身运动：
- **训练内容**: [动作/计划/强度]
- **饮食建议**: [饮食/减脂/增肌]
- **注意事项**: [安全提醒]

### 如果是情感关系：
- **核心观点**: [情感观点/分析]
- **行动建议**: [可操作建议]
- **情感价值**: [共鸣点/启发]

### 如果是新闻科普：
- **关键事实**: [核心事实信息]
- **知识价值**: [有什么值得学习的]
- **可靠性**: [信息来源/可信度]

## 📸 视觉分析
- **图片数量**: {image_count}张
- **图片风格**: [描述图片的整体风格]
- **图文配合**: [文字和图片如何配合]

## 💡 亮点与价值
- **内容亮点**: [这篇笔记的亮点]
- **实用价值**: [★★★★★] - [实用性评估]
- **新颖性**: [★★★★★] - [内容有多新]

## 📝 总结评价
[一句话总结这篇笔记的价值和特色]

---

## 原始文案内容:
{text}

---

请确保：
1. 首先正确识别笔记类型
2. 根据类型输出对应的"核心信息提取"部分
3. 其他部分对所有类型都适用
4. 如果某部分不适用，标注"[不适用]"
"""


# ==================== API 配置 ====================

def get_api_key() -> str:
    """获取 Gemini API Key"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    try:
        sys.path.insert(0, str(Path(__file__).parent))
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
        print("\n请配置环境变量: set GEMINI_API_KEY='your-key'")
        return False

    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"❌ Gemini API 配置失败: {e}")
        return False


# ==================== 分析器 ====================

class XHSAnalyzer:
    """小红书图文分析器 - 简化版"""

    def __init__(self, model: str = 'flash-lite', api_key: str = None):
        self.api_key = api_key or get_api_key()
        self.model_name = f'gemini-2.5-flash-lite' if model == 'flash-lite' else f'gemini-2.5-{model}'

        if not configure_gemini(self.api_key):
            raise ValueError("无法配置 Gemini API")

    def upload_images(self, image_paths: List[Path]) -> List:
        """上传图片到 Gemini"""
        uploaded_files = []

        print(f"\n📤 上传图片到 Gemini...")
        print(f"{'='*60}")

        for i, img_path in enumerate(image_paths, 1):
            print(f"[{i}/{len(image_paths)}] {img_path.name}... ", end='', flush=True)

            try:
                img_file = genai.upload_file(
                    path=str(img_path),
                    display_name=img_path.name
                )

                # 等待处理完成
                while img_file.state.name == "PROCESSING":
                    time.sleep(1)
                    img_file = genai.get_file(img_file.name)

                if img_file.state.name == "ACTIVE":
                    size_mb = img_path.stat().st_size / (1024 * 1024)
                    print(f"✅ ({size_mb:.2f}MB)")
                    uploaded_files.append(img_file)
                else:
                    print(f"❌ 状态: {img_file.state.name}")

            except Exception as e:
                print(f"❌ {e}")

        print(f"{'='*60}")
        print(f"✅ 成功上传 {len(uploaded_files)}/{len(image_paths)} 张图片\n")

        return uploaded_files

    def analyze(self, text: str, image_files: List) -> tuple:
        """分析图文内容"""
        prompt = UNIVERSAL_PROMPT.format(text=text, image_count=len(image_files))

        print(f"🤖 使用模型: {self.model_name}")
        print(f"🔄 正在分析...")

        try:
            model = genai.GenerativeModel(self.model_name)
            contents = image_files + [prompt]

            start_time = time.time()
            response = model.generate_content(contents)
            elapsed = time.time() - start_time

            print(f"✅ 分析完成! ({elapsed:.1f}秒)\n")

            # 提取 token 信息
            token_info = {
                'prompt_tokens': 0,
                'candidates_tokens': 0,
                'total_tokens': 0
            }
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info['prompt_tokens'] = response.usage_metadata.prompt_token_count or 0
                token_info['candidates_tokens'] = response.usage_metadata.candidates_token_count or 0
                token_info['total_tokens'] = response.usage_metadata.total_token_count or 0

            return response.text, token_info

        except Exception as e:
            error_msg = f"❌ 分析失败: {e}"
            print(error_msg)
            return error_msg, {}

    def delete_files(self, files: List):
        """删除已上传的文件"""
        for f in files:
            try:
                genai.delete_file(f.name)
            except:
                pass


# ==================== 文件操作 ====================

def get_image_files(image_dir: Path) -> List[Path]:
    """获取目录中的所有图片文件"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    image_paths = set()

    for ext in image_extensions:
        image_paths.update(image_dir.glob(f"*{ext}"))

    return sorted(image_paths)


def load_text_content(image_dir: Path) -> tuple:
    """从目录加载文字内容"""
    # 尝试读取 content.txt
    text_path = image_dir / "content.txt"

    username = image_dir.parent.name  # 从目录名获取用户名
    text_content = ""

    if text_path.exists():
        with open(text_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取纯文案内容
        lines = content.split('\n')
        content_lines = []
        in_content = False
        for line in lines:
            if '文案:' in line or 'desc:' in line.lower():
                in_content = True
                continue
            if in_content:
                content_lines.append(line)

        text_content = '\n'.join(content_lines).strip()

        # 如果没有提取到，使用全部内容
        if not text_content:
            text_content = content

    return username, text_content


def save_result(title: str, username: str, text: str,
                result: str, model: str, token_info: dict,
                image_count: int, output_dir: str = "xhs_analysis") -> Path:
    """保存分析结果"""
    output_path = Path(output_dir)
    safe_username = username[:30]
    user_output = output_path / safe_username
    user_output.mkdir(parents=True, exist_ok=True)

    safe_title = title[:50].replace('/', '_').replace('\\', '_').replace(':', '_')
    timestamp = time.strftime('%Y%m%d_%H%M%S')

    result_file = user_output / f"{safe_title}_{timestamp}.md"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        f.write(f"## 📌 元信息\n\n")
        f.write(f"| 项目 | 内容 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| **作者** | {username} |\n")
        f.write(f"| **分析时间** | {time.strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write(f"| **使用模型** | {model} |\n")
        f.write(f"| **图片数量** | {image_count} |\n")

        if token_info and token_info.get('total_tokens', 0) > 0:
            f.write(f"| **Token 使用** | 输入: {token_info.get('prompt_tokens', 0):,} | 输出: {token_info.get('candidates_tokens', 0):,} | 总计: {token_info.get('total_tokens', 0):,} |\n")

        f.write(f"\n---\n\n")
        f.write(f"## 📄 原始文字\n\n{text}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 🤖 AI 分析结果\n\n{result}")

    return result_file


# ==================== 主处理流程 ====================

def process_single_note(image_dir: str, analyzer: XHSAnalyzer,
                        output_dir: str = "xhs_analysis") -> bool:
    """处理单个笔记目录"""
    image_dir = Path(image_dir)

    if not image_dir.is_dir():
        print(f"❌ 目录不存在: {image_dir}")
        return False

    # 获取图片文件
    image_paths = get_image_files(image_dir)

    if not image_paths:
        print(f"❌ 未找到图片文件")
        return False

    print(f"\n{'='*80}")
    print(f"📁 笔记: {image_dir.name}")
    print(f"👤 作者: {image_dir.parent.name}")
    print(f"📸 图片: {len(image_paths)} 张")
    print(f"{'='*80}")

    # 加载文字内容
    username, text_content = load_text_content(image_dir)
    print(f"📄 文字: {len(text_content)} 字符\n")

    # 上传图片
    uploaded_files = analyzer.upload_images(image_paths)

    if not uploaded_files:
        print(f"❌ 图片上传失败")
        return False

    try:
        # 分析
        result, token_info = analyzer.analyze(text_content, uploaded_files)

        # 删除上传的文件
        analyzer.delete_files(uploaded_files)

        # 保存结果
        if result and not result.startswith("❌"):
            result_file = save_result(
                title=image_dir.name,
                username=username,
                text=text_content,
                result=result,
                model=analyzer.model_name,
                token_info=token_info,
                image_count=len(uploaded_files),
                output_dir=output_dir
            )
            print(f"💾 结果已保存: {result_file.name}")

            if token_info and token_info.get('total_tokens', 0) > 0:
                print(f"📊 Token: 输入 {token_info.get('prompt_tokens', 0):,} | 输出 {token_info.get('candidates_tokens', 0):,} | 总计 {token_info.get('total_tokens', 0):,}")

            return True
        else:
            print(f"❌ 分析失败")
            return False

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return False


def batch_process_user(user_dir: str, analyzer: XHSAnalyzer,
                       output_dir: str = "xhs_analysis") -> dict:
    """批量处理用户的所有笔记"""
    user_path = Path(user_dir)

    if not user_path.is_dir():
        print(f"❌ 目录不存在: {user_dir}")
        return {'total': 0, 'success': 0, 'fail': 0}

    # 查找所有笔记目录
    note_dirs = []
    for item in user_path.iterdir():
        if item.is_dir():
            if get_image_files(item):
                note_dirs.append(item)

    if not note_dirs:
        print(f"❌ 未找到包含图片的笔记目录")
        return {'total': 0, 'success': 0, 'fail': 0}

    print(f"\n📊 找到 {len(note_dirs)} 个笔记\n")

    stats = {'total': len(note_dirs), 'success': 0, 'fail': 0}

    for i, note_dir in enumerate(note_dirs, 1):
        print(f"\n[{i}/{len(note_dirs)}] {note_dir.name}")
        print(f"{'='*60}")

        if process_single_note(note_dir, analyzer, output_dir):
            stats['success'] += 1
        else:
            stats['fail'] += 1

        time.sleep(2)  # 避免请求过快

    print(f"\n{'='*60}")
    print(f"📊 完成")
    print(f"总计: {stats['total']} | 成功: {stats['success']} | 失败: {stats['fail']}")

    return stats


# ==================== 主程序 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="小红书图文笔记分析工具 - 简化版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析单个笔记:
   python xhs_simple_analysis.py --dir "xhs_images/用户名/笔记标题"

2. 批量分析用户的所有笔记:
   python xhs_simple_analysis.py --user-dir "xhs_images/用户名"

3. 指定模型:
   python xhs_simple_analysis.py --dir "images" --model flash
        """
    )

    parser.add_argument('--dir', help='单个笔记的图片文件夹路径')
    parser.add_argument('--user-dir', help='用户文件夹路径（批量处理）')
    parser.add_argument('--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型')
    parser.add_argument('-o', '--output', default='xhs_analysis',
                        help='输出目录（默认: xhs_analysis）')
    parser.add_argument('--api-key', help='Gemini API Key')

    args = parser.parse_args()

    # 初始化分析器
    try:
        analyzer = XHSAnalyzer(model=args.model, api_key=args.api_key)
    except ValueError as e:
        print(f"❌ {e}")
        return

    print(f"\n{'='*80}")
    print(f"🖼️  小红书图文笔记分析工具")
    print(f"{'='*80}")

    if args.dir:
        process_single_note(args.dir, analyzer, args.output)
    elif args.user_dir:
        batch_process_user(args.user_dir, analyzer, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
