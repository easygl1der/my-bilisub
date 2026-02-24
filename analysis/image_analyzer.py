#!/usr/bin/env python3
"""
使用 Gemini API 进行图文多模态分析

功能：
1. 提取小红书图文笔记的图片和文字
2. 上传图片到 Gemini Files API
3. 使用 Gemini 进行图文混合分析

使用示例:
    # 分析单个小红书笔记
    python multimodal_gemini.py --url "小红书笔记链接"

    # 批量分析（从CSV读取链接列表）
    python multimodal_gemini.py --csv notes.csv

    # 指定模式
    python multimodal_gemini.py --url "..." --mode knowledge

    # 从本地图片文件夹分析
    python multimodal_gemini.py --dir "images_folder" --text "笔记描述文字"
"""

import os
import sys
import time
import json
import re
import csv
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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


# ==================== 配置 ====================

GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',
    'flash': 'gemini-2.5-flash',
    'pro': 'gemini-2.5-pro',
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
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.config_api import API_CONFIG
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


# ==================== 小红书图片提取 ====================

def extract_xhs_images(url: str) -> Tuple[str, List[str]]:
    """
    从小红书链接提取笔记的图片URL

    复用 download_xhs_images.py 的逻辑

    Returns:
        (标题, 图片URL列表)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    print(f"📡 请求小红书页面...")
    print(f"   URL: {url[:80]}...")

    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        print(f"   状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            return None, []

        if '/404?' in response.url or '你访问的页面不见了' in response.text:
            print(f"❌ 页面无法访问（反爬虫保护）")
            return None, []

        html = response.text
        print(f"✅ 页面获取成功 (长度: {len(html)})")

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None, []

    # 提取标题
    title = "小红书笔记"
    title_match = re.search(r'<title[^>]*>(.+?)</title>', html)
    if title_match:
        title = title_match.group(1).replace(' - 小红书', '').strip()
    print(f"📝 标题: {title[:50]}...")

    # 提取图片URL
    print(f"\n🔍 正在提取笔记图片...")

    start_idx = html.find('window.__INITIAL_STATE__=')
    if start_idx == -1:
        print(f"❌ 未找到 __INITIAL_STATE__")
        return title, []

    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    data = None
    try:
        data = json.loads(json_str)
        print(f"✅ JSON解析成功")
    except json.JSONDecodeError:
        print(f"⚠️  JSON解析失败，使用正则搜索...")

    image_urls = []

    # 方法1: 从解析好的 JSON 中提取
    if data:
        try:
            note = data.get('note', {})
            note_detail = note.get('noteDetail', {})
            image_list = note_detail.get('imageList', [])

            if image_list:
                print(f"✅ 从 note.noteDetail.imageList 找到 {len(image_list)} 张图片")
                for img_obj in image_list:
                    if isinstance(img_obj, dict):
                        url = (img_obj.get('urlDefault') or
                               img_obj.get('url_default') or
                               img_obj.get('url') or
                               img_obj.get('infoList', [{}])[0].get('url')
                               if isinstance(img_obj.get('infoList'), list) else None)
                        if url:
                            image_urls.append(url)
        except Exception as e:
            print(f"⚠️  方法1失败: {e}")

    # 方法2: 直接在 JSON 字符串中搜索
    if not image_urls:
        start = json_str.find('"imageList"')
        if start >= 0:
            bracket_start = json_str.find('[', start)
            if bracket_start >= 0:
                depth = 0
                i = bracket_start
                while i < len(json_str):
                    if json_str[i] == '[':
                        depth += 1
                    elif json_str[i] == ']':
                        depth -= 1
                        if depth == 0:
                            bracket_end = i
                            break
                    i += 1

                list_content = json_str[bracket_start+1:bracket_end]
                url_pattern = r'"urlDefault":"([^"]+)"'
                for match in re.finditer(url_pattern, list_content):
                    url = match.group(1)
                    if url:
                        image_urls.append(url)

    # 清理和去重
    seen = set()
    unique_urls = []
    for url in image_urls:
        url = url.split('?')[0]
        try:
            url = url.encode('utf-8').decode('unicode_escape')
        except:
            pass
        url = url.replace(r'\/', '/')
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        elif not url.startswith('https://'):
            continue
        if url not in seen and 'xhscdn' in url:
            seen.add(url)
            unique_urls.append(url)

    print(f"📋 找到 {len(unique_urls)} 张图片")

    return title, unique_urls


def download_images(image_urls: List[str], output_dir: Path) -> List[Path]:
    """
    下载图片到指定目录

    Returns:
        下载的图片路径列表
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/',
    }

    downloaded_paths = []

    print(f"\n📥 开始下载 {len(image_urls)} 张图片...")
    print(f"{'='*60}")

    for i, img_url in enumerate(image_urls, 1):
        try:
            print(f"[{i}/{len(image_urls)}] ", end='', flush=True)

            img_response = requests.get(img_url, headers=headers, timeout=30)

            if img_response.status_code == 200:
                # 确定文件扩展名
                content_type = img_response.headers.get('Content-Type', '')
                if 'png' in content_type or img_url.endswith('.png'):
                    ext = '.png'
                elif 'webp' in content_type or img_url.endswith('.webp'):
                    ext = '.webp'
                else:
                    ext = '.jpg'

                filename = f"image_{i:02d}{ext}"
                filepath = output_dir / filename

                with open(filepath, 'wb') as f:
                    f.write(img_response.content)

                size = len(img_response.content) / 1024
                print(f"✅ {size:.1f}KB")
                downloaded_paths.append(filepath)
            else:
                print(f"❌ HTTP {img_response.status_code}")

        except Exception as e:
            print(f"❌ {str(e)[:30]}")

        time.sleep(0.3)

    print(f"{'='*60}")
    print(f"\n🎉 下载完成! 成功: {len(downloaded_paths)}/{len(image_urls)}")

    return downloaded_paths


