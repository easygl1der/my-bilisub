#!/usr/bin/env python3
"""
Telegram Bot with Natural Language Understanding (Conversational Version)

Users can send natural language commands that are parsed by Gemini AI
and converted to structured commands for auto_content_workflow.py

Features:
- Multi-turn dialogue with Gemini
- Confirmation before command execution
- File discovery and selection after execution
"""

import os
import sys
import json
import asyncio
import subprocess
import time
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Import Telegram
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    print("❌ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")
    sys.exit(1)

# Import Gemini
try:
    from analysis.subtitle_analyzer import GeminiClient
except ImportError:
    print("❌ 无法导入 GeminiClient")
    print("请确保 analysis/subtitle_analyzer.py 存在")
    sys.exit(1)

# ==================== Output Formatting ====================

def format_gemini_output(text: str) -> str:
    """Format Gemini output for better readability"""
    # Clean up
    text = text.strip()

    # Add spacing around sections
    text = text.replace("\n\n", "\n\n\n")

    # Highlight keywords
    keywords = ["命令:", "参数:", "URL:", "模式:", "说明:", "文件:", "选择:"]
    for kw in keywords:
        text = text.replace(kw, f"**{kw}**")

    return text


# ==================== Configuration ====================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "bot_config_1.json"

def load_config() -> Dict:
    """Load configuration from config file"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
BOT_TOKEN = config.get('bot_token')
GEMINI_API_KEY = config.get('gemini_api_key')
ALLOWED_USERS = config.get('allowed_users', [])

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    print(f"请在 {CONFIG_PATH} 中配置 bot_token")
    sys.exit(1)

if not GEMINI_API_KEY:
    print("❌ 未配置 Gemini API Key")
    print(f"请在 {CONFIG_PATH} 中配置 gemini_api_key")
    sys.exit(1)


# ==================== Conversation State Management ====================

@dataclass
class ConversationState:
    """Track conversation state per user"""
    phase: str = "dialogue"  # "dialogue" | "confirm" | "file_select"
    history: List[str] = field(default_factory=list)  # Conversation history with Gemini
    pending_command: Optional[Dict] = None  # Command waiting for confirmation
    generated_files: List[Dict] = field(default_factory=list)  # Files from last execution
    process: Optional[object] = None  # Currently running subprocess

    def clear(self):
        """Clear conversation state"""
        self.phase = "dialogue"
        self.history = []
        self.pending_command = None
        self.generated_files = []
        self.process = None


# Global state manager
user_states = {}  # {user_id: ConversationState}
user_processes = {}  # {user_id: asyncio.subprocess.Process}


def get_user_state(user_id: int) -> ConversationState:
    """Get or create conversation state for user"""
    if user_id not in user_states:
        user_states[user_id] = ConversationState()
    return user_states[user_id]


def get_user_process(user_id: int) -> Optional[object]:
    """Get currently running process for user"""
    return user_processes.get(user_id)


def set_user_process(user_id: int, process: object):
    """Set currently running process for user"""
    user_processes[user_id] = process


def clear_user_process(user_id: int):
    """Clear process for user"""
    if user_id in user_processes:
        del user_processes[user_id]


# ==================== Command Map ====================

COMMAND_MAP = {
    "download": {
        "script": "auto_content_workflow.py",
        "base_args": [],
        "url_arg_pos": 0,
        "description": "下载视频"
    },
    "subtitle": {
        "script": "auto_content_workflow.py",
        "base_args": ["--bili-mode", "subtitle"],
        "url_arg_pos": 0,
        "description": "B站字幕分析"
    },
    "notes": {
        "script": "auto_content_workflow.py",
        "base_args": ["--generate-notes"],
        "url_arg_pos": 0,
        "description": "生成学习笔记"
    },
    "comments": {
        "script": "auto_content_workflow.py",
        "base_args": ["--fetch-comments"],
        "url_arg_pos": 0,
        "description": "爬取评论"
    },
    "auto": {
        "script": "auto_content_workflow.py",
        "base_args": [],
        "url_arg_pos": 0,
        "description": "智能自动处理"
    },
    "bili_auto": {
        "script": "auto_content_workflow.py",
        "base_args": ["--bili-mode", "subtitle", "--fetch-comments"],
        "url_arg_pos": 0,
        "description": "B站组合处理（字幕+评论）"
    },
    "scrape_bilibili": {
        "script": "workflows/ai_bilibili_homepage.py",
        "base_args": ["--mode", "full"],
        "url_arg_pos": None,
        "description": "刷B站首页推荐"
    },
    "scrape_xiaohongshu": {
        "script": "workflows/ai_xiaohongshu_homepage.py",
        "base_args": ["--mode", "full"],
        "url_arg_pos": None,
        "description": "刷小红书推荐"
    }
}


# ==================== Gemini Prompt ====================

COMMAND_DESCRIPTIONS = """你现在是一个"命令解析助手"，负责与用户进行多轮对话，理解用户需求并转换成结构化的 JSON 指令，供后端的 Telegram Bot 调用本地 Python 脚本使用。

## 对话规则：

1. **不理解时主动提问**：不要直接返回错误，而是问用户澄清问题
   - 例子："你想要下载这个视频，还是分析它的字幕？"
   - 例子："你想爬取多少条评论？"

