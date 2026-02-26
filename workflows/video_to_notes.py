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
from typing import Dict, List, Optional, Tuple

# Tenacity for retry logic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

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
    """获取 Gemini API Key (优先级: 配置文件 > 环境变量)"""
    # 1. 优先从配置文件读取
    try:
        # 获取项目根目录 (workflows/ 的父目录)
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
    """获取 GitHub 配置 (优先级: 配置文件 > 环境变量)"""
    # 1. 优先从配置文件读取
    token = None
    repo = None
    try:
        # 获取项目根目录 (workflows/ 的父目录)
        project_root = Path(__file__).parent.parent
        config_path = project_root / 'config'
        sys.path.insert(0, str(config_path))
        from config_api import API_CONFIG
        github_config = API_CONFIG.get('github', {})
        token = github_config.get('token')
        repo = github_config.get('repo')
    except (ImportError, FileNotFoundError):
        pass

    # 2. 其次从环境变量读取
    if not token or not repo:
        token = token or os.environ.get('GITHUB_TOKEN')
        repo = repo or os.environ.get('GITHUB_REPO')

    return {'token': token, 'repo': repo}


# ==================== 关键帧提取与上传 ====================

def extract_keyframe_timestamps_with_gemini(video_path: str, api_key: str,
                                             min_count: int = 5, max_count: int = 20,
                                             min_interval: int = 3) -> List[Dict]:
    """
    使用 Gemini 分析视频，智能提取关键时间点

    Args:
        video_path: 视频文件路径
        api_key: Gemini API Key
        min_count: 最少关键帧数量
        max_count: 最多关键帧数量
        min_interval: 关键帧之间的最小间隔（秒）

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
    # 使用 format() 避免花括号转义问题
    prompt = """你是一个专业的视频分析师，擅长识别视频中的关键时刻。

请分析这个视频（时长: {duration}秒），提取有价值的关键时刻作为关键帧。

**核心原则：**
- 注重**内容变化**而非简单的画面切换
- 避免提取过于相似或重复的场景
- 确保每个关键帧都有独特的价值
- 参考数量：{min_count}-{max_count} 个

**什么样的时刻值得提取？**

**对于讲座/PPT类型视频：**
- 每个新话题/章节开始（不是每页PPT）
- 展示重要图表、公式、代码示例
- 讲师强调重点内容时

**对于新闻/资讯/盘点类视频：**
- 每个新话题/新产品的介绍开始
- 展示重要的产品界面或演示画面
- 数据图表、重要对比出现时
- 总结或结论出现的时刻

**对于Vlog/生活记录：**
- 场景明显切换（进入新环境）
- 人物活动明显变化
- 重要事件发生时刻

**什么样的时刻应该跳过？**
- 过于相似的连续场景（如多个电影片段连续出现）
- 纯过渡画面（如淡入淡出、转场）
- 重复出现的界面或内容

**输出格式：**
请严格按照以下 JSON 格式返回（只返回 JSON，不要有其他说明文字）：
```json
[
  {{"timestamp": 10.5, "description": "开场介绍，说明视频主题", "reason": "内容开始"}},
  {{"timestamp": 45.2, "description": "第一页PPT，展示核心概念框架", "reason": "重要知识点"}},
  {{"timestamp": 120.0, "description": "切换到案例分析", "reason": "实际应用"}}
]
```

