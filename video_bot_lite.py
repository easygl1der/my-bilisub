#!/usr/bin/env python3
"""
轻量版视频分析 Bot - 用于 Railway 部署

只保留 AI 视频分析功能，去除重型依赖（Whisper/PyTorch）
镜像大小 < 500MB
"""

import os
import sys
import json
import time
import asyncio
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================
CONFIG_PATH = Path("config/bot_config.json")
OUTPUT_DIR = Path("output/bot")
MAX_QUEUE_SIZE = 5
MAX_CONCURRENT_TASKS = 1
# =============================================

# 尝试导入 telegram 库
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        filters,
        ContextTypes
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisMode(Enum):
    KNOWLEDGE = "knowledge"      # 知识型笔记
    SUMMARY = "summary"          # 内容总结
    HIGHLIGHTS = "highlights"    # 金句提取


@dataclass
class Task:
    task_id: str
    user_id: int
    user_name: str
    url: str
    mode: AnalysisMode = AnalysisMode.KNOWLEDGE
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    message_id: Optional[int] = None
    error_message: Optional[str] = None


class TaskQueue:
    def __init__(self, max_size: int = MAX_QUEUE_SIZE):
        self.queue: deque[Task] = deque()
        self.active_tasks: List[Task] = []
        self.max_size = max_size
        self.task_counter = 0
        self.lock = threading.Lock()

    def add(self, task: Task) -> bool:
        with self.lock:
            if len(self.queue) + len(self.active_tasks) >= self.max_size:
                return False
            self.task_counter += 1
            task.task_id = f"task_{self.task_counter}"
            self.queue.append(task)
            return True

    def get_next(self) -> Optional[Task]:
        with self.lock:
            if not self.queue:
                return None
            return self.queue.popleft()

    def get_position(self, task_id: str) -> int:
        with self.lock:
            for i, task in enumerate(self.queue):
                if task.task_id == task_id:
                    return i + 1
            return 0

    def add_active(self, task: Task):
        with self.lock:
            self.active_tasks.append(task)

    def remove_active(self, task_id: str):
        with self.lock:
            self.active_tasks = [t for t in self.active_tasks if t.task_id != task_id]

    def get_stats(self) -> Dict:
        with self.lock:
            return {
                "queued": len(self.queue),
                "active": len(self.active_tasks),
                "total_processed": self.task_counter
            }


from typing import Dict


class VideoBotConfig:
    def __init__(self):
        self.bot_token: Optional[str] = None
        self.allowed_users: List[int] = []
        self.proxy_url: Optional[str] = None
        self.gemini_api_key: Optional[str] = None
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.bot_token = data.get('bot_token')
                self.allowed_users = data.get('allowed_users', [])
                self.proxy_url = data.get('proxy_url')
                self.gemini_api_key = data.get('gemini_api_key')
            except Exception as e:
                print(f"⚠️ 配置加载失败: {e}")

        if not self.bot_token:
            self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.proxy_url:
            self.proxy_url = os.environ.get('TELEGRAM_PROXY_URL')
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get('GEMINI_API_KEY')

        if not self.bot_token:
            raise ValueError("未配置 Bot Token！")

        if not self.gemini_api_key:
            print("⚠️ 未配置 Gemini API Key，视频分析可能失败")