2. **缺少参数时询问**：当必要参数缺失时，友好地询问
   - 例子："请提供视频链接"
   - 例子："你需要指定评论数量吗？默认是100条"

3. **确认执行**：完全理解用户意图后，先总结再询问确认
   - 不要立即执行命令
   - 用自然语言总结理解的结果
   - 询问用户是否确认（回复"确认"、"执行"、"开始"等）

4. **多轮对话**：支持多轮来回对话直到完全理解
   - 保持对话历史
   - 引用之前的对话内容
   - 逐步澄清不明确的地方

## 执行后文件选择流程：

当命令执行完成后，我会给你列出所有生成的文件，你需要：
1. 用自然语言总结生成的文件列表
2. 询问用户想要哪些文件（全部发送、只特定类型、或用户指定）
3. 等待用户用自然语言回复选择
4. 根据用户选择，返回文件列表（用简单的方式描述，如索引1,3,5）

## 项目结构说明：

执行命令后，文件会保存到以下位置：

1. 下载的视频：
   - B站：test_downloads/[UP主名]/视频文件.mp4
   - 小红书：test_downloads/xhs/视频文件.mp4
   - YouTube：test_downloads/youtube/视频文件.mp4

2. B站字幕：
   - MediaCrawler/bilibili_subtitles/[UP主名]/[标题]_AI总结.md
   - MediaCrawler/bilibili_subtitles/[UP主名]/[标题]_zh.srt

3. 学习笔记：
   - learning_notes/[视频标题]_学习笔记.md
   - learning_notes/[视频标题]_学习笔记/assets/关键帧图片

4. 评论数据：
   - B站：bili_comments_output/bili_comments_BV号_时间戳.json
   - 小红书：xhs_comments_output/xhs_comments_ID_时间戳.json

5. 分析报告：
   - B站首页：MediaCrawler/bilibili_subtitles/homepage_日期_AI总结.md
   - B站首页：MediaCrawler/bilibili_videos/homepage_videos_日期.csv
   - 小红书首页：output/xiaohongshu_homepage/xiaohongshu_homepage_日期_AI报告.md
   - 小红书图文：xhs_analysis/[用户名]_[标题]_时间戳.md

文件时间戳格式：YYYY-MM-DD_HHMMSS

## 可用命令：

- `download`：下载视频
  - url：必填，视频链接（B站/小红书/YouTube）
  - --info-only：可选，只获取信息不下载
  - -o 或 --output：可选，输出目录路径

- `subtitle`：B站字幕分析
  - url：必填，B站视频链接
  - -m 或 --model：可选，Gemini模型（flash/flash-lite/pro），默认flash-lite

- `notes`：生成学习笔记
  - url：必填，视频链接
  - -m 或 --model：可选，Gemini模型（flash/flash-lite/pro），默认flash-lite
  - --keyframes：可选，关键帧数量
  - --no-gemini：可选，禁用Gemini智能检测
  - --upload-github：可选，上传图片到GitHub CDN

- `comments`：爬取评论
  - url：必填，内容链接（B站/小红书）
  - -c 或 --comment-count：可选，评论数量，默认50
  - --only-liked：可选（仅B站），只爬有点赞数的主评论
  - --comments-only：可选（仅B站），只爬取评论不下载视频
  - --headless：可选（仅小红书），无头模式

- `auto`：智能自动处理
  - url：必填，内容链接
  - 其他可选参数同上

- `bili_auto`：B站组合处理（字幕分析+评论）
  - url：必填，B站视频链接
  - -c 或 --comment-count：可选，评论数量，默认50
  - -m 或 --model：可选，Gemini模型，默认flash-lite

- `scrape_bilibili`：刷B站首页推荐
  - --refresh-count：可选，刷新次数，默认3
  - --max-videos：可选，最多视频数，默认50
  - --mode：可选，运行模式（scrape/scrape+subtitle/full），默认full
  - -m 或 --model：可选，Gemini模型，默认flash-lite

- `scrape_xiaohongshu`：刷小红书推荐
  - --refresh-count：可选，刷新次数，默认3
  - --max-notes：可选，最多笔记数，默认50
  - --mode：可选，运行模式（scrape/full），默认full
  - --headless：可选，无头模式

## 返回格式：

### 对话模式（需要澄清或确认）：
```json
{
  "mode": "dialogue",
  "response": "向用户提出的文字或问题"
}
```

### 确认模式（准备执行）：
```json
{
  "mode": "confirm",
  "command": "命令名",
  "args": ["参数1", "参数2"],
  "url": "URL（如果有）",
  "summary": "向用户确认的简短描述"
}
```

### 文件选择模式（执行后）：
这里不使用JSON，直接用自然语言询问用户，用户也用自然语言回答。

## 任务流程：

1. 阅读用户的自然语言输入（中文或英文）
2. 如果需要更多信息，主动提问
3. 如果完全理解，返回确认模式
4. 保持对话历史，支持多轮对话
5. 输出必须是合法JSON（对话和确认模式）
6. 支持平台识别：B站（bilibili.com, b23.tv）、小红书（xiaohongshu.com, xhslink.com）、YouTube（youtube.com, youtu.be）
7. 不要杜撰不存在的命令名
8. 如果缺少必填参数，视为无法理解，返回错误