**注意事项：**
1. timestamp 单位为秒，保留一位小数
2. 按时间顺序排列
3. 只返回 JSON 数组，不要有任何其他说明文字
4. 相邻关键帧之间至少间隔 {min_interval} 秒
5. **质量优先于数量**：宁缺毋滥，确保每个关键帧都有独特价值""".format(
        duration=f"{duration:.0f}",
        min_count=min_count,
        max_count=max_count,
        min_interval=min_interval
    )

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

                # 显示识别到的关键帧数量（不再截断）
                print(f"   └─ 📊 识别到 {len(keyframes)} 个关键时刻")
                return keyframes
    except json.JSONDecodeError as e:
        print(f"   └─ ⚠️  Gemini 返回格式解析失败: {e}")
        # 输出原始响应用于调试
        print(f"   └─ 📋 原始响应（前500字符）:")
        print("   " + "\n   ".join(result_text[:500].split('\n')))

    print(f"   └─ ⚠️  未能识别关键时刻，将使用默认方案")
    return []


def validate_temporal_distribution(keyframes: List[Dict], duration: float) -> List[Dict]:
    """
    验证并补充关键帧的时间分布，确保覆盖完整视频

    Args:
        keyframes: Gemini返回的关键帧列表
        duration: 视频总时长（秒）

    Returns:
        验证并可能补充后的关键帧列表
    """
    if not keyframes:
        return keyframes

    # 检查三分段覆盖率
    third = duration / 3
    segments = {
        'first': [kf for kf in keyframes if kf['timestamp'] <= third],
        'middle': [kf for kf in keyframes if third < kf['timestamp'] <= third * 2],
        'last': [kf for kf in keyframes if kf['timestamp'] > third * 2]
    }

    coverage = {k: len(v) for k, v in segments.items()}
    total = len(keyframes)
    min_coverage = total * 0.15  # 每段至少15%

    # 如果某段覆盖率不足，发出警告
    for segment_name, frames in segments.items():
        if len(frames) < min_coverage:
            segment_cn = {'first': '开头', 'middle': '中间', 'last': '结尾'}[segment_name]
            print(f"   ⚠️  警告: {segment_cn}段覆盖率不足 ({len(frames)}/{total:.0f}帧)")

    return keyframes


def get_video_duration(video_path: Path) -> float:
    """
    获取视频时长（秒）

    Args:
        video_path: 视频文件路径

    Returns:
        视频时长（秒），失败返回0
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        return 0


def calculate_adaptive_keyframe_range(video_path: Path, api_key: str = None) -> Tuple[int, int, int]:
    """
    计算自适应的关键帧数量范围

    Args:
        video_path: 视频文件路径
        api_key: Gemini API Key（可选，用于内容密度分析）

    Returns:
        (min_count, max_count, min_interval)
    """
    duration = get_video_duration(video_path)

    if duration <= 0:
        # 无法获取时长，返回保守默认值
        return 5, 15, 3

    # 基础范围计算 - 更保守的策略，避免太多帧
    # 短视频(<3分钟): 每15-20秒一帧
    # 中等视频(3-10分钟): 每20-40秒一帧
    # 长视频(>10分钟): 每40-60秒一帧
    if duration < 180:
        min_count = max(5, int(duration / 20))
        max_count = min(20, int(duration / 15))
    elif duration < 600:
        min_count = max(8, int(duration / 40))
        max_count = min(30, int(duration / 20))
    else:
        min_count = max(10, int(duration / 60))
        max_count = min(40, int(duration / 40))

    # 确保 min <= max
    if min_count > max_count:
        min_count, max_count = max_count, min_count

    # 最小间隔（确保帧之间有足够间距）
    if max_count > 0:
        min_interval = max(5, int(duration / max_count * 0.7))  # 至少5秒，或理论间隔的70%
    else:
        min_interval = 8

    print(f"   └─ 📏 根据时长 {duration:.0f}秒，建议 {min_count}-{max_count} 帧，间隔至少 {min_interval}秒")

    return min_count, max_count, min_interval


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
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps if fps > 0 else 0

    if fps <= 0:
        fps = 30  # 默认帧率

    keyframes = []
    temp_dir = Path(".temp_keyframes")
    temp_dir.mkdir(exist_ok=True)

    print(f"\n🖼️  提取关键帧 ({len(keyframe_data)} 个候选)")
    print(f"   └─ 视频实际时长: {video_duration:.1f}秒")

    # 过滤掉超出视频时长的时间戳
    valid_keyframes = [kf for kf in keyframe_data if kf['timestamp'] <= video_duration]
    invalid_count = len(keyframe_data) - len(valid_keyframes)
    if invalid_count > 0:
        print(f"   └─ ⚠️  跳过 {invalid_count} 个超出视频时长的时间戳")

    for i, kf in enumerate(valid_keyframes):
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

            print(f"  [{i+1}/{len(valid_keyframes)}] {timestamp:.1f}s - {description[:30]}...")

            keyframes.append({
                'local_path': str(local_path),
                'timestamp': timestamp,
                'description': description,
                'reason': reason,
                'uploaded': False,
                'url': None
            })
        else:
            print(f"  [{i+1}/{len(valid_keyframes)}] ⚠️  无法提取 {timestamp:.1f}s 的帧")

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