class VideoProcessor:
    """轻量级视频处理器 - 只做 AI 分析"""

    def __init__(self, task: Task, progress_callback=None, api_key: str = None):
        self.task = task
        self.progress_callback = progress_callback
        self.api_key = api_key
        self.output_dir = OUTPUT_DIR / task.task_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _update_progress(self, percent: int, message: str):
        self.task.progress = percent
        if self.progress_callback:
            self.progress_callback(self.task, percent, message)

    def _run_command(self, cmd: List[str], timeout: int = 3600) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=timeout,
                cwd=Path(__file__).parent
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def download_video(self) -> tuple[bool, str]:
        """下载视频"""
        self._update_progress(10, "📥 开始下载视频...")

        output_path = self.output_dir / "video.mp4"

        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]/best',
            '-o', str(output_path),
            '--concurrentfragments', '4',
            '--max-filesize', '500M',  # 限制 500MB
            self.task.url
        ]

        success, output = self._run_command(cmd, timeout=600)

        if success and output_path.exists():
            self._update_progress(40, "✅ 视频下载完成")
            return True, str(output_path)
        return False, output

    def analyze_video(self, video_path: str) -> tuple[bool, str]:
        """AI 视频分析"""
        self._update_progress(50, "🤖 开始 AI 视频分析...")

        # 直接调用 Gemini API
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')

            # 上传视频文件
            self._update_progress(60, "📤 上传视频到 AI...")
            video_file = genai.upload_file(path=video_path)

            # 等待视频处理完成
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file.refresh()

            # 根据模式生成 prompt
            prompts = {
                AnalysisMode.KNOWLEDGE: """请分析这个视频，生成知识型笔记：

1. **核心观点**（3-5个要点）
2. **关键概念**（专业术语解释）
3. **金句摘录**（最有价值的句子）
4. **思维导图**（内容结构）
5. **可行动建议**（具体怎么做）

请用 Markdown 格式输出，清晰易读。""",

                AnalysisMode.SUMMARY: """请总结这个视频的内容：

1. **主要内容**（简述）
2. **关键信息**（3-5个要点）
3. **结论/启示**

请用 Markdown 格式输出，简洁明了。""",

                AnalysisMode.HIGHLIGHTS: """请从这个视频中提取金句和亮点：

1. **金句**（有深度的句子）
2. **精彩片段**（印象深刻的部分）
3. **值得引用的话**

请用 Markdown 格式输出。"""
            }

            prompt = prompts.get(self.task.mode, prompts[AnalysisMode.KNOWLEDGE])

            self._update_progress(80, "🧠 AI 正在分析...")

            response = model.generate_content([video_file, prompt])
            result_text = response.text

            # 保存结果
            output_file = self.output_dir / "analysis.md"
            output_file.write_text(result_text, encoding='utf-8')

            self._update_progress(100, "✅ 分析完成！")
            return True, str(output_file)

        except Exception as e:
            return False, str(e)

    def process(self) -> Dict:
        """执行处理流程"""
        result = {
            "success": False,
            "error": None,
            "files": {}
        }

        try:
            # 下载视频
            success, video_path = self.download_video()
            if not success:
                result["error"] = f"下载失败: {video_path}"
                return result

            result["files"]["video"] = video_path

            # AI 分析
            success, analysis_path = self.analyze_video(video_path)
            if success:
                result["files"]["analysis"] = analysis_path
                result["success"] = True
            else:
                result["error"] = f"分析失败: {analysis_path}"

        except Exception as e:
            result["error"] = str(e)

        return result