现在，请等待用户的自然语言输入，每次只对单条输入生成一份 JSON。
"""


async def chat_with_gemini(user_input: str, history: List[str], context: str = "") -> Dict:
    """Conversational chat with Gemini with improved context management"""
    try:
        client = GeminiClient(model='flash-lite', api_key=GEMINI_API_KEY)

        # Build prompt with improved context
        context_summary = build_context_summary(history, context)

        history_text = ""
        if history:
            # Format as user/bot conversation for clarity
            formatted_history = []
            for i, msg in enumerate(history[-6:]):  # Keep last 6 messages
                role = "用户" if i % 2 == 0 else "Bot"
                formatted_history.append(f"{role}: {msg}")
            history_text = "\n".join(formatted_history) + "\n\n"

        context_text = f"\n{context}" if context else ""

        # Add explicit context reminder for Gemini
        context_reminder = """
【重要提示】
- 请记住对话中已经提供的关键信息（如视频URL）
- 如果用户已提供视频链接，不要再问"是哪个视频"
- 对话应该自然推进，不要重复问已回答过的问题
- 根据已有信息直接推断用户意图
- **必须返回纯JSON格式，不要有任何其他文字**
"""

        prompt = f"{COMMAND_DESCRIPTIONS}\n\n{context_summary}{history_text}{context_reminder}\n\n当前用户说：{user_input}"

        # Debug: Print prompt (can be removed later)
        print(f"\n🔍 [DEBUG] Prompt length: {len(prompt)} chars")
        print(f"🔍 [DEBUG] User input: {user_input}")

        # Retry mechanism for Gemini API
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            response = client.generate_content(prompt)

            if response.get('success'):
                # Success! Break retry loop
                break
            else:
                last_error = response.get('error', 'Unknown error')
                print(f"❌ [DEBUG] Gemini API attempt {attempt + 1}/{max_retries} failed: {last_error}")
                if attempt < max_retries - 1:
                    # Wait before retry
                    await asyncio.sleep(1)

        if not response.get('success'):
            print(f"❌ [DEBUG] Gemini API failed after {max_retries} attempts: {last_error}")
            return {"mode": "error", "response": f"Gemini调用失败（已重试{max_retries}次）: {last_error}"}

        # Debug: Print raw response
        raw_text = response['text']
        print(f"📥 [DEBUG] Gemini raw response length: {len(raw_text)} chars")
        print(f"📥 [DEBUG] First 200 chars: {raw_text[:200]}")

        # Clean and parse JSON
        text = raw_text.strip()

        # Try to extract JSON from various formats
        if not text:
            print("❌ [DEBUG] Empty response from Gemini")
            return {"mode": "error", "response": "Gemini返回空内容"}

        # Remove common JSON markers
        text = text.replace("```json", "").replace("```", "").strip()

        # Try to find JSON object boundaries
        if text.startswith("{"):
            # Good, looks like JSON
            pass
        else:
            # Try to find JSON in the text
            import re
            json_match = re.search(r'\{[^{}]*\{.*\}[^{}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
                print(f"🔧 [DEBUG] Extracted JSON from text")
            else:
                print(f"❌ [DEBUG] No JSON found in response")
                return {"mode": "error", "response": f"Gemini未返回有效JSON。原始内容: {text[:100]}..."}

        try:
            parsed = json.loads(text)
            print(f"✅ [DEBUG] JSON parsed successfully")
            return parsed
        except json.JSONDecodeError as e:
            print(f"❌ [DEBUG] JSON decode error: {e}")
            print(f"❌ [DEBUG] Text that failed to parse: {text[:500]}")
            return {"mode": "error", "response": f"无法解析Gemini返回的JSON: {str(e)}\n\n原始内容: {text[:200]}"}

    except Exception as e:
        print(f"❌ [DEBUG] Unexpected error: {type(e).__name__}: {e}")
        return {"mode": "error", "response": f"解析错误: {str(e)}"}


# ==================== File Discovery ====================

def build_context_summary(history: List[str], context: str) -> str:
    """Build a summary of key information from conversation history"""
    if not history:
        return ""

    # Extract key information from conversation
    info_items = []

    # Look for URLs
    import re
    url_pattern = r'(https?://[^\s]+)'
    for msg in history[-6:]:  # Check last 6 messages
        urls = re.findall(url_pattern, msg)
        for url in urls:
            if url not in [item.get('url', '') for item in info_items]:
                info_items.append(f"• 视频链接: {url}")

    # Look for command decisions
    command_keywords = ['命令', '执行', '确认', 'download', 'subtitle', 'notes', 'comments', 'scrape']
    for msg in history[-4:]:  # Check last 4 messages for decisions
        if any(kw in msg.lower() for kw in command_keywords):
            if msg not in info_items:
                info_items.append(f"• 用户选择: {msg[:50]}")

    # Add context if provided
    if context:
        info_items.append(f"• 当前上下文: {context[:50]}")

    if info_items:
        return "\n".join(info_items)
    return ""


def get_file_type(file_path: Path) -> str:
    """Determine file type based on path"""
    path_str = str(file_path).lower()

    if any(x in path_str for x in ['.mp4', '.mkv', '.avi', '.mov']):
        return "视频文件"
    elif any(x in path_str for x in ['.srt', '.vtt', '.ass']):
        return "字幕文件"
    elif any(x in path_str for x in ['.json', '.csv']):
        return "数据文件"
    elif any(x in path_str for x in ['.md', '.txt']):
        return "文档文件"
    elif any(x in path_str for x in ['.jpg', '.jpeg', '.png', '.webp']):
        return "图片文件"
    else:
        return "其他文件"


def find_generated_files(project_root: Path, command: str = None) -> List[Dict]:
    """Find files generated by recent command execution (within last 5 minutes)"""
    now = time.time()
    results = []

    # Directories to search based on command
    search_dirs = [
        project_root / "test_downloads",
        project_root / "downloaded_videos",
        project_root / "output",
        project_root / "MediaCrawler" / "bilibili_subtitles",
        project_root / "learning_notes",
        project_root / "bili_comments_output",
        project_root / "xhs_comments_output",
        project_root / "xhs_analysis",
        project_root / "xhs_images",
    ]

    # For scrape commands, also search for AI summary files specifically
    ai_summary_pattern = None
    if command == "scrape_bilibili":
        ai_summary_pattern = "homepage_*_AI总结.md"
    elif command == "scrape_xiaohongshu":
        ai_summary_pattern = "xiaohongshu_homepage_*_AI报告.md"

    # First, look for AI summary files (priority)
    if ai_summary_pattern:
        if command == "scrape_bilibili":
            summary_dir = project_root / "MediaCrawler" / "bilibili_subtitles"
        else:  # scrape_xiaohongshu
            summary_dir = project_root / "output" / "xiaohongshu_homepage"

        if summary_dir.exists():
            for file in summary_dir.glob(ai_summary_pattern):
                if file.is_file() and (now - file.stat().st_mtime) < 600:  # 10 minutes for scrape commands
                    size = file.stat().st_size
                    size_mb = size / 1024 / 1024
                    size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size_mb*1024:.0f} KB"

                    results.insert(0, {  # Insert at beginning (priority)
                        "path": str(file),
                        "name": file.name,
                        "type": "AI分析报告",
                        "size_str": size_str,
                        "is_ai_summary": True  # Mark as AI summary
                    })

    # Then search for other files
    for dir_path in search_dirs:
        if not dir_path.exists():
            continue

        for file in dir_path.rglob("*"):
            if file.is_file():
                # Check if file was created recently (within 5 minutes)
                if (now - file.stat().st_mtime) < 300:
                    size = file.stat().st_size
                    size_mb = size / 1024 / 1024
                    size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size_mb*1024:.0f} KB"

                    # Skip if it's already in results (AI summary)
                    if any(r['path'] == str(file) for r in results):
                        continue

                    results.append({
                        "path": str(file),
                        "name": file.name,
                        "type": get_file_type(file),
                        "size_str": size_str
                    })

    return results


def read_ai_summary(file_path: Path) -> str:
    """Read AI summary file and return its content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Limit to 4000 chars for Telegram message
        if len(content) > 4000:
            content = content[:3900] + "\n\n...(内容过长，已截断，完整内容请查看文件)"
        return content
    except Exception as e:
        return f"无法读取AI报告: {str(e)}"