# ==================== Gemini 图文分析 ====================

class MultimodalAnalyzer:
    """图文多模态分析器"""

    def __init__(self, model: str = 'flash-lite', api_key: str = None):
        """
        初始化分析器

        Args:
            model: 模型类型 (flash/flash-lite/pro)
            api_key: Gemini API Key
        """
        self.api_key = api_key or get_api_key()
        self.model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash'])
        self.model = model

        if not configure_gemini(self.api_key):
            raise ValueError("无法配置 Gemini API")

    def upload_images(self, image_paths: List[Path]) -> List:
        """
        批量上传图片到 Gemini Files API

        Args:
            image_paths: 图片路径列表

        Returns:
            上传的文件对象列表
        """
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

    def analyze_note(self, text: str, image_files: List,
                     mode: str = 'knowledge', custom_prompt: str = None) -> Tuple[str, dict]:
        """
        图文混合分析

        Args:
            text: 笔记文字内容
            image_files: 上传的图片文件对象列表
            mode: 分析模式
            custom_prompt: 自定义提示词

        Returns:
            (分析结果, token信息)
        """
        prompt = self._get_prompt(mode, custom_prompt, text)

        print(f"🤖 使用模型: {self.model_name}")
        print(f"📝 分析模式: {mode}")
        print(f"{'='*60}")

        try:
            model = genai.GenerativeModel(self.model_name)

            # 构建输入：图片 + 提示词
            contents = image_files + [prompt]

            print(f"🔄 正在分析...")
            start_time = time.time()

            response = model.generate_content(contents)

            elapsed = time.time() - start_time
            print(f"✅ 分析完成! ({elapsed:.1f}秒)\n")

            # 提取 token 使用信息
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

    def _get_prompt(self, mode: str, custom_prompt: str, text: str) -> str:
        """构建分析提示词"""
        if custom_prompt:
            return f"{custom_prompt}\n\n## 笔记文字内容:\n{text}"

        knowledge_prompt = f"""你是一个专业的小红书图文笔记分析师，擅长将图文内容转化为结构化的知识库笔记。请分析以下图文笔记，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 笔记基本信息
- **笔记类型**: [穿搭分享/美妆教程/美食探店/旅行攻略/知识科普/产品测评/生活记录/其他]
- **核心主题**: [一句话概括]
- **内容风格**: [干货教程/种草推荐/日常生活/观点分享]

## 📖 图文内容摘要（150-250字）
[结合图片和文字，用精炼的语言概括笔记核心内容]

## 🎯 核心信息提取
### 主题/产品
- **主要对象**: [笔记介绍的主要产品/地点/话题]
- **关键特点**: [列举3-5个关键特点]

### 干货要点
[如果笔记有实用信息，列出要点]
- 要点1: [详细说明]
- 要点2: [详细说明]
- 要点3: [详细说明]

### 推荐理由
[作者推荐的核心理由]
- 理由1: [...]
- 理由2: [...]

## 📸 图片分析
[分析图片内容]
- **图片数量**: {len(text) if hasattr(self, '_image_count') else '若干'}张
- **图片风格**: [实拍图/街拍图/摆拍图/平铺图/细节图/对比图]
- **视觉效果**: [图片的氛围感、色调、构图等]
- **关键细节**: [从图片中观察到的细节]

## 💡 亮点与价值
### 独特之处
[这篇笔记与众不同的地方]

### 实用价值
- **参考性**: [高/中/低] - [说明]
- **可操作性**: [高/中/低] - [说明]

### 情绪价值
- **氛围感**: [给人什么感觉]
- **共鸣点**: [可能引起共鸣的地方]

## 📝 作者风格分析
- **表达方式**: [简洁明了/详细啰嗦/幽默风趣/正式严肃]
- **内容倾向**: [实用干货/情感共鸣/审美展示/知识分享]
- **可信度**: [高/中/低] - [理由]

## ⚠️ 注意事项
[需要留意的点，如:
- 是否为广告推广
- 信息是否有夸大
- 是否有踩雷风险
- 实际参考时需要注意什么]

## 🔗 相关延伸
[基于笔记内容，推荐值得深入了解的相关话题、产品或思考方向]

---

## 笔记文字内容:

{text}

---

请确保输出结构完整，每个部分都要有实质内容。如果某部分确实不适用，请标注"[不适用]"并说明原因。"""

        summary_prompt = f"""请用中文详细总结这个图文笔记的内容，包括：
1. 笔记的主题和类型
2. 主要展示的产品/内容/场景
3. 关键信息和亮点
4. 图片的视觉效果
5. 任何值得注意的细节

## 笔记文字内容:
{text}"""

        prompts = {
            'knowledge': knowledge_prompt,
            'summary': summary_prompt,
        }

        return prompts.get(mode, summary_prompt)

    def delete_files(self, files: List):
        """删除已上传的文件"""
        for f in files:
            try:
                genai.delete_file(f.name)
            except:
                pass


