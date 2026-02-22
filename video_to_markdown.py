#!/usr/bin/env python3
"""
视频学习笔记生成器 (简化版 + GitHub 图床)

功能：
1. 从视频提取关键帧
2. 上传到 GitHub + jsDelivr CDN（永久存储）
3. 使用 Gemini 分析视频
4. 输出 Markdown 格式（图片为云端链接）

使用示例:
    python video_to_markdown.py -f "video.mp4"

配置说明:
    需要在 config_api.py 中配置 GitHub Token 和仓库信息：
    API_CONFIG = {
        "github": {
            "token": "your_github_token",
            "repo": "username/repo-name"
        }
    }
"""

import os
import sys
import re
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# ==================== 配置 ====================

GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',
    'flash': 'gemini-2.5-flash',
    'pro': 'gemini-2.5-pro',
}

DEFAULT_OUTPUT_DIR = "learning_notes"


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


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """清理文件名"""
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    name = ''.join(char for char in name if ord(char) >= 32)
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]
    return name or "untitled"


def get_github_config() -> Dict:
    """获取 GitHub 配置"""
    # 环境变量
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')

    # 从 config_api.py 获取
    if not token or not repo:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from config_api import API_CONFIG
            github_config = API_CONFIG.get('github', {})
            token = token or github_config.get('token')
            repo = repo or github_config.get('repo')
        except ImportError:
            pass

    return {'token': token, 'repo': repo}


# ==================== 关键帧提取与上传 ====================