async def parse_file_selection(user_input: str, available_files: List[Dict]) -> List[int]:
    """Parse user's file selection using Gemini"""
    if not available_files:
        return []

    file_list = "\n".join(
        f"{i+1}. {f['name']} ({f['type']}, {f['size_str']})"
        for i, f in enumerate(available_files)
    )

    prompt = f"""我生成了以下文件：

{file_list}

用户说：{user_input}

请返回用户选择的文件索引列表（如 [1, 3, 5]）。
如果用户说"全部"或"全部发送"，返回所有索引 [0, 1, 2, ...]。
如果用户说只要某种类型（如"只要文档"），返回对应类型的索引。
只返回数字列表，不要其他文字。
"""

    try:
        client = GeminiClient(model='flash-lite', api_key=GEMINI_API_KEY)
        response = client.generate_content(prompt)

        if response.get('success'):
            text = response['text'].strip()
            # Try to parse as list
            match = re.search(r'\[([\d\s,]+)\]', text)
            if match:
                indices_str = match.group(1)
                indices = [int(x.strip()) for x in indices_str.split(',') if x.strip().isdigit()]
                return indices

        return []  # Default: return empty if parsing fails

    except Exception:
        return []


async def send_selected_files(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           file_indices: List[int], available_files: List[Dict]):
    """Send selected files to user with JSON file handling"""
    for idx in file_indices:
        if idx < len(available_files):
            file_info = available_files[idx]
            file_path = Path(file_info["path"])
            file_name = file_info["name"]
            file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''

            if file_path.exists():
                try:
                    # Check if it's a JSON file
                    if file_ext == 'json':
                        # Read JSON as text
                        with open(file_path, 'r', encoding='utf-8') as f:
                            json_content = f.read()

                        # If JSON is small (< 4000 chars), send as text message
                        if len(json_content) < 4000:
                            # Format for better readability
                            formatted_json = json.dumps(json.loads(json_content), ensure_ascii=False, indent=2)

                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"📄 **JSON文件**\n\n"
                                    f"**文件名**: {file_info['name']}\n"
                                    f"**大小**: {file_info['size_str']}\n"
                                    f"---\n"
                                    f"```json\n{formatted_json}\n```"
                            )
                        else:
                            # Split into chunks and send multiple messages
                            chunk_size = 3500  # Leave room for headers
                            chunks = [json_content[i:i+chunk_size]
                                     for i in range(0, len(json_content), chunk_size)]

                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"📄 **JSON文件 (分片发送)**\n\n"
                                    f"**文件名**: {file_info['name']}\n"
                                    f"**大小**: {file_info['size_str']}\n"
                                    f"**总长度**: {len(json_content):,} 字符\n"
                                    f"**分**: {len(chunks)} 部分"
                            )

                            for i, chunk in enumerate(chunks, 1):
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=f"📄 第 {i}/{len(chunks)} 部分：\n\n```json\n{chunk}\n```"
                                )
                    else:
                        # Non-JSON file, send as document
                        with open(file_path, "rb") as f:
                            await context.bot.send_document(
                                chat_id=update.effective_chat.id,
                                document=f,
                                filename=file_info["name"],
                                caption=f"{file_info['type']} - {file_info['size_str']}"
                            )
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚠️ 发送文件失败: {file_info['name']}\n错误: {str(e)}"
                    )