class VideoBotLite:
    """轻量级视频分析 Bot"""

    def __init__(self):
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError("请先安装 python-telegram-bot")

        self.config = VideoBotConfig()
        self.queue = TaskQueue()
        self.processor_running = False

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        builder = Application.builder().token(self.config.bot_token)

        if self.config.proxy_url:
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(proxy=self.config.proxy_url)
            builder = builder.connection_pool_request(request)
            print(f"🌐 使用代理: {self.config.proxy_url}")

        self.application = builder.build()

        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CallbackQueryHandler(self.btn_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_url))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user

        welcome_msg = f"""👋 你好，{user.first_name}！

我是**视频分析 Bot**，使用 AI 分析视频内容。

🎬 **支持平台**
• B站 (bilibili.com)
• 小红书 (xiaohongshu.com)
• YouTube (youtube.com)

🤖 **分析模式**
• 知识型笔记 - 核心观点、概念、金句
• 内容总结 - 简洁摘要
• 金句提取 - 精彩句子

📝 **使用方法**
1. 发送视频链接
2. 选择分析模式
3. 等待 AI 分析完成

💡 发送 /help 查看详细帮助

现在请发送一个视频链接！"""

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_msg = """📖 **使用帮助**

**支持的视频链接**
• B站: https://www.bilibili.com/video/...
• 小红书: https://www.xiaohongshu.com/...
• YouTube: https://www.youtube.com/watch?v=...

**分析模式说明**

1️⃣ **知识型笔记**
   • 核心观点（3-5个）
   • 关键概念解释
   • 金句摘录
   • 思维导图
   • 可行动建议

2️⃣ **内容总结**
   • 简洁的内容概述
   • 关键信息提取
   • 结论启示

3️⃣ **金句提取**
   • 有深度的句子
   • 精彩片段
   • 值得引用的话

**注意事项**
• 视频大小建议 < 500MB
• 分析耗时约 1-5 分钟
• 使用 Gemini 2.0 Flash AI"""

        await update.message.reply_text(help_msg, parse_mode='Markdown')

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.queue.get_stats()

        status_msg = f"""📊 **系统状态**

🔄 队列: {stats['queued']} 排队 / {stats['active']} 处理中
✅ 已处理: {stats['total_processed']} 个

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def btn_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id

        if data.startswith("mode_"):
            # 用户选择了分析模式
            parts = data.split('_')
            task_id = parts[1]
            mode_str = parts[2]

            # 找到任务
            task = None
            for t in self.queue.queue:
                if t.task_id == task_id and t.user_id == user_id:
                    task = t
                    break

            if not task:
                await query.edit_message_text("⚠️ 任务不存在")
                return

            # 设置模式
            mode_map = {
                'knowledge': AnalysisMode.KNOWLEDGE,
                'summary': AnalysisMode.SUMMARY,
                'highlights': AnalysisMode.HIGHLIGHTS
            }
            task.mode = mode_map.get(mode_str, AnalysisMode.KNOWLEDGE)
            task.message_id = query.message.message_id

            if not self.processor_running:
                self.processor_running = True
                asyncio.create_task(self._process_queue())

            mode_name = {
                AnalysisMode.KNOWLEDGE: "知识型笔记",
                AnalysisMode.SUMMARY: "内容总结",
                AnalysisMode.HIGHLIGHTS: "金句提取"
            }.get(task.mode, "")

            await query.edit_message_text(
                f"✅ 已选择: **{mode_name}**\n\n"
                f"任务ID: `{task_id}`\n"
                f"⏳ 开始处理...",
                parse_mode='Markdown'
            )

    async def msg_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()

        if not any(domain in url for domain in ['bilibili.com', 'b23.tv',
                                                   'xiaohongshu.com', 'xhslink.com',
                                                   'youtube.com', 'youtu.be']):
            await update.message.reply_text(
                "⚠️ 不支持的链接\n\n"
                "请发送: B站/小红书/YouTube 视频链接"
            )
            return

        user = update.effective_user
        task = Task(
            task_id="",
            user_id=user.id,
            user_name=user.first_name,
            url=url
        )

        if not self.queue.add(task):
            await update.message.reply_text(
                f"⚠️ 队列已满 ({self.queue.get_stats()['queued']}/{MAX_QUEUE_SIZE})"
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("📚 知识型笔记", callback_data=f"mode_{task.task_id}_knowledge"),
                InlineKeyboardButton("📝 内容总结", callback_data=f"mode_{task.task_id}_summary"),
            ],
            [
                InlineKeyboardButton("💎 金句提取", callback_data=f"mode_{task.task_id}_highlights"),
                InlineKeyboardButton("❌ 取消", callback_data=f"cancel_{task.task_id}"),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎬 收到视频！\n\n{url[:80]}...\n\n"
            f"请选择分析模式:",
            reply_markup=reply_markup
        )

    async def _process_queue(self):
        while True:
            task = self.queue.get_next()
            if task is None:
                await asyncio.sleep(2)
                continue

            if len(self.queue.active_tasks) >= MAX_CONCURRENT_TASKS:
                await asyncio.sleep(2)
                self.queue.queue.appendleft(task)
                continue

            self.queue.add_active(task)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            asyncio.create_task(self._process_task(task))

    async def _process_task(self, task: Task):
        def progress_callback(t, percent, msg):
            if t.message_id:
                asyncio.create_task(self._send_progress(t, percent, msg))

        loop = asyncio.get_event_loop()
        processor = VideoProcessor(task, progress_callback, self.config.gemini_api_key)

        await self._send_message(
            task.user_id,
            f"🔄 开始分析 `{task.task_id}`\n{task.url[:60]}..."
        )

        result = await loop.run_in_executor(None, processor.process)

        task.completed_at = datetime.now()
        self.queue.remove_active(task.task_id)

        if result["success"]:
            task.status = TaskStatus.COMPLETED
            await self._send_result(task, result)
        else:
            task.status = TaskStatus.FAILED
            await self._send_message(
                task.user_id,
                f"❌ 任务失败\n\n错误: {result.get('error', '未知错误')}"
            )

    async def _send_progress(self, task: Task, percent: int, message: str):
        if task.message_id:
            try:
                progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
                await self.application.bot.edit_message_text(
                    chat_id=task.user_id,
                    message_id=task.message_id,
                    text=f"🔄 `{task.task_id}`\n\n进度: {percent}%\n[{progress_bar}]\n\n{message}",
                    parse_mode='Markdown'
                )
            except Exception:
                pass

    async def _send_result(self, task: Task, result: Dict):
        files = result.get("files", {})
        analysis_path = files.get("analysis")

        content = ""
        if analysis_path and Path(analysis_path).exists():
            content = Path(analysis_path).read_text(encoding='utf-8')

        msg = f"""✅ **分析完成！**

耗时: {(task.completed_at - task.started_at).total_seconds():.1f} 秒

---

{content[:2000]}"""

        if len(content) > 2000:
            msg += f"\n\n...（内容过长，已截断）"

        await self._send_message(task.user_id, msg)

    async def _send_message(self, chat_id: int, text: str):
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"发送失败: {e}")

    def run(self):
        print("🚀 视频分析 Bot 启动...")
        print(f"📁 输出: {OUTPUT_DIR}")
        print("\n按 Ctrl+C 停止\n")
        self.application.run_polling()


def main():
    if not TELEGRAM_AVAILABLE:
        print("❌ 缺少依赖")
        print("pip install python-telegram-bot google-generativeai")
        return

    try:
        bot = VideoBotLite()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot 已停止")


if __name__ == "__main__":
    main()