def extract_keyframes_uniform_sample(video_path: Path, count: int = 6) -> List[Dict]:
    """
    均匀采样提取关键帧（传统方案）

    Args:
        video_path: 视频文件路径
        count: 目标关键帧数量

    Returns:
        关键帧列表 [{local_path, timestamp, description, reason, uploaded, url}]
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("❌ 无法打开视频文件")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30  # 默认帧率

    interval = max(1, total_frames // count)
    keyframes = []
    temp_dir = Path(".temp_keyframes")
    temp_dir.mkdir(exist_ok=True)

    frame_idx = 0
    extracted_count = 0

    while cap.isOpened() and extracted_count < count:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % interval == 0 and extracted_count < count:
            timestamp = frame_idx / fps if fps > 0 else 0
            filename = f"keyframe_{extracted_count+1:02d}_{int(timestamp)}s.jpg"
            local_path = temp_dir / filename

            cv2.imwrite(str(local_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            print(f"  [{extracted_count+1}/{count}] 均匀采样 @ {timestamp:.0f}秒")

            keyframes.append({
                'local_path': str(local_path),
                'timestamp': timestamp,
                'description': f'采样点 @ {timestamp:.0f}秒',
                'reason': '均匀采样',
                'uploaded': False,
                'url': None
            })
            extracted_count += 1

        frame_idx += 1

    cap.release()
    return keyframes


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


def extract_and_upload_keyframes_smart(video_path: Path, count: int = None,
                                     use_gemini: bool = True,
                                     api_key: str = None) -> List[Dict]:
    """
    智能提取关键帧并上传到 GitHub 图床

    Args:
        video_path: 视频文件路径
        count: 目标关键帧数量（None 则自动计算）
        use_gemini: 是否使用 Gemini 智能检测（False 则使用均匀采样）
        api_key: Gemini API Key

    Returns:
        关键帧列表 [{local_path, timestamp, description, reason, uploaded, url}]
    """
    import cv2
    import requests
    import base64
    import uuid
    import shutil

    # 如果未指定数量，计算自适应范围
    if count is None and api_key:
        min_count, max_count, min_interval = calculate_adaptive_keyframe_range(video_path, api_key)
        # 使用中间值作为目标
        count = (min_count + max_count) // 2
    elif count is None:
        count = 10  # 默认值

    if use_gemini:
        print(f"\n🖼️  智能提取关键帧 (目标: {count} 帧)")
    else:
        print(f"\n🖼️  均匀提取关键帧 (目标: {count} 帧)")

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
            # 计算自适应范围
            min_count, max_count, min_interval = calculate_adaptive_keyframe_range(video_path, api_key)

            # 步骤1: 使用 Gemini 识别关键时间点（传入范围而非固定值）
            keyframe_data = extract_keyframe_timestamps_with_gemini(
                str(video_path), api_key, min_count, max_count, min_interval
            )

            if keyframe_data:
                # 步骤2: 根据时间点精准提取
                keyframes = extract_keyframes_at_timestamps(
                    video_path, keyframe_data
                )
                print(f"   └─ ✅ Gemini 智能检测完成")
        except Exception as e:
            print(f"   └─ ⚠️  Gemini 检测失败: {e}，使用备选方案")

    # 如果 Gemini 失败，直接报错退出
    if not keyframes:
        if use_gemini:
            print(f"   └─ ❌ Gemini 检测失败，无法继续")
            raise SystemExit("关键帧检测失败，请检查 Gemini API 配置或网络连接后重试")
        else:
            # 直接使用均匀采样
            keyframes = extract_keyframes_uniform_sample(video_path, count)

    # 上传到 GitHub
    if github_token and github_repo and keyframes:
        print(f"\n📤 上传图片到 GitHub...")
        upload_stats = {'success': 0, 'failed': 0}

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]

        for i, kf in enumerate(keyframes, 1):
            local_path = kf['local_path']
            filename = f"{timestamp_str}_{unique_id}_kf_{i:03d}.jpg"

            url = upload_to_github(local_path, github_token, github_repo, filename)
            if url:
                kf['url'] = url
                kf['uploaded'] = True
                upload_stats['success'] += 1
                print(f"  [{i}/{len(keyframes)}] ✅ 上传成功")
            else:
                kf['uploaded'] = False
                upload_stats['failed'] += 1
                print(f"  [{i}/{len(keyframes)}] ❌ 上传失败（已达最大重试次数）")

        # 上传统计
        print(f"\n📊 上传统计:")
        print(f"  成功: {upload_stats['success']}/{len(keyframes)}")
        print(f"  失败: {upload_stats['failed']}/{len(keyframes)}")
        if upload_stats['success'] + upload_stats['failed'] > 0:
            print(f"  成功率: {upload_stats['success']/(upload_stats['success']+upload_stats['failed'])*100:.1f}%")
    else:
        print(f"\n⚠️  跳过上传，使用本地图片")
        for kf in keyframes:
            kf['uploaded'] = False

    # 注意：不在这里清理临时文件，让调用方在完成复制后再清理
    # 这样可以确保即使上传失败，本地文件也能被正确复制

    return keyframes


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout
    )),
    before_sleep=lambda retry_state: print(f"    🔄 第 {retry_state.attempt_number} 次重试...")
)
def upload_to_github(image_path: Path, token: str, repo: str, filename: str = None) -> Optional[str]:
    """
    上传图片到 GitHub 并返回 jsDelivr CDN 链接（带重试机制）

    Args:
        image_path: 本地图片路径
        token: GitHub Personal Access Token
        repo: 仓库名称 (格式: username/repo-name)
        filename: 自定义文件名

    Returns:
        jsDelivr CDN URL 或 None
    """
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
            if response.status_code >= 500:
                # 服务器错误，抛出异常触发重试
                raise requests.exceptions.ServerError(f"Server error: {response.status_code}")
            return None

    except requests.exceptions.SSLError as e:
        print(f"    SSL 错误: {e}")
        raise  # 触发重试
    except requests.exceptions.ConnectionError as e:
        print(f"    连接错误: {e}")
        raise  # 触发重试
    except requests.exceptions.Timeout as e:
        print(f"    超时: {e}")
        raise  # 触发重试
    except Exception as e:
        print(f"    上传失败: {e}")
        return None  # 其他错误不重试


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

def detect_video_source(source: str) -> Dict:
    """检测视频来源

    Returns:
        {
            'type': 'local' | 'url',
            'platform': 'bilibili' | 'xiaohongshu' | 'youtube' | 'other',
            'url': 原始 URL（如果是 URL 类型）
            'file_path': 本地文件路径（如果是本地类型）
        }
    """
    if source.startswith(('http://', 'https://')):
        # URL 类型
        if 'bilibili.com' in source or 'b23.tv' in source:
            return {'type': 'url', 'platform': 'bilibili', 'url': source, 'file_path': None}
        elif 'xiaohongshu.com' in source or 'xhslink.com' in source:
            return {'type': 'url', 'platform': 'xiaohongshu', 'url': source, 'file_path': None}
        elif 'youtube.com' in source or 'youtu.be' in source:
            return {'type': 'url', 'platform': 'youtube', 'url': source, 'file_path': None}
        else:
            return {'type': 'url', 'platform': 'other', 'url': source, 'file_path': None}
    else:
        # 本地文件类型
        return {'type': 'local', 'platform': 'local', 'url': None, 'file_path': source}


def build_markdown(title: str, video_path: Path, keyframes: List[Dict],
                    analysis: str, assets_dir: str = 'assets') -> str:
    """生成 Markdown 笔记"""
    lines = []

    # 检测视频来源
    video_source = detect_video_source(str(video_path))
    source_type = video_source['type']
    platform = video_source['platform']
    original_url = video_source['url']

    # 根据视频来源生成时间戳链接
    if source_type == 'url':
        # 在线视频：生成带时间戳的链接
        if platform == 'bilibili':
            # B站：提取 BV 号或 AV 号
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(original_url)
            # 提取视频 ID（可能是 /video/BVxxx 或 ?p=xxx）
            video_id = None
            if 'bilibili.com/video/' in original_url:
                path_parts = parsed.path.split('/')
                for part in path_parts:
                    if part.startswith('BV') or part.startswith('av'):
                        video_id = part
                        break
            elif 'p=' in original_url or 'bvid=' in original_url:
                # 从 URL 参数提取
                query_params = parse_qs(parsed.query)
                video_id = query_params.get('p', [None])[0] or query_params.get('bvid', [None])[0]

            if video_id:
                # B站时间戳链接：https://www.bilibili.com/video/BVxxx/?t=seconds
                base_url = f"https://www.bilibili.com/video/{video_id}"
            else:
                base_url = original_url
        elif platform == 'youtube':
            # YouTube：使用 t 参数
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(original_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            # 其他平台：直接使用原 URL
            base_url = original_url
    else:
        # 本地视频：不需要跳转链接，只显示时间
        base_url = None

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
    lines.append(f"| **关键帧数量** | {len(keyframes)} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 关键帧
    if keyframes:
        lines.append("## 🖼️ 关键帧详解")
        lines.append("")
        lines.append(f"共 {len(keyframes)} 个关键帧")
        lines.append("")
        lines.append("*点击时间戳可跳转到视频对应位置*")
        lines.append("")

        for i, kf in enumerate(keyframes):
            timestamp = kf.get('timestamp', 0)
            description = kf.get('description', '')
            reason = kf.get('reason', '')

            # 优先使用云端 URL
            if kf.get('uploaded') and kf.get('url'):
                lines.append(f"![关键帧]({kf['url']})")
            else:
                # 回退到本地路径
                filename = Path(kf['local_path']).name
                lines.append(f"![关键帧]({assets_dir}/{filename})")

            # 时间和描述（添加跳转链接）
            time_min = int(timestamp // 60)
            time_sec = int(timestamp % 60)
            total_seconds = int(timestamp)
            # 根据视频来源生成时间戳链接
            if base_url:
                # 在线视频：生成可点击的链接
                lines.append(f"[{time_min:02d}:{time_sec:02d}]({base_url}#t={total_seconds}) - {description}")
            else:
                # 本地视频：只显示时间戳
                lines.append(f"[{time_min:02d}:{time_sec:02d}] - {description}")
            lines.append("")

            # 选择理由
            if reason:
                lines.append(f"> 💡 **选择理由**: {reason}")
                lines.append("")

            # 与下一帧之间的内容过渡
            if i < len(keyframes) - 1:
                next_kf = keyframes[i + 1]
                next_timestamp = next_kf['timestamp']
                time_gap = next_timestamp - timestamp
                next_description = next_kf.get('description', '下一场景')

                lines.append(f"📋 **接下来 {time_gap:.0f} 秒**: 从当前内容过渡到「{next_description}」")
                lines.append("")

            lines.append("---")
            lines.append("")

    # AI 分析
    if analysis:
        lines.append("---")
        lines.append("")
        lines.append("## 🧠 AI 深度分析")
        lines.append("")
        lines.append(analysis)
        lines.append("")

    # 个人笔记
    lines.append("---")
    lines.append("")
    lines.append("## 📝 我的笔记")
    lines.append("")
    lines.append("> ✨ 在这里添加你的个人思考、疑问和总结")
    lines.append("")

    return "\n".join(lines)


# ==================== 主流程 ====================

def calculate_optimal_keyframe_count(video_path: Path, user_override: int = None,
                                     api_key: str = None) -> int:
    """
    根据视频内容动态计算最优关键帧数量

    优先使用 Gemini 分析视频内容来决定关键帧数量，
    如果 Gemini 不可用，则回退到时长估算。

    Args:
        video_path: 视频文件路径
        user_override: 用户指定的数量（如果提供，则直接使用）
        api_key: Gemini API Key

    Returns:
        计算得到的关键帧数量
    """
    # 如果用户明确指定，直接使用
    if user_override is not None:
        return user_override

    # 优先尝试用 Gemini 分析视频内容
    if api_key:
        gemini_estimate = estimate_keyframes_with_gemini(video_path, api_key)
        if gemini_estimate:
            return gemini_estimate

    # 回退方案：基于视频时长
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        duration = 0

    if duration <= 0:
        return 6  # 默认值

    # 更细粒度的时长策略（作为回退）
    if duration < 60:
        count = 4
        reason = "短视频"
    elif duration < 180:
        count = 8
        reason = "中等视频"
    elif duration < 600:
        count = 12
        reason = "较长视频"
    elif duration < 1800:
        count = 18
        reason = "长视频"
    else:
        count = min(25, int(duration / 60))  # 每分钟约1帧
        reason = "超长视频"

    print(f"   └─ 📏 时长估算: {duration:.0f}秒，{reason}，建议 {count} 个关键帧")
    return count


def estimate_keyframes_with_gemini(video_path: Path, api_key: str) -> Optional[int]:
    """
    使用 Gemini 快速分析视频，估计最优关键帧数量

    这是一个轻量级的分析，只返回建议的数量，不需要详细的时间点。

    Returns:
        建议的关键帧数量，或 None（分析失败）
    """
    import google.generativeai as genai
    import time

    try:
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

        print(f"   └─ 🤖 Gemini 分析视频内容...")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # 上传视频
        video_file = genai.upload_file(path=str(video_path))

        # 等待处理完成
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name != "ACTIVE":
            genai.delete_file(video_file.name)
            return None

        # 简化的提示词 - 只需要估计数量
        prompt = f"""分析这个视频（时长: {duration:.0f}秒），回答以下问题：