# ==================== 输出管理 ====================

def save_result(title: str, text: str, result: str, mode: str, model: str,
                token_info: dict, image_count: int,
                output_dir: str = "multimodal_analysis") -> Path:
    """保存分析结果"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 清理标题作为文件名
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    result_file = output_path / f"{safe_title}_{timestamp}.md"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f"# {title} - 图文分析\n\n")
        f.write(f"## 📌 元信息\n\n")
        f.write(f"| 项目 | 内容 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| **笔记标题** | {title} |\n")
        f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write(f"| **使用模型** | {model} |\n")
        f.write(f"| **分析模式** | {mode} |\n")
        f.write(f"| **图片数量** | {image_count} |\n")

        if token_info and token_info.get('total_tokens', 0) > 0:
            f.write(f"| **Token 使用** | 输入: {token_info.get('prompt_tokens', 0):,} | 输出: {token_info.get('candidates_tokens', 0):,} | **总计: {token_info.get('total_tokens', 0):,}** |\n")

        f.write(f"\n---\n\n")
        f.write(f"## 📄 原始文字内容\n\n")
        f.write(f"{text}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 🤖 AI 分析结果\n\n")
        f.write(result)

    return result_file


# ==================== 主处理流程 ====================

def process_xhs_note(url: str, analyzer: MultimodalAnalyzer,
                     mode: str = 'knowledge', output_dir: str = "multimodal_analysis",
                     keep_images: bool = False) -> bool:
    """
    处理单个小红书笔记

    Args:
        url: 小红书笔记链接
        analyzer: MultimodalAnalyzer 实例
        mode: 分析模式
        output_dir: 输出目录
        keep_images: 是否保留下载的图片

    Returns:
        是否成功
    """
    # 提取图片URL
    title, image_urls = extract_xhs_images(url)

    if not image_urls:
        print(f"❌ 未找到图片")
        return False

    # 下载图片
    temp_dir = Path(output_dir) / "_temp_images"
    downloaded_paths = download_images(image_urls, temp_dir)

    if not downloaded_paths:
        print(f"❌ 图片下载失败")
        return False

    # 上传图片到 Gemini
    try:
        uploaded_files = analyzer.upload_images(downloaded_paths)

        if not uploaded_files:
            print(f"❌ 图片上传失败")
            return False

        # 构建文字内容（如果有标题，可以作为文字的一部分）
        text_content = f"笔记标题: {title}\n\n"

        # 分析图文
        result, token_info = analyzer.analyze_note(
            text=text_content,
            image_files=uploaded_files,
            mode=mode
        )

        # 删除上传的文件
        analyzer.delete_files(uploaded_files)

        # 保存结果
        if result and not result.startswith("❌"):
            result_file = save_result(
                title=title,
                text=text_content,
                result=result,
                mode=mode,
                model=analyzer.model_name,
                token_info=token_info,
                image_count=len(uploaded_files),
                output_dir=output_dir
            )
            print(f"💾 结果已保存: {result_file.name}")

            # 打印 token 信息
            if token_info and token_info.get('total_tokens', 0) > 0:
                print(f"📊 Token 使用: 输入 {token_info.get('prompt_tokens', 0):,} | 输出 {token_info.get('candidates_tokens', 0):,} | 总计 {token_info.get('total_tokens', 0):,}")

            return True
        else:
            print(f"❌ 分析失败")
            return False

    finally:
        # 清理临时图片
        if not keep_images and temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def process_local_images(image_dir: str, text: str, analyzer: MultimodalAnalyzer,
                         mode: str = 'knowledge', output_dir: str = "multimodal_analysis") -> bool:
    """
    处理本地图片文件夹

    Args:
        image_dir: 图片文件夹路径
        text: 配套的文字内容
        analyzer: MultimodalAnalyzer 实例
        mode: 分析模式
        output_dir: 输出目录

    Returns:
        是否成功
    """
    image_dir = Path(image_dir)

    if not image_dir.is_dir():
        print(f"❌ 目录不存在: {image_dir}")
        return False

    # 获取所有图片文件
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    image_paths = []
    for ext in image_extensions:
        image_paths.extend(image_dir.glob(f"*{ext}"))
        image_paths.extend(image_dir.glob(f"*{ext.upper()}"))

    image_paths = sorted(image_paths)

    if not image_paths:
        print(f"❌ 未找到图片文件")
        return False

    print(f"📁 找到 {len(image_paths)} 张图片")

    # 上传图片
    uploaded_files = analyzer.upload_images(image_paths)

    if not uploaded_files:
        print(f"❌ 图片上传失败")
        return False

    try:
        # 分析图文
        result, token_info = analyzer.analyze_note(
            text=text or "(无文字内容)",
            image_files=uploaded_files,
            mode=mode
        )

        # 删除上传的文件
        analyzer.delete_files(uploaded_files)

        # 保存结果
        if result and not result.startswith("❌"):
            title = image_dir.name
            result_file = save_result(
                title=title,
                text=text,
                result=result,
                mode=mode,
                model=analyzer.model_name,
                token_info=token_info,
                image_count=len(uploaded_files),
                output_dir=output_dir
            )
            print(f"💾 结果已保存: {result_file.name}")

            if token_info and token_info.get('total_tokens', 0) > 0:
                print(f"📊 Token 使用: 输入 {token_info.get('prompt_tokens', 0):,} | 输出 {token_info.get('candidates_tokens', 0):,} | 总计 {token_info.get('total_tokens', 0):,}")

            return True
        else:
            print(f"❌ 分析失败")
            return False

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return False


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="使用 Gemini API 进行图文多模态分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析单个小红书笔记:
   python multimodal_gemini.py --url "小红书笔记链接"

2. 批量分析（从CSV读取）:
   python multimodal_gemini.py --csv notes.csv

3. 分析本地图片文件夹:
   python multimodal_gemini.py --dir "images_folder" --text "配套的文字描述"

4. 指定模式:
   python multimodal_gemini.py --url "..." --mode knowledge

5. 保留下载的图片:
   python multimodal_gemini.py --url "..." --keep-images
        """
    )

    parser.add_argument('--url', help='小红书笔记链接')
    parser.add_argument('--csv', help='CSV文件路径（包含url列）')
    parser.add_argument('--dir', help='本地图片文件夹路径')
    parser.add_argument('--text', help='配套的文字内容（用于--dir模式）')
    parser.add_argument('-m', '--mode', choices=['knowledge', 'summary'],
                        default='knowledge', help='分析模式（默认: knowledge）')
    parser.add_argument('--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('-o', '--output', default='multimodal_analysis',
                        help='输出目录（默认: multimodal_analysis）')
    parser.add_argument('--keep-images', action='store_true',
                        help='保留下载的图片')
    parser.add_argument('--api-key', help='Gemini API Key（覆盖配置文件）')

    args = parser.parse_args()

    # 初始化分析器
    try:
        analyzer = MultimodalAnalyzer(model=args.model, api_key=args.api_key)
    except ValueError as e:
        print(f"❌ {e}")
        return

    print(f"\n{'='*80}")
    print(f"🖼️  图文多模态分析工具")
    print(f"{'='*80}")

    # 处理小红书链接
    if args.url:
        print(f"🔗 链接: {args.url[:80]}...")
        success = process_xhs_note(
            url=args.url,
            analyzer=analyzer,
            mode=args.mode,
            output_dir=args.output,
            keep_images=args.keep_images
        )

        if success:
            print(f"\n✅ 完成!")
        else:
            print(f"\n❌ 失败!")

    # 处理本地图片文件夹
    elif args.dir:
        print(f"📁 图片目录: {args.dir}")
        print(f"📝 文字内容: {args.text[:100] if args.text else '(无)'}...")
        success = process_local_images(
            image_dir=args.dir,
            text=args.text or "",
            analyzer=analyzer,
            mode=args.mode,
            output_dir=args.output
        )

        if success:
            print(f"\n✅ 完成!")
        else:
            print(f"\n❌ 失败!")

    # 批量处理CSV
    elif args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"❌ CSV文件不存在: {args.csv}")
            return

        print(f"📋 CSV文件: {args.csv}")

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"📊 待处理: {len(rows)} 条记录\n")

        success_count = 0
        fail_count = 0

        for i, row in enumerate(rows, 1):
            url = row.get('url') or row.get('链接') or row.get('URL', '')
            if not url:
                continue

            print(f"\n{'='*80}")
            print(f"[{i}/{len(rows)}] 处理: {url[:60]}...")
            print(f"{'='*80}")

            if process_xhs_note(url, analyzer, args.mode, args.output, args.keep_images):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"📊 批量处理完成")
        print(f"{'='*80}")
        print(f"总计: {len(rows)} | 成功: {success_count} | 失败: {fail_count}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