def extract_keyframe_timestamps_with_gemini(video_path: str, api_key: str,
                                             target_count: int = 8) -> List[Dict]:
    """
    使用 Gemini 分析视频，智能提取关键时间点

    Args:
        video_path: 视频文件路径
        api_key: Gemini API Key
        target_count: 目标关键帧数量

    Returns:
        关键时间点列表 [{timestamp, description, reason}]
    """
    import google.generativeai as genai
    import json
    import time

    print(f"\n🤖 Gemini 智能检测关键时刻...")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')

    # 上传视频
    print(f"   └─ 📤 上传视频到 Gemini...")
    video_file = genai.upload_file(path=str(video_path))

    # 等待处理完成
    print(f"   └─ ⏳ 等待视频处理...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name != "ACTIVE":
        genai.delete_file(video_file.name)
        print(f"   └─ ❌ 视频处理失败")
        return []

    # 获取视频时长
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        duration = 0

    # 构建提示词 - 让 Gemini 返回关键时间点
    prompt = f"""你是一个专业的视频分析师，擅长识别视频中的关键时刻。

请分析这个视频（时长: {duration:.0f}秒），提取约 {target_count} 个关键时刻的时间点。

**请根据视频类型关注不同内容：**

**对于讲座/PPT类型视频，请关注：**
- PPT 页面切换的时刻
- 新话题/章节开始的时刻
- 展示重要图表、公式、代码示例的时刻
- 讲师强调重点内容的时刻

**对于风景/Vlog类型视频，请关注：**
- 场景明显变化的时刻
- 进入新地点/环境的时刻
- 展示特色景观的时刻
- 人物活动明显变化的时刻

**对于采访/对话类型视频，请关注：**
- 话题转换的时刻
- 出现重要观点或金句的时刻
- 情绪明显变化的时刻
- 对话方发生明显变化的时刻

请严格按照以下 JSON 格式返回（只返回 JSON，不要有其他说明文字）：
```json
[
  {{"timestamp": 10.5, "description": "开场介绍，说明视频主题", "reason": "内容开始"},
  {{"timestamp": 45.2, "description": "第一页PPT，展示核心概念框架", "reason": "重要知识点"},
  {{"timestamp": 120.0, "description": "切换到案例分析", "reason": "实际应用"}}
]
```

**注意事项：**
1. timestamp 单位为秒，保留一位小数
2. 按时间顺序排列
3. 只返回 JSON 数组，不要有任何其他说明文字"""

    print(f"   └─ 🔄 Gemini 分析中...")
    start_time = time.time()

    response = model.generate_content([video_file, prompt])

    elapsed = time.time() - start_time
    print(f"   └─ ✅ 分析完成 ({elapsed:.1f}秒)")

    # 删除上传的文件
    genai.delete_file(video_file.name)

    # 解析 JSON 响应
    result_text = response.text.strip()

    # 尝试提取 JSON 数组
    try:
        # 处理可能的 markdown 代码块
        if '```' in result_text:
            # 提取代码块内容
            parts = result_text.split('```')
            for i, part in enumerate(parts):
                if 'json' in part.lower():
                    result_text = part.lower().replace('json', '').replace('```', '').strip()
                    break
                elif i % 2 == 1 and not any(keyword in part for keyword in ['json', 'javascript', 'python']):
                    result_text = part.strip()
                    break

        # 尝试找到 JSON 数组
        json_start = result_text.find('[')
        if json_start == -1:
            json_start = result_text.find('[')

        if json_start >= 0:
            json_end = result_text.rfind(']')
            if json_end > json_start:
                json_str = result_text[json_start:json_end+1]
                keyframes = json.loads(json_str)
                print(f"   └─ 📊 识别到 {len(keyframes)} 个关键时刻")
                return keyframes
    except json.JSONDecodeError as e:
        print(f"   └─ ⚠️  Gemini 返回格式解析失败: {e}")

    print(f"   └─ ⚠️  未能识别关键时刻，将使用默认方案")
    return []


def extract_keyframes_at_timestamps(video_path: str, keyframe_data: List[Dict]) -> List[Dict]:
    """
    根据 Gemini 返回的时间点精准提取关键帧

    Args:
        video_path: 视频文件路径
        keyframe_data: Gemini 返回的关键帧数据 [{timestamp, description, reason}]

    Returns:
        提取的关键帧信息列表 [{local_path, timestamp, description, reason, uploaded, url}]
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30  # 默认帧率

    keyframes = []
    temp_dir = Path(".temp_keyframes")
    temp_dir.mkdir(exist_ok=True)

    print(f"\n🖼️  提取关键帧 ({len(keyframe_data)} 帧)")

    for i, kf in enumerate(keyframe_data):
        timestamp = kf['timestamp']
        description = kf.get('description', '')
        reason = kf.get('reason', '')

        # 跳转到指定时间戳（向前取整帧，避免黑屏）
        frame_number = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_number - 5))
        ret, frame = cap.read()

        if ret:
            # 保存帧
            filename = f"keyframe_{i+1:02d}_{int(timestamp)}s.jpg"
            local_path = temp_dir / filename
            cv2.imwrite(str(local_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            print(f"  [{i+1}/{len(keyframe_data)}] {timestamp:.1f}s - {description[:30]}...")

            keyframes.append({
                'local_path': str(local_path),
                'timestamp': timestamp,
                'description': description,
                'reason': reason,
                'uploaded': False,
                'url': None
            })
        else:
            print(f"  [{i+1}/{len(keyframe_data)}] ⚠️  无法提取 {timestamp:.1f}s 的帧")

    cap.release()
    return keyframes


def detect_scene_changes_fallback(video_path: str, target_count: int = 6) -> List[Dict]:
    """
    备选方案：使用 OpenCV 检测场景变化（当 Gemini 不可用时）

    Args:
        video_path: 视频文件路径
        target_count: 目标关键帧数量

    Returns:
        关键帧数据列表 [{timestamp, description, reason}]
    """
    import cv2

    print(f"\n🔄 使用 OpenCV 场景检测（备选方案）")

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30  # 默认帧率

    # 计算采样间隔（多采样一些候选）
    interval = max(1, total_frames // (target_count * 3))

    prev_frame = None
    scene_changes = []
    last_scene_time = -2.0

    for frame_idx in range(0, total_frames, interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # 转灰度并缩放（加快处理）
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (320, 180))

        if prev_frame is not None:
            # 计算帧差异
            diff = cv2.absdiff(prev_frame, gray)
            diff_score = diff.mean()

            current_time = frame_idx / fps

            # 当差异超过阈值，记录为场景切换
            if diff_score > 30 and (current_time - last_scene_time) >= 2.0:
                scene_changes.append({
                    'timestamp': current_time,
                    'description': f'场景变化 @ {current_time:.0f}秒',
                    'reason': '视觉变化检测'
                })
                last_scene_time = current_time

        prev_frame = gray

    cap.release()

    # 如果检测到的场景变化太少，回退到均匀采样
    if len(scene_changes) < target_count:
        print(f"   └─ ⚠️  仅检测到 {len(scene_changes)} 个场景，补充均匀采样")
        interval = max(1, total_frames // (target_count - len(scene_changes)))
        for i in range(len(scene_changes), target_count):
            timestamp = (i + 1) * interval / fps
            scene_changes.append({
                'timestamp': timestamp,
                'description': f'采样点 @ {timestamp:.0f}秒',
                'reason': '均匀采样补充'
            })

    # 限制数量
    scene_changes = scene_changes[:target_count]

    print(f"   └─ 📊 检测到 {len(scene_changes)} 个关键点")
    return scene_changes


# 原有的关键帧提取函数（保留为备用）
def extract_and_upload_keyframes_uniform(video_path: Path, count: int = 6) -> List[Dict]:
    """
    提取关键帧并上传到 GitHub 图床

    图床方案：GitHub + jsDelivr CDN
    - 永久存储
    - 全球 CDN 加速
    - 完全免费
    """
    import cv2
    import requests
    import base64

    print(f"\n🖼️  提取关键帧 ({count} 帧)")

    # 获取 GitHub 配置
    github_config = get_github_config()
    github_token = github_config.get('token')
    github_repo = github_config.get('repo')

    if not github_token or not github_repo:
        print("⚠️  未配置 GitHub Token，将使用本地图片")
        print("   请在 config_api.py 中配置:")
        print("   API_CONFIG = {'github': {'token': 'your_token', 'repo': 'username/repo'}}")

    # 创建临时目录
    temp_dir = Path(".temp_keyframes")
    temp_dir.mkdir(exist_ok=True)

    # 提取帧
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("❌ 无法打开视频文件")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0

    interval = max(1, total_frames // count)
    keyframes = []
    frame_idx = 0
    extracted_count = 0

    while cap.isOpened() and extracted_count < count:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % interval == 0:
            timestamp = frame_idx / fps if fps > 0 else 0
            local_path = temp_dir / f"frame_{extracted_count+1:03d}.jpg"

            cv2.imwrite(str(local_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            keyframes.append({
                'local_path': local_path,
                'timestamp': timestamp
            })

            extracted_count += 1
            print(f"  [{extracted_count}/{count}] 提取帧 @ {timestamp:.0f}秒")

        frame_idx += 1

    cap.release()

    # 上传到 GitHub
    if github_token and github_repo:
        print(f"\n📤 上传图片到 GitHub...")
        uploaded_count = 0

        # 生成唯一的文件名（避免冲突）
        import uuid
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]

        for i, kf in enumerate(keyframes, 1):
            local_path = kf['local_path']
            filename = f"{timestamp_str}_{unique_id}_frame_{i:03d}.jpg"

            url = upload_to_github(local_path, github_token, github_repo, filename)
            if url:
                kf['url'] = url
                kf['uploaded'] = True
                uploaded_count += 1
                print(f"  [{i}/{count}] ✅ 上传成功")
            else:
                kf['uploaded'] = False
                print(f"  [{i}/{count}] ⚠️  上传失败，使用本地路径")

        print(f"✅ 成功上传: {uploaded_count}/{count}")
    else:
        print(f"\n⚠️  跳过上传，使用本地图片")
        for kf in keyframes:
            kf['uploaded'] = False

    return keyframes


def extract_and_upload_keyframes_smart(video_path: Path, count: int = 6,
                                     use_gemini: bool = True,
                                     api_key: str = None) -> List[Dict]:
    """
    智能提取关键帧并上传到 GitHub 图床

    Args:
        video_path: 视频文件路径
        count: 目标关键帧数量
        use_gemini: 是否使用 Gemini 智能检测
        api_key: Gemini API Key

    Returns:
        关键帧列表 [{local_path, timestamp, description, reason, uploaded, url}]
    """
    import cv2
    import requests
    import base64
    import uuid
    import shutil

    print(f"\n🖼️  智能提取关键帧 (目标: {count} 帧)")

    # 获取 GitHub 配置
    github_config = get_github_config()
    github_token = github_config.get('token')
    github_repo = github_config.get('repo')

    if not github_token or not github_repo:
        print("⚠️  未配置 GitHub Token，将使用本地图片")

    # 创建临时目录
    temp_dir = Path(".temp_keyframes")
    temp_dir.mkdir(exist_ok=True)

    # 尝试使用 Gemini 智能检测
    keyframes = []

    if use_gemini and api_key:
        try:
            # 步骤1: 使用 Gemini 识别关键时间点
            keyframe_data = extract_keyframe_timestamps_with_gemini(
                str(video_path), api_key, count
            )

            if keyframe_data:
                # 步骤2: 根据时间点精准提取
                keyframes = extract_keyframes_at_timestamps(
                    video_path, keyframe_data
                )
                print(f"   └─ ✅ Gemini 智能检测完成")
        except Exception as e:
            print(f"   └─ ⚠️  Gemini 检测失败: {e}，使用备选方案")

    # 如果 Gemini 失败或未启用，使用备选方案
    if not keyframes:
        print(f"   └─ 🔄 使用备选方案（OpenCV 场景检测）")
        keyframe_data = detect_scene_changes_fallback(str(video_path), count)
        keyframes = extract_keyframes_at_timestamps(video_path, keyframe_data)

    # 上传到 GitHub
    if github_token and github_repo and keyframes:
        print(f"\n📤 上传图片到 GitHub...")
        uploaded_count = 0

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]

        for i, kf in enumerate(keyframes, 1):
            local_path = kf['local_path']
            filename = f"{timestamp_str}_{unique_id}_kf_{i:03d}.jpg"

            url = upload_to_github(local_path, github_token, github_repo, filename)
            if url:
                kf['url'] = url
                kf['uploaded'] = True
                uploaded_count += 1
                print(f"  [{i}/{len(keyframes)}] ✅ 上传成功")
            else:
                kf['uploaded'] = False

        print(f"✅ 成功上传: {uploaded_count}/{len(keyframes)}")
    else:
        print(f"\n⚠️  跳过上传，使用本地图片")
        for kf in keyframes:
            kf['uploaded'] = False

    # 清理临时文件
    shutil.rmtree(temp_dir, ignore_errors=True)

    return keyframes


def upload_to_github(image_path: Path, token: str, repo: str, filename: str = None) -> Optional[str]:
    """
    上传图片到 GitHub 并返回 jsDelivr CDN 链接

    Args:
        image_path: 本地图片路径
        token: GitHub Personal Access Token
        repo: 仓库名称 (格式: username/repo-name)
        filename: 自定义文件名

    Returns:
        jsDelivr CDN URL 或 None
    """
    import requests
    import base64

    try:
        if not filename:
            filename = image_path.name

        with open(image_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode()

        # 上传到 GitHub 的 assets 目录
        url = f"https://api.github.com/repos/{repo}/contents/assets/{filename}"

        response = requests.put(
            url,
            headers={
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            },
            json={
                'message': f'Upload {filename}',
                'content': content
            },
            timeout=30
        )

        if response.status_code in [200, 201]:
            # 返回 jsDelivr CDN 链接（不包含分支名，jsDelivr 会自动使用默认分支）
            cdn_url = f"https://cdn.jsdelivr.net/gh/{repo}/assets/{filename}"
            return cdn_url
        else:
            print(f"    GitHub API 错误: {response.status_code}")
            return None

    except Exception as e:
        print(f"    上传失败: {e}")
        return None


# ==================== Gemini 分析 ====================

def analyze_with_gemini(video_path: Path, title: str, language: str = 'zh',
                        model: str = 'flash-lite') -> Optional[str]:
    """使用 Gemini 分析视频"""
    import google.generativeai as genai

    api_key = get_api_key()
    if not api_key:
        raise ValueError("未配置 Gemini API Key")

    genai.configure(api_key=api_key)
    model_name = GEMINI_MODELS.get(model, GEMINI_MODELS['flash-lite'])
    gen_model = genai.GenerativeModel(model_name)

    # 获取视频时长
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        duration = 0

    print(f"\n🤖 Gemini 分析...")
    print(f"📤 上传视频...")

    video_file = genai.upload_file(path=str(video_path))

    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name != "ACTIVE":
        genai.delete_file(video_file.name)
        return None

    # 提示词
    if language == 'en':
        prompt = f"""You are a professional video content analyst. Analyze this video ({duration:.0f} seconds) and generate structured learning notes.

## 📋 Video Overview
- **Topic**: [One sentence summary]
- **Content Type**: [Tutorial/Review/Vlog/News/Other]

## 📖 Content Summary (150-250 words)
[Concise summary]

## 🎯 Key Takeaways
- **Point 1**: [Detailed explanation]
- **Point 2**: [Detailed explanation]
- **Point 3**: [Detailed explanation]
- **Point 4**: [Detailed explanation]
- **Point 5**: [Detailed explanation]

## 💡 Core Concepts
| Concept | Explanation |
|---------|-------------|
| Concept A | ... |
| Concept B | ... |

## 📝 Action Items
1. [Action item 1]
2. [Action item 2]
3. [Action item 3]

## 🔗 Further Learning
- Related topics worth exploring"""
    else:
        prompt = f"""你是一个专业的视频内容分析师。请分析这个视频（时长: {duration:.0f}秒），生成结构化的学习笔记。

## 📋 视频概览
- **核心主题**: [一句话概括]
- **内容类型**: [教程/测评/科普/生活分享/新闻资讯/其他]

## 📖 内容概要（150-250字）
[精炼的语言概括视频核心内容]

## 🎯 核心要点
- **要点1**: [详细说明]
- **要点2**: [详细说明]
- **要点3**: [详细说明]
- **要点4**: [详细说明]
- **要点5**: [详细说明]

## 💡 关键概念
| 概念 | 解释 |
|------|------|
| 概念A | ... |
| 概念B | ... |

## 📝 实践要点
1. [可执行的行动项1]
2. [可执行的行动项2]
3. [可执行的行动项3]

## 🔗 延伸思考
- 值得深入了解的相关话题
- 视频引发的问题或思考"""

    print(f"🔄 正在分析...")
    start_time = time.time()

    response = gen_model.generate_content([video_file, prompt])

    elapsed = time.time() - start_time
    genai.delete_file(video_file.name)

    print(f"✅ 分析完成! ({elapsed:.1f}秒)")

    return response.text


# ==================== Markdown 生成 ====================

def build_markdown(title: str, video_path: Path, keyframes: List[Dict],
                    analysis: str, assets_dir: str = 'assets') -> str:
    """生成 Markdown 笔记"""
    lines = []

    # 标题
    lines.append(f"# {title} - 学习笔记")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 元信息
    lines.append("## 📌 元信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| **视频文件** | {video_path.name} |")
    lines.append(f"| **生成时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 关键帧
    if keyframes:
        lines.append("## 🖼️ 关键帧")
        lines.append("")
        for kf in keyframes:
            timestamp = kf.get('timestamp', 0)

            # 优先使用云端 URL
            if kf.get('uploaded') and kf.get('url'):
                lines.append(f"![关键帧]({kf['url']})")
            else:
                # 回退到本地路径
                filename = Path(kf['local_path']).name
                lines.append(f"![关键帧]({assets_dir}/{filename})")

            lines.append(f"*{timestamp:.0f}秒*")
            lines.append("")

    # AI 分析
    if analysis:
        lines.append("---")
        lines.append("")
        lines.append("## 🧠 AI 学习笔记")
        lines.append("")
        lines.append(analysis)
        lines.append("")

    # 个人笔记
    lines.append("---")
    lines.append("")
    lines.append("## 📝 我的笔记")
    lines.append("")
    lines.append("> 留白供添加个人笔记")
    lines.append("")

    return "\n".join(lines)


# ==================== 主流程 ====================

def generate_note(source: str, output_dir: str = DEFAULT_OUTPUT_DIR,
                  keyframe_count: int = 6, gemini_model: str = 'flash-lite',
                  language: str = 'auto') -> Dict:
    """生成视频学习笔记"""
    print(f"\n{'='*60}")
    print(f"🎬 视频学习笔记生成器")
    print(f"{'='*60}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = Path(source)
    if not video_path.exists():
        return {'success': False, 'error': f'文件不存在: {source}'}

    # 获取视频信息
    title = video_path.stem
    safe_title = sanitize_filename(title)
    note_dir = output_dir / safe_title
    note_dir.mkdir(parents=True, exist_ok=True)

    md_file = note_dir / f"{safe_title}_学习笔记.md"

    # 检查是否已存在
    if md_file.exists():
        print(f"⏭️  笔记已存在")
        return {'success': True, 'output_file': md_file, 'skipped': True}

    assets_dir = note_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 提取关键帧并上传（使用智能检测）
    api_key_for_keyframes = get_api_key()
    keyframes = extract_and_upload_keyframes_smart(video_path, keyframe_count, use_gemini=True, api_key=api_key_for_keyframes)

    # 复制未上传的图片到 assets 目录
    for kf in keyframes:
        if not kf.get('uploaded'):
            import shutil
            dest = assets_dir / Path(kf['local_path']).name
            shutil.copy(kf['local_path'], dest)
            kf['local_relative'] = f"{assets_dir.name}/{dest.name}"

    # Gemini 分析
    try:
        analysis = analyze_with_gemini(video_path, title, language, gemini_model)
    except Exception as e:
        print(f"❌ Gemini 分析失败: {e}")
        analysis = None

    # 生成 Markdown
    print(f"\n📝 生成笔记...")
    markdown_content = build_markdown(title, video_path, keyframes, analysis)

    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"✅ 笔记已保存: {md_file}")

    # 清理临时文件
    import shutil
    shutil.rmtree(".temp_keyframes", ignore_errors=True)

    return {
        'success': True,
        'output_file': md_file,
        'note_dir': note_dir
    }


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="视频学习笔记生成器 (GitHub + jsDelivr 图床)",
        epilog="""
使用示例:
  python video_to_markdown.py -f "video.mp4"

配置说明:
  需要在 config_api.py 中配置:
  API_CONFIG = {
      "gemini": {"api_key": "your_gemini_key"},
      "github": {
          "token": "ghp_xxxxxxxxxxxx",
          "repo": "username/video-notes-assets"
      }
  }
        """
    )

    parser.add_argument('-f', '--file', help='本地视频文件路径')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_DIR,
                       help=f'输出目录（默认: {DEFAULT_OUTPUT_DIR}）')
    parser.add_argument('--keyframes', type=int, default=6,
                       help='提取关键帧数量（默认: 6）')
    parser.add_argument('--gemini-model', choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--lang', choices=['auto', 'zh', 'en'],
                       default='auto', help='输出语言（默认: auto）')
    parser.add_argument('--force', action='store_true',
                       help='覆盖已存在的笔记')

    args = parser.parse_args()

    # 检查 API Key
    if not get_api_key():
        print("❌ 未配置 Gemini API Key")
        print("\n请配置:")
        print("1. 环境变量: set GEMINI_API_KEY=your-key")
        print("2. 或在 config_api.py 中添加配置")
        return

    # 检查 GitHub 配置
    github_config = get_github_config()
    if not github_config.get('token') or not github_config.get('repo'):
        print("⚠️  未配置 GitHub Token，图片将保存为本地文件")
        print("   如需云端存储，请配置:")
        print("   API_CONFIG = {'github': {'token': 'your_token', 'repo': 'username/repo'}}")
        print()

    if not args.file:
        parser.print_help()
        return

    # 处理
    result = generate_note(
        args.file,
        output_dir=args.output,
        keyframe_count=args.keyframes,
        gemini_model=args.gemini_model,
        language=args.lang
    )

    if result.get('success'):
        print(f"\n✅ 完成!")
    else:
        print(f"\n❌ 失败: {result.get('error')}")


if __name__ == "__main__":
    main()