1. 这个视频是什么类型？（讲座/Vlog/教程/新闻/其他）
2. 视频内容的丰富程度如何？（简单/中等/丰富）
3. 你认为这个视频需要提取多少个关键帧才能充分展示其内容？

请只返回一个数字（建议的关键帧数量，3-25之间），不要有其他说明。

例如：
- 短教程：返回 4
- 中等长度的技术讲解：返回 8-12
- 长讲座：返回 15-20"""

        response = model.generate_content([video_file, prompt])
        genai.delete_file(video_file.name)

        # 解析响应
        result = response.text.strip()

        # 尝试提取数字
        import re
        numbers = re.findall(r'\d+', result)

        if numbers:
            count = int(numbers[0])
            count = max(3, min(25, count))  # 限制在 3-25 之间
            print(f"   └─ 📊 Gemini 建议: {count} 个关键帧")
            return count

    except Exception as e:
        # 静默失败
        pass

    return None


def analyze_subtitle_information_density(video_path: Path) -> Optional[Dict]:
    """
    分析视频字幕的信息密度

    Returns:
        {
            'density_score': float,  # 0-1 之间的信息密度分数
            'topic_count': int,      # 估计的话题数量
            'word_count': int,       # 总字数
            'has_subtitle': bool     # 是否有字幕
        }
        或 None（无法获取字幕）
    """
    import yt_dlp
    import re

    try:
        # 尝试从视频文件名或元数据获取URL
        # 如果是本地文件，尝试从文件名推测BV号
        bvid_match = re.search(r'BV[\w]+', str(video_path))
        url = None

        if bvid_match:
            bvid = bvid_match.group(0)
            url = f"https://www.bilibili.com/video/{bvid}"

        if not url:
            return None

        # 获取字幕
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-Hans', 'zh-Hant', 'zh'],
            'subtitlesformat': 'srt',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # 检查是否有字幕
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})

            if not subtitles and not automatic_captions:
                return None

            # 优先使用人工字幕
            sub_data = None
            if subtitles:
                for lang in ['zh-Hans', 'zh-Hant', 'zh']:
                    if lang in subtitles:
                        sub_data = subtitles[lang]
                        break
            elif automatic_captions:
                for lang in ['zh-Hans', 'zh-Hant', 'zh']:
                    if lang in automatic_captions:
                        sub_data = automatic_captions[lang]
                        break

            if not sub_data or not sub_data.get('url'):
                return None

            # 下载字幕内容
            import requests
            response = requests.get(sub_data['url'], timeout=10)
            subtitle_text = response.text

            # 分析字幕内容
            return analyze_subtitle_content(subtitle_text)

    except Exception as e:
        # 静默失败，返回 None
        return None


def analyze_subtitle_content(srt_content: str) -> Dict:
    """
    分析 SRT 字幕内容的信息密度

    Args:
        srt_content: SRT 格式的字幕内容

    Returns:
        信息密度分析结果
    """
    # 提取纯文本（去掉时间码和序号）
    lines = srt_content.split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        # 跳过序号行和时间码行
        if not line or line.isdigit() or '-->' in line:
            continue
        # 跳过常见的字幕格式标记
        if line.startswith('\\') or line.startswith('[', ) or line.startswith('('):
            continue
        text_lines.append(line)

    full_text = ' '.join(text_lines)

    # 基础统计
    char_count = len(full_text)
    word_count = len(full_text.split())

    if word_count < 10:
        return {
            'density_score': 0.1,
            'topic_count': 1,
            'word_count': word_count,
            'has_subtitle': True
        }

    # 信息密度指标
    # 1. 关键词密度（技术术语、专业词汇等）
    tech_keywords = [
        '算法', '模型', '数据', 'AI', '人工智能', '机器学习', '深度学习',
        '框架', '架构', '原理', '技术', '方法', '实现', '应用',
        '代码', '编程', '开发', '系统', '设计', '优化',
        '神经', '网络', '训练', '推理', '参数', '层',
        'Transformer', 'Attention', 'BERT', 'GPT', 'LLM',
        '视频', '图像', '音频', '处理', '识别', '检测',
        'API', '接口', '函数', '类', '对象', '变量'
    ]

    keyword_hits = sum(1 for kw in tech_keywords if kw in full_text)
    keyword_density = keyword_hits / max(1, word_count / 50)  # 每50字的期望关键词数

    # 2. 句子复杂度（平均句长）
    sentences = re.split(r'[。！？!?]', full_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = sum(len(s.split()) for s in sentences) / max(1, len(sentences))

    # 3. 话题切换频率（基于段落分隔或明显的停顿）
    # SRT 中长的时间间隔通常表示话题切换
    time_intervals = re.findall(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', srt_content)

    gap_count = 0
    for i in range(1, len(time_intervals)):
        prev_end = time_intervals[i-1][1]
        curr_start = time_intervals[i][0]

        # 解析时间
        def parse_time(t):
            h, m, s_ms = t.split(':')
            s, ms = s_ms.split(',')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        prev_end_sec = parse_time(prev_end)
        curr_start_sec = parse_time(curr_start)

        # 间隔超过2秒认为是话题切换
        if curr_start_sec - prev_end_sec > 2:
            gap_count += 1

    # 综合计算信息密度分数 (0-1)
    density_score = min(1.0, (
        keyword_density * 0.3 +           # 关键词贡献30%
        min(1.0, avg_sentence_length / 20) * 0.3 +  # 句长贡献30%
        min(1.0, gap_count / 10) * 0.4    # 话题切换贡献40%
    ))

    # 估计话题数量（基于间隔和字数）
    topic_count = max(3, int(gap_count * 0.8) + int(word_count / 300))
    topic_count = min(30, topic_count)  # 最多30个话题

    return {
        'density_score': density_score,
        'topic_count': topic_count,
        'word_count': word_count,
        'has_subtitle': True
    }


def generate_note(source: str, output_dir: str = DEFAULT_OUTPUT_DIR,
                  keyframe_count: int = None, gemini_model: str = 'flash-lite',
                  language: str = 'auto', use_gemini: bool = True) -> Dict:
    """生成视频学习笔记

    Args:
        source: 视频文件路径
        output_dir: 输出目录
        keyframe_count: 关键帧数量（None 则自动计算）
        gemini_model: Gemini 模型
        language: 输出语言
        use_gemini: 是否使用 Gemini 智能检测关键帧
    """
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

    # 获取API密钥
    api_key = get_api_key() if use_gemini else None

    # 提取关键帧并上传（函数内部会自动计算自适应范围）
    # 如果用户指定了 keyframe_count，则使用用户指定的值
    keyframes = extract_and_upload_keyframes_smart(
        video_path,
        count=keyframe_count,  # 传入用户指定的值或None（自动计算）
        use_gemini=use_gemini,
        api_key=api_key
    )

    # 验证时间分布
    if keyframes:
        duration = get_video_duration(video_path)
        if duration > 0:
            validate_temporal_distribution(keyframes, duration)

    # 复制未上传的图片到 assets 目录
    import shutil
    for kf in keyframes:
        if not kf.get('uploaded'):
            local_path = Path(kf['local_path'])
            if local_path.exists():
                dest = assets_dir / local_path.name
                shutil.copy(str(local_path), dest)
                kf['local_relative'] = f"{assets_dir.name}/{dest.name}"
            else:
                print(f"⚠️  本地文件不存在，跳过: {local_path.name}")

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
        description="视频学习笔记生成器 (GitHub + jsDelivr 图床 + Gemini 智能关键帧检测)",
        epilog="""