# ==================== Bot Commands ====================

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop currently running process for user"""
    user_id = update.effective_user.id

    # Check user authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Get currently running process
    process = get_user_process(user_id)
    state = get_user_state(user_id)

    if not process:
        await update.message.reply_text("ℹ️ 你当前没有正在运行的命令")
        return

    try:
        # Try to terminate the process
        if hasattr(process, 'terminate'):
            process.terminate()
            await asyncio.sleep(1)  # Give it a moment to terminate gracefully

        # If still running, kill it
        if hasattr(process, 'poll') and process.poll() is None:
            if hasattr(process, 'kill'):
                process.kill()
                await asyncio.sleep(0.5)

        # Clear process and state
        clear_user_process(user_id)
        state.clear()

        await update.message.reply_text("✅ 已停止当前运行的命令")

    except ProcessLookupError:
        # Process already ended
        clear_user_process(user_id)
        await update.message.reply_text("✅ 命令已结束")
    except Exception as e:
        await update.message.reply_text(f"❌ 停止命令时出错: {str(e)}")
        # Still try to clear
        clear_user_process(user_id)
        state.clear()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id

    # Check user authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Clear conversation state
    get_user_state(user_id).clear()

    help_text = """👋 你好！我是**智能内容处理 Bot**

我会通过对话理解你的需求，自动执行对应的命令。

🎯 **使用方法**
`/ask 你想做什么`

💡 **对话式交互**
✨ 支持多轮对话，我会主动提问确认你的需求
✨ 执行前会先确认，避免误操作
✨ 执行后展示生成的文件，让你选择需要的部分

🛑 **停止运行**
`/stop` - 停止当前正在运行的命令

📄 **读取文件**
`/read` - 读取已生成的文件内容
用法：
  • `/read` - 列出所有可读取的文件
  • `/read 文件编号` - 读取指定文件
  • `/read 文件名` - 按名称查找文件（支持模糊搜索）

📝 **示例对话**

示例 3 - 文件读取：
```
你: /ask 爬取评论
Bot: ✅ 执行完成！
     我生成了以下文件：
     1. 视频字幕 SRT 文件 (2.3 MB)
     2. AI 分析报告 (15 KB)
     3. 评论数据 JSON (450 KB)

     你想要哪些？可以：
     • 全部发送
     • 只要特定类型（如'只要文档'）
     • 指定文件编号

     用自然语言回复即可

你: /read 1
Bot: 📄 **文档文件**
     **文件名**: 视频字幕 SRT 文件
     **大小**: 2.3 MB
     ---
     [文件内容...]

你: /read AI分析报告
Bot: 📄 **文档文件**
     **文件名**: AI 分析报告
     **大小**: 15 KB
     ---
     [AI分析内容...]
```

示例 4 - 文件选择：

示例 1 - 基础操作：
```
你: /ask 帮我处理这个视频 https://www.bilibili.com/video/BV1xxx
我: 你想对这个视频做什么？
   1. 下载视频
   2. 分析字幕
   3. 生成学习笔记
   4. 爬取评论
你: 字幕分析
我: 你要爬取多少条评论？默认是100条
你: 50条就行
我: ✅ 我理解你想：
   • 对B站视频进行字幕分析
   • 同时爬取50条评论

   确认执行吗？（回复"确认"或"执行"）
```

示例 2 - 文件选择：
```
我: ⏳ 正在执行...
   ✅ 执行完成！

   我生成了以下文件：
   1. 视频字幕 SRT 文件 (2.3 MB)
   2. AI 分析报告 (15 KB)
   3. 评论数据 JSON (450 KB)

   你想要哪些？可以全部发送，或选择特定类型。

你: 全部发送
我: 📤 正在发送文件...
   ✅ 已发送 3 个文件
```