使用示例:
  python video_to_markdown.py -f "video.mp4"
  python video_to_markdown.py -f "video.mp4" --keyframes 12
  python video_to_markdown.py -f "video.mp4" --no-gemini

关键帧检测模式:
  - Gemini 智能检测（默认）: AI 理解视频内容，精准提取关键时刻
  - 传统均匀采样（--no-gemini）: 按固定间隔提取关键帧

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

    parser.add_argument('-f', '--file', help='本地视频文件路径 或视频 URL（自动下载）')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_DIR,
                       help=f'输出目录（默认: {DEFAULT_OUTPUT_DIR}）')
    parser.add_argument('--keyframes', type=int, default=None,
                       help='提取关键帧数量（默认: 根据视频时长自动计算）')
    parser.add_argument('--gemini-model', choices=['flash', 'flash-lite', 'pro'],
                       default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--lang', choices=['auto', 'zh', 'en'],
                       default='auto', help='输出语言（默认: auto）')
    parser.add_argument('--force', action='store_true',
                       help='覆盖已存在的笔记')
    parser.add_argument('--no-gemini', action='store_true',
                       help='禁用 Gemini 智能检测，使用传统均匀采样')

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
        return 1

    # 处理
    result = generate_note(
        args.file,
        output_dir=args.output,
        keyframe_count=args.keyframes,
        gemini_model=args.gemini_model,
        language=args.lang,
        use_gemini=not args.no_gemini
    )

    if result.get('success'):
        print(f"\n✅ 完成!")
        # 返回生成的文件路径信息
        output_file = result.get('output_file')
        if output_file:
            print(f"📁 输出文件: {output_file}")
        return 0
    else:
        print(f"\n❌ 失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