🎁 **支持平台**
• B站 (bilibili.com, b23.tv)
• 小红书 (xiaohongshu.com, xhslink.com)
• YouTube (youtube.com, youtu.be)

📌 **可用功能**
• 下载视频 / 只获取信息
• B站字幕分析
• 生成学习笔记
• 爬取评论
• 刷B站/小红书推荐

📢 **提示**
• 用自然语言描述你的需求即可
• 支持多轮对话澄清
• 执行前会先确认
• 可以选择需要的输出文件
• 中英文都支持

现在就开始对话吧！用 /ask 告诉我你想做什么。
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_read_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Read file content command"""
    user_id = update.effective_user.id

    # Check user authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Get user input from chatbox or command args
    # Priority: full_message (chatbox) > args_input (command)

    user_input = ""
    # Check if user sent a message in chatbox (reply_to_message)
    if update.message and hasattr(update.message, 'reply_to_message'):
        user_input = update.message.text
    elif update.message and hasattr(update.message, 'text'):
        # Regular message in chatbox
        user_input = update.message.text

    # If no chatbox message, use command args
    if not user_input:
        user_input = " ".join(context.args) if context.args else ""

    if not user_input:
        # List available files from state
        state = get_user_state(user_id)
        if not state.generated_files:
            await update.message.reply_text(
                "ℹ️ 你当前没有可读取的文件。\n\n"
                "请先执行一个命令生成文件，然后就可以读取了。"
            )
            return

        # Show file list
        file_list = "\n".join(
            f"{i+1}. {f['name']} ({f['type']}, {f['size_str']})"
            for i, f in enumerate(state.generated_files)
        )

        await update.message.reply_text(
            f"📂 **可读取的文件**\n\n{file_list}\n\n"
            f"💡 使用方法：\n"
            f"`/read 文件编号`\n\n"
            f"例如：`/read 1` 读取第1个文件"
        )

    # User specified a file number
    if user_input.isdigit():
        file_num = int(user_input) - 1  # Convert to 0-based index

        if file_num < 0 or file_num >= len(state.generated_files):
            await update.message.reply_text(f"❌ 无效的文件编号，请选择 1-{len(state.generated_files)} 之间的数字")
            return

        # Read the file
        file_info = state.generated_files[file_num]
        file_path = Path(file_info["path"])

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Limit content for Telegram message (max 4000 chars)
            if len(content) > 4000:
                content = content[:3800] + "\n\n...(内容过长，已截断，完整内容请查看文件)"

            # Determine content type
            file_type = file_info.get("type", "文件")

            await update.message.reply_text(
                f"📄 **{file_type}**\n\n"
                f"**文件名**: {file_info['name']}\n"
                f"**大小**: {file_info['size_str']}\n\n"
                f"---\n\n{content}",
                parse_mode="Markdown"
            )

        except FileNotFoundError:
            await update.message.reply_text(f"❌ 文件不存在: {file_info['name']}")
        except Exception as e:
            await update.message.reply_text(f"❌ 读取文件时出错: {str(e)}")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all generated files"""
    user_id = update.effective_user.id

    # Check user authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Get user state
    state = get_user_state(user_id)

    if not state.generated_files:
        await update.message.reply_text(
            "ℹ️ 你当前没有可查看的文件列表。\n\n"
            "💡 提示：\n"
            "• 请先执行一个命令（如 `/ask 刷小红书推荐`）生成文件\n"
            "• 使用 `/read 文件编号` 来读取和发送文件内容\n"
        )
        return

    # Show all files
    file_list = "\n".join(
        f"{i+1}. {f['name']} ({f['type']}, {f['size_str']})"
        for i, f in enumerate(state.generated_files)
    )

    await update.message.reply_text(
        f"📋 **生成的文件列表**\n\n{file_list}\n\n"
        f"**使用方法**\n"
        f"• `/read 文件编号` - 读取并并发送第N个文件\n"
        f"• `/read 文件名` - 按名称查找文件\n"
        f"• `/read AI分析报告` - 读取最近AI报告\n"
        f"• `/read 继续` - 继续读取下一个文件\n"
        f"• `/read 全部` - 发送所有文件\n"
        f"• `/history` - 查看对话历史\n"
        )

    # Update help text to include /history command
    state.clear()


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process conversational /ask command"""
    user_id = update.effective_user.id

    # Check user authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Get user input
    user_input = " ".join(context.args) if context.args else ""
    if not user_input:
        await update.message.reply_text("❌ 请提供你想做什么\n\n用法: `/ask 你想做什么`")
        return

    state = get_user_state(user_id)

    # Handle different phases
    if state.phase == "file_select":
        # User is selecting files after execution
        selected_indices = await parse_file_selection(user_input, state.generated_files)

        if selected_indices:
            await update.message.reply_text(f"📤 正在发送 {len(selected_indices)} 个文件...")
            await send_selected_files(update, context, selected_indices, state.generated_files)
            state.clear()  # Clear state after file selection
            await update.message.reply_text("✅ 发送完成！可以继续用 /ask 告诉我其他需求")
        else:
            await update.message.reply_text("🤔 我不太明白，请用数字选择，或说'全部'")

        return

    # Main dialogue flow
    # Add user input to history
    state.history.append(user_input)

    await update.message.reply_text(f"🧠 理解中：`{user_input}`", parse_mode="Markdown")

    # Call Gemini
    result = await chat_with_gemini(user_input, state.history)

    if result.get("mode") == "error":
        await update.message.reply_text(f"❌ {result.get('response', '未知错误')}")
        return

    # Dialogue mode - Gemini asking question
    if result.get("mode") == "dialogue":
        response = result.get("response", "")
        await update.message.reply_text(response)
        return

    # Confirm mode - Ready to execute
    if result.get("mode") == "confirm":
        command = result.get("command", "")
        summary = result.get("summary", "")
        args = result.get("args", [])
        url = result.get("url", "")

        # Validate command
        if command not in COMMAND_MAP:
            await update.message.reply_text(f"❌ 命令 `{command}` 不在可用列表中")
            return

        # Save pending command
        state.pending_command = result
        state.phase = "confirm"

        # Build confirmation message with inline keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 确认执行", callback_data=f"confirm_{command}"),
                InlineKeyboardButton("❌ 取消", callback_data=f"cancel_{command}")
            ]
        ])

        await update.message.reply_text(
            f"✅ 我理解你想：\n\n{summary}\n\n确认执行吗？",
            reply_markup=keyboard
        )
        return

    # Unexpected mode
    await update.message.reply_text(f"❌ 未知的响应模式: {result.get('mode')}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    # Check authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await query.edit_message_text("❌ 未授权用户")
        return

    if not query.data:
        return

    data = query.data
    state = get_user_state(user_id)

    if data.startswith("cancel_"):
        # User cancelled
        await query.edit_message_text("❌ 已取消执行")
        state.clear()
        return

    if data.startswith("confirm_"):
        # User confirmed execution
        command = data.split("_", 1)[1]
        pending = state.pending_command

        if not pending or pending.get("command") != command:
            await query.edit_message_text("❌ 确认超时，请重新开始")
            state.clear()
            return

        # Execute command
        cmd = pending["command"]
        args = pending.get("args", [])
        url = pending.get("url", "")

        config = COMMAND_MAP[cmd]
        script = PROJECT_ROOT / config["script"]
        base_args = config["base_args"]
        url_arg_pos = config.get("url_arg_pos")

        # Build final args
        final_args = base_args.copy()
        if url and url_arg_pos is not None:
            final_args.insert(url_arg_pos, url)
        final_args.extend(args)

        await query.edit_message_text(
            f"✅ 确认执行：`/{cmd}`\n"
            f"📥 命令：`python {config['script']} {' '.join(final_args)}`",
            parse_mode="Markdown"
        )

        # Execute
        await query.message.reply_text("⏳ 正在执行...")
        await query.message.reply_text("💡 如需停止，请发送 /stop")

        try:
            # Check if user already has a process running
            existing_process = get_user_process(user_id)
            if existing_process:
                # Try to kill existing process
                try:
                    if hasattr(existing_process, 'kill'):
                        existing_process.kill()
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

            # Create and start process
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script),
                *final_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
                env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}
            )

            # Save process reference so it can be stopped
            set_user_process(user_id, process)
            state.process = process

            # Read output and wait for process to complete
            # communicate() waits for the process and returns (stdout, stderr)
            stdout, stderr = await process.communicate()

            stdout_text = (stdout.decode('utf-8', errors='replace') if stdout else '')
            stderr_text = (stderr.decode('utf-8', errors='replace') if stderr else '')

            # Filter out Playwright/HTML warnings
            # Remove lines like: "21 elements. Proceeding with the first one: <div..."
            import re
            warning_pattern = r'^\d+\s+elements\. Proceeding with the first one:'
            filtered_stderr = '\n'.join(
                line for line in stderr_text.split('\n')
                if not re.search(warning_pattern, line)
                and 'data-v-' not in line  # Also filter HTML with data-v- attributes
                and '<div' not in line  # Filter HTML tags
            )

            raw_output = stdout_text + ('\n' + filtered_stderr if filtered_stderr else '')

            # Clear process reference
            clear_user_process(user_id)
            state.process = None

            if process.returncode == 0:
                # Find generated files
                generated = find_generated_files(PROJECT_ROOT, cmd)

                # Check if there's an AI summary (for scrape commands)
                ai_summary = None
                if generated:
                    for f in generated:
                        if f.get('is_ai_summary'):
                            ai_summary = read_ai_summary(Path(f['path']))
                            # Remove AI summary from the list so it's not included in file selection
                            generated = [g for g in generated if not g.get('is_ai_summary')]
                            break

                if ai_summary:
                    # Send AI summary first
                    await query.message.reply_text(
                        f"📊 **AI分析报告**\n\n{ai_summary}",
                        parse_mode="Markdown"
                    )

                if generated:
                    state.generated_files = generated
                    state.phase = "file_select"

                    file_list = "\n".join(
                        f"{i+1}. {f['name']} ({f['type']}, {f['size_str']})"
                        for i, f in enumerate(generated)
                    )

                    if ai_summary:
                        # If AI summary was shown, just ask about other files
                        await query.message.reply_text(
                            f"✅ 执行完成！\n\n"
                            f"其他生成的文件：\n\n{file_list}\n\n"
                            f"你想要哪些？可以：\n"
                            f"• 全部发送\n"
                            f"• 只要特定类型（如'只要文档'）\n"
                            f"• 指定文件编号\n\n"
                            f"用自然语言回复即可"
                        )
                    else:
                        await query.message.reply_text(
                            f"✅ 执行完成！\n\n"
                            f"我生成了以下文件：\n\n{file_list}\n\n"
                            f"你想要哪些？可以：\n"
                            f"• 全部发送\n"
                            f"• 只要特定类型（如'只要文档'）\n"
                            f"• 指定文件编号\n\n"
                            f"用自然语言回复即可"
                        )
                else:
                    await query.message.reply_text(
                        f"✅ 执行完成！\n\n没有生成新的文件。"
                    )
                    state.clear()

            else:
                # Command failed - ask user if they want to continue
                # Don't show file selection, don't clear state
                # Let Gemini ask the user in next /ask

                error_msg = ""
                if raw_output:
                    error_msg = f"⚠️ 执行未完成。\n\n```\n{raw_output[-1000:]}\n```"
                else:
                    error_msg = "⚠️ 执行未完成，没有输出信息。"

                await query.message.reply_text(
                    f"{error_msg}\n\n"
                    f"💡 如需继续执行，请发送 `/ask 继续`\n"
                    f"我会询问你是否要重新执行命令。"
                )

                # Don't clear state - keep it so user can continue with /ask
                # state.clear()  # REMOVED

        except asyncio.TimeoutError:
            try:
                await query.answer("⏰ 执行超时", timeout=5)
            except Exception:
                pass  # Query might be too old
            try:
                await query.message.reply_text("⏰ 执行超时，请重试")
            except Exception:
                pass
            clear_user_process(user_id)
            state.process = None
            # Don't clear state - let user decide with /ask
            # state.clear()  # REMOVED
        except Exception as e:
            error_msg = f"❌ 执行错误: {str(e)}"
            # Handle query expired errors gracefully
            if "Query is too old" in str(e) or "response timeout" in str(e):
                # Query expired, try to send new message instead
                try:
                    await query.message.reply_text(
                        f"⚠️ 确认按钮已过期，请重新执行命令。\n\n错误详情: {str(e)}"
                    )
                except Exception:
                    # If that also fails, just log
                    print(f"❌ Failed to send error message: {e}")
            else:
                # Normal error, try to send via query.answer
                try:
                    await query.answer(error_msg[:200], timeout=5)
                except Exception:
                    # Query might be too old, try message.reply_text
                    try:
                        await query.message.reply_text(error_msg[:4000])
                    except Exception:
                        pass

            clear_user_process(user_id)
            state.process = None
            state.clear()


# ==================== Main ====================

def main():
    print("\n" + "="*80)
    print("🚀 智能内容处理 Bot 启动中...")
    print("="*80)
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✅ Bot Token: {BOT_TOKEN[:20]}...{BOT_TOKEN[-10:]}")
    print(f"✅ Gemini API Key: {GEMINI_API_KEY[:20]}...{GEMINI_API_KEY[-10:]}")

    if ALLOWED_USERS:
        print(f"🔒 仅限用户: {ALLOWED_USERS}")
    else:
        print("🔓 开放模式：所有用户都可以使用")

    print("\n✅ 新功能：")
    print("  • 多轮对话 - 主动提问澄清需求")
    print("  • 执行前确认 - 避免误操作")
    print("  • 文件选择 - 选择需要的输出")

    # Create application
    builder = Application.builder().token(BOT_TOKEN)
    application = builder.build()

    # Add global error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle all errors globally"""
        print(f"\n❌ [ERROR] {type(context.error).__name__}: {context.error}")

        # Don't respond to polls or callback queries that are too old
        if update and hasattr(update, 'effective_message'):
            try:
                await update.effective_message.reply_text(
                    f"❌ 发生错误: {type(context.error).__name__}\n\n{context.error}",
                    timeout=10
                )
            except Exception as e:
                print(f"❌ Failed to send error message: {e}")

    application.add_error_handler(error_handler)

    # Register commands
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("ask", cmd_ask))
    application.add_handler(CommandHandler("read", cmd_read_file))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("help", cmd_start))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("\n" + "="*80)
    print("✅ Bot 配置完成")
    print("🔄 Bot 正在运行...")
    print("="*80)
    print("\n💡 发送 /start 查看帮助\n")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        if "Conflict" in str(e):
            print(f"\n⚠️ 检测到 Bot 冲突: {e}")
            print("💡 建议:")
            print("  1. 检查是否有其他 Bot 实例正在运行")
            print("  2. 等待几秒后重试")
            print("  3. 使用 BotFather 清除 Webhook")
            raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot 已停止")
    except Exception as e:
        print(f"\n\n❌ Bot 启动失败: {e}")
        import traceback
        traceback.print_exc()
