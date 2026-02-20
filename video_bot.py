#!/usr/bin/env python3
"""
B站/小红书视频处理 Telegram Bot

功能：
- 接收视频链接
- 自动下载、转录、优化、分析
- 任务队列管理
- 进度通知

部署：
1. 本地运行：python video_bot.py
2. 配合ngrok：ngrok http 8443
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
from typing import Dict, Optional, List
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
TASKS_DIR = Path("bot_tasks")
MAX_QUEUE_SIZE = 10
MAX_CONCURRENT_TASKS = 1  # 同时处理的任务数
# =============================================


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(Enum):
    """任务类型"""
    TRANSCRIBE = "transcribe"        # 仅转录
    OPTIMIZE = "optimize"            # 转录 + 优化
    ANALYZE = "analyze"              # 视频分析
    FULL = "full"                    # 完整流程：下载 + 转录 + 优化 + 分析


@dataclass
class Task:
    """任务数据结构"""
    task_id: str
    user_id: int
    user_name: str
    url: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    message_id: Optional[int] = None  # 进度消息ID
    result_file: Optional[str] = None
    error_message: Optional[str] = None
    options: Dict = field(default_factory=dict)


class TaskQueue:
    """任务队列管理"""

    def __init__(self, max_size: int = MAX_QUEUE_SIZE):
        self.queue: deque[Task] = deque()
        self.active_tasks: List[Task] = []
        self.max_size = max_size
        self.task_counter = 0
        self.lock = threading.Lock()

    def add(self, task: Task) -> bool:
        """添加任务到队列"""
        with self.lock:
            if len(self.queue) + len(self.active_tasks) >= self.max_size:
                return False
            self.task_counter += 1
            task.task_id = f"task_{self.task_counter}"
            self.queue.append(task)
            return True

    def get_next(self) -> Optional[Task]:
        """获取下一个待处理任务"""
        with self.lock:
            if not self.queue:
                return None
            return self.queue.popleft()

    def get_position(self, task_id: str) -> int:
        """获取任务在队列中的位置"""
        with self.lock:
            for i, task in enumerate(self.queue):
                if task.task_id == task_id:
                    return i + 1
            return 0

    def get_user_tasks(self, user_id: int) -> List[Task]:
        """获取用户的所有任务"""
        with self.lock:
            return [t for t in list(self.queue) + self.active_tasks if t.user_id == user_id]

    def add_active(self, task: Task):
        """添加到活跃任务"""
        with self.lock:
            self.active_tasks.append(task)

    def remove_active(self, task_id: str):
        """从活跃任务移除"""
        with self.lock:
            self.active_tasks = [t for t in self.active_tasks if t.task_id != task_id]

    def get_stats(self) -> Dict:
        """获取队列统计"""
        with self.lock:
            return {
                "queued": len(self.queue),
                "active": len(self.active_tasks),
                "total_processed": self.task_counter
            }


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
    print("⚠️ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")


class VideoBotConfig:
    """Bot 配置管理"""

    def __init__(self):
        self.bot_token: Optional[str] = None
        self.allowed_users: List[int] = []  # 允许使用的用户ID
        self.proxy_url: Optional[str] = None  # 代理设置
        self.load()

    def load(self):
        """加载配置"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.bot_token = data.get('bot_token')
                self.allowed_users = data.get('allowed_users', [])
                self.proxy_url = data.get('proxy_url')
            except Exception as e:
                print(f"⚠️ 配置加载失败: {e}")

        # 环境变量优先
        if not self.bot_token:
            self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.proxy_url:
            self.proxy_url = os.environ.get('TELEGRAM_PROXY_URL')

        if not self.bot_token:
            raise ValueError(
                "未配置 Bot Token！\n"
                "请创建 config/bot_config.json 或设置 TELEGRAM_BOT_TOKEN 环境变量"
            )

        # 默认允许所有用户（生产环境建议限制）
        if not self.allowed_users:
            self.allowed_users = []  # 空列表 = 允许所有


class VideoProcessor:
    """视频处理器 - 调用现有工具"""

    def __init__(self, task: Task, progress_callback=None):
        self.task = task
        self.progress_callback = progress_callback
        self.output_dir = OUTPUT_DIR / task.task_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _update_progress(self, percent: int, message: str):
        """更新进度"""
        self.task.progress = percent
        if self.progress_callback:
            self.progress_callback(self.task, percent, message)

    def _run_command(self, cmd: List[str], timeout: int = 3600) -> tuple[bool, str]:
        """运行命令并返回结果"""
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

    def detect_platform(self, url: str) -> str:
        """检测平台"""
        if 'bilibili.com' in url or 'b23.tv' in url:
            return 'bilibili'
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            return 'xiaohongshu'
        elif 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'
        return 'unknown'

    def download_video(self) -> tuple[bool, str]:
        """下载视频"""
        self._update_progress(5, "📥 开始下载视频...")

        output_path = self.output_dir / "video.mp4"

        cmd = [
            'yt-dlp',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '-o', str(output_path),
            '--concurrentfragments', '4',
            self.task.url
        ]

        # 添加平台特定的 headers
        if self.detect_platform(self.task.url) == 'bilibili':
            cmd.extend([
                '--headers', 'Referer: https://www.bilibili.com/',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ])

        success, output = self._run_command(cmd, timeout=600)

        if success and output_path.exists():
            self._update_progress(20, "✅ 视频下载完成")
            return True, str(output_path)
        return False, output

    def transcribe(self, video_path: str, model: str = "medium") -> tuple[bool, str]:
        """语音识别"""
        self._update_progress(25, f"🎙️ 开始语音识别 (模型: {model})...")

        cmd = [
            'python', 'ultimate_transcribe.py',
            '-u', self.task.url,
            '-m', model,
            '-f', 'srt,txt',
            '--no-ocr'
        ]

        success, output = self._run_command(cmd, timeout=1800)

        if success:
            # 查找生成的字幕文件
            srt_files = list(Path("output/ultimate").glob("*.srt"))
            if srt_files:
                latest_srt = max(srt_files, key=lambda p: p.stat().st_mtime)
                self._update_progress(60, "✅ 语音识别完成")
                return True, str(latest_srt)

        self._update_progress(60, "⚠️ 语音识别完成（可能有警告）")
        return True, output  # 即使有警告也继续

    def optimize_subtitle(self, srt_path: str, prompt_type: str = "optimization") -> tuple[bool, str]:
        """优化字幕"""
        self._update_progress(65, f"📝 开始优化字幕 (模式: {prompt_type})...")

        cmd = [
            'python', 'optimize_srt_glm.py',
            '-s', srt_path,
            '-p', prompt_type
        ]

        success, output = self._run_command(cmd, timeout=600)

        optimized_files = list(Path("output/optimized_srt").glob("*_optimized.srt"))
        if optimized_files:
            latest_opt = max(optimized_files, key=lambda p: p.stat().st_mtime)
            self._update_progress(80, "✅ 字幕优化完成")
            return True, str(latest_opt)

        return success, output

    def analyze_video(self, video_path: str, mode: str = "knowledge") -> tuple[bool, str]:
        """AI 视频分析"""
        self._update_progress(85, "🤖 开始 AI 视频分析...")

        cmd = [
            'python', 'video_understand_gemini.py',
            '-video', video_path,
            '-m', mode,
            '-o', str(self.output_dir / "analysis")
        ]

        success, output = self._run_command(cmd, timeout=1200)

        # 查找分析结果
        analysis_files = list(self.output_dir.glob("*.md"))
        if analysis_files:
            self._update_progress(95, "✅ 视频分析完成")
            return True, str(analysis_files[0])

        return success, output

    def process(self) -> Dict:
        """执行完整处理流程"""
        result = {
            "success": False,
            "steps": [],
            "files": {},
            "error": None
        }

        try:
            task_type = self.task.task_type

            # 步骤1: 下载视频（如果需要）
            if task_type in [TaskType.TRANSCRIBE, TaskType.OPTIMIZE, TaskType.FULL]:
                success, video_path = self.download_video()
                result["steps"].append({"name": "download", "success": success})
                if success:
                    result["files"]["video"] = video_path

            # 步骤2: 语音识别
            if task_type in [TaskType.TRANSCRIBE, TaskType.OPTIMIZE, TaskType.FULL]:
                model = self.task.options.get('whisper_model', 'medium')
                success, srt_path = self.transcribe(video_path, model)
                result["steps"].append({"name": "transcribe", "success": success})
                if success:
                    result["files"]["srt"] = srt_path

            # 步骤3: 优化字幕
            if task_type in [TaskType.OPTIMIZE, TaskType.FULL]:
                prompt_type = self.task.options.get('prompt_type', 'optimization')
                success, opt_path = self.optimize_subtitle(
                    result["files"].get("srt", ""),
                    prompt_type
                )
                result["steps"].append({"name": "optimize", "success": success})
                if success:
                    result["files"]["optimized"] = opt_path

            # 步骤4: AI 分析
            if task_type in [TaskType.ANALYZE, TaskType.FULL]:
                mode = self.task.options.get('analysis_mode', 'knowledge')
                video_path = result["files"].get("video", "")
                success, analysis_path = self.analyze_video(video_path, mode)
                result["steps"].append({"name": "analyze", "success": success})
                if success:
                    result["files"]["analysis"] = analysis_path

            # 检查是否所有步骤都成功
            failed_steps = [s for s in result["steps"] if not s["success"]]
            result["success"] = len(failed_steps) == 0

            self._update_progress(100, "✅ 处理完成！")

        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

        return result


class VideoBot:
    """视频处理 Telegram Bot"""

    def __init__(self):
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError("请先安装 python-telegram-bot")

        self.config = VideoBotConfig()
        self.queue = TaskQueue()
        self.processor_running = False

        # 创建输出目录
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        TASKS_DIR.mkdir(parents=True, exist_ok=True)

        # 初始化 Telegram Application
        builder = Application.builder().token(self.config.bot_token)

        # 配置代理（如果设置）
        if self.config.proxy_url:
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(proxy=self.config.proxy_url)
            builder = builder.connection_pool_request(request)
            print(f"🌐 使用代理: {self.config.proxy_url}")

        self.application = builder.build()

        # 注册处理器
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("queue", self.cmd_queue))
        self.application.add_handler(CallbackQueryHandler(self.btn_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_url))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        user = update.effective_user

        welcome_msg = f"""👋 你好，{user.first_name}！

我是**视频处理 Bot**，可以帮你：

🎬 **支持平台**
• B站 (bilibili.com)
• 小红书 (xiaohongshu.com)
• YouTube (youtube.com)

🔧 **功能菜单**
• 仅字幕提取 - 快速生成 SRT 字幕
• 字幕+优化 - 提取并 AI 优化字幕
• AI 视频分析 - 智能分析视频内容
• 完整处理 - 全套流程

📝 **使用方法**
1. 发送视频链接
2. 选择处理类型
3. 等待完成并接收结果

💡 发送 /help 查看详细帮助
💡 发送 /queue 查看任务队列
💡 发送 /status 查看系统状态

现在请发送一个视频链接试试吧！"""

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_msg = """📖 **使用帮助**

**支持的视频链接**
• B站: https://www.bilibili.com/video/...
• 小红书: https://www.xiaohongshu.com/...
• YouTube: https://www.youtube.com/watch?v=...

**处理类型说明**

1️⃣ **仅字幕提取**
   • 使用 Whisper 进行语音识别
   • 输出 SRT/TXT 格式字幕
   • 耗时约 3-10 分钟（取决于视频长度）

2️⃣ **字幕 + 优化**
   • 先提取字幕，再用 GLM AI 优化
   • 修正标点、错别字、专业术语
   • 额外耗时约 1-2 分钟

3️⃣ **AI 视频分析**
   • 使用 Gemini 2.5 Flash 分析视频
   • 生成知识库型笔记（核心观点、金句等）
   • 耗时约 1-5 分钟

4️⃣ **完整处理**
   • 下载 + 字幕 + 优化 + 分析
   • 全套服务一步到位

**高级选项**

处理过程中可：
• 发送 /queue 查看队列位置
• 发送 /status 查看系统状态

**注意事项**
• 视频过长会消耗更多时间
• 建议视频大小在 2GB 以内
• 处理完成后会自动发送结果"""

        await update.message.reply_text(help_msg, parse_mode='Markdown')

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """系统状态"""
        stats = self.queue.get_stats()

        status_msg = f"""📊 **系统状态**

🔄 队列统计
• 排队中: {stats['queued']} 个
• 处理中: {stats['active']} 个
• 已处理: {stats['total_processed']} 个

⚙️ 系统配置
• 最大队列: {MAX_QUEUE_SIZE}
• 并发任务: {MAX_CONCURRENT_TASKS}

💾 存储空间
• 输出目录: {OUTPUT_DIR}

🕐 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看队列"""
        user_id = update.effective_user.id
        user_tasks = self.queue.get_user_tasks(user_id)

        if not user_tasks:
            await update.message.reply_text("📭 你没有正在处理的任务")
            return

        msg = "📋 **你的任务列表**\n\n"

        for task in user_tasks:
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.RUNNING: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌"
            }.get(task.status, "❓")

            type_name = {
                TaskType.TRANSCRIBE: "字幕提取",
                TaskType.OPTIMIZE: "字幕+优化",
                TaskType.ANALYZE: "视频分析",
                TaskType.FULL: "完整处理"
            }.get(task.task_type, task.task_type)

            position = self.queue.get_position(task.task_id)
            pos_text = f" (第 {position} 位)" if position > 0 else ""

            msg += f"{status_emoji} `{task.task_id}` - {type_name}{pos_text}\n"
            msg += f"   进度: {task.progress}%\n\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    async def msg_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """接收视频链接"""
        url = update.message.text.strip()

        # 验证是否是有效链接
        if not any(domain in url for domain in ['bilibili.com', 'b23.tv',
                                                   'xiaohongshu.com', 'xhslink.com',
                                                   'youtube.com', 'youtu.be']):
            await update.message.reply_text(
                "⚠️ 不支持的链接格式\n\n"
                "请发送以下平台的视频链接:\n"
                "• B站 (bilibili.com / b23.tv)\n"
                "• 小红书 (xiaohongshu.com)\n"
                "• YouTube (youtube.com)"
            )
            return

        user = update.effective_user

        # 创建任务
        task = Task(
            task_id="",
            user_id=user.id,
            user_name=user.first_name,
            url=url,
            task_type=TaskType.TRANSCRIBE  # 默认，用户会通过按钮选择
        )

        # 添加到队列
        if not self.queue.add(task):
            await update.message.reply_text(
                "⚠️ 队列已满，请稍后再试\n\n"
                f"当前队列: {self.queue.get_stats()['queued']} 个任务"
            )
            return

        # 发送选择菜单
        keyboard = [
            [
                InlineKeyboardButton("🎙️ 仅字幕提取", callback_data=f"type_{task.task_id}_transcribe"),
                InlineKeyboardButton("✍️ 字幕+优化", callback_data=f"type_{task.task_id}_optimize"),
            ],
            [
                InlineKeyboardButton("🤖 AI 视频分析", callback_data=f"type_{task.task_id}_analyze"),
                InlineKeyboardButton("🎯 完整处理", callback_data=f"type_{task.task_id}_full"),
            ],
            [
                InlineKeyboardButton("❌ 取消任务", callback_data=f"cancel_{task.task_id}"),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎬 收到视频链接！\n\n{url[:80]}...\n\n"
            f"任务ID: `{task.task_id}`\n\n"
            "请选择处理类型:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def btn_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """按钮回调处理"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id

        # 解析回调数据
        parts = data.split('_')
        action = parts[0]

        if action == "cancel":
            # 取消任务
            task_id = parts[1]
            # 从队列移除
            for i, task in enumerate(self.queue.queue):
                if task.task_id == task_id and task.user_id == user_id:
                    del self.queue.queue[i]
                    await query.edit_message_text("❌ 任务已取消")
                    return

        elif action == "type":
            # 用户选择了处理类型
            task_id = parts[1]
            task_type_str = parts[2]

            # 找到任务
            task = None
            for t in self.queue.queue:
                if t.task_id == task_id and t.user_id == user_id:
                    task = t
                    break

            if not task:
                await query.edit_message_text("⚠️ 任务不存在或已过期")
                return

            # 设置任务类型
            task_type_map = {
                'transcribe': TaskType.TRANSCRIBE,
                'optimize': TaskType.OPTIMIZE,
                'analyze': TaskType.ANALYZE,
                'full': TaskType.FULL
            }
            task.task_type = task_type_map.get(task_type_str, TaskType.TRANSCRIBE)

            # 保存进度消息ID
            task.message_id = query.message.message_id

            # 启动处理器（如果还没启动）
            if not self.processor_running:
                self.processor_running = True
                asyncio.create_task(self._process_queue())

            # 发送确认消息
            type_name = {
                TaskType.TRANSCRIBE: "仅字幕提取",
                TaskType.OPTIMIZE: "字幕 + 优化",
                TaskType.ANALYZE: "AI 视频分析",
                TaskType.FULL: "完整处理"
            }.get(task.task_type, "")

            position = self.queue.get_position(task_id)

            await query.edit_message_text(
                f"✅ 已选择: **{type_name}**\n\n"
                f"任务ID: `{task_id}`\n"
                f"队列位置: 第 {position} 位\n\n"
                f"⏳ 任务开始后将实时更新进度...",
                parse_mode='Markdown'
            )

    async def _process_queue(self):
        """处理队列中的任务（后台运行）"""
        while True:
            # 获取下一个任务
            task = self.queue.get_next()

            if task is None:
                await asyncio.sleep(2)
                continue

            # 检查并发限制
            if len(self.queue.active_tasks) >= MAX_CONCURRENT_TASKS:
                await asyncio.sleep(2)
                self.queue.queue.appendleft(task)  # 放回队列
                continue

            # 处理任务
            self.queue.add_active(task)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            # 在线程中运行处理（避免阻塞）
            asyncio.create_task(self._process_task(task))

    async def _process_task(self, task: Task):
        """处理单个任务"""
        def progress_callback(t, percent, msg):
            """进度更新回调"""
            if t.message_id:
                # 异步发送进度更新
                asyncio.create_task(self._send_progress_update(t, percent, msg))

        # 在线程池中执行（因为 subprocess 是阻塞的）
        loop = asyncio.get_event_loop()
        processor = VideoProcessor(task, progress_callback)

        # 发送开始消息
        await self._send_message(
            task.user_id,
            f"🔄 开始处理任务 `{task.task_id}`\n"
            f"类型: {task.task_type.value}\n"
            f"链接: {task.url[:60]}..."
        )

        # 在线程中运行处理
        result = await loop.run_in_executor(None, processor.process)

        # 处理完成
        task.completed_at = datetime.now()
        self.queue.remove_active(task.task_id)

        if result["success"]:
            task.status = TaskStatus.COMPLETED
            task.result_file = result.get("files", {})

            # 发送结果
            await self._send_result(task, result)
        else:
            task.status = TaskStatus.FAILED
            task.error_message = result.get("error", "未知错误")

            await self._send_message(
                task.user_id,
                f"❌ 任务 `{task.task_id}` 失败\n\n"
                f"错误: {task.error_message}"
            )

    async def _send_progress_update(self, task: Task, percent: int, message: str):
        """发送进度更新"""
        if task.message_id:
            try:
                # 尝试编辑原消息
                progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)

                await self.application.bot.edit_message_text(
                    chat_id=task.user_id,
                    message_id=task.message_id,
                    text=f"🔄 `{task.task_id}` 处理中...\n\n"
                         f"进度: {percent}%\n"
                         f"[{progress_bar}]\n\n"
                         f"{message}",
                    parse_mode='Markdown'
                )
            except Exception:
                pass  # 消息可能已被删除

    async def _send_result(self, task: Task, result: Dict):
        """发送处理结果"""
        files = result.get("files", {})

        msg = f"""✅ **处理完成！**

任务ID: `{task.task_id}`
类型: {task.task_type.value}
耗时: {(task.completed_at - task.started_at).total_seconds():.1f} 秒

📁 生成的文件:"""

        for name, path in files.items():
            if path and Path(path).exists():
                size = Path(path).stat().st_size / 1024  # KB
                msg += f"\n• {name}: {Path(path).name} ({size:.1f} KB)"

        msg += "\n\n💡 结果文件已保存到服务器"

        # 如果有分析结果，尝试发送预览
        if "analysis" in files and files["analysis"]:
            analysis_path = Path(files["analysis"])
            if analysis_path.exists():
                content = analysis_path.read_text(encoding='utf-8')
                preview = content[:500] + "..." if len(content) > 500 else content
                msg += f"\n\n📝 **分析预览**:\n\n{preview}"

        await self._send_message(task.user_id, msg)

    async def _send_message(self, chat_id: int, text: str):
        """发送消息"""
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"发送消息失败: {e}")

    def run(self):
        """运行 Bot"""
        print("🚀 视频处理 Bot 启动中...")
        print(f"📁 输出目录: {OUTPUT_DIR}")
        print(f"📋 最大队列: {MAX_QUEUE_SIZE}")
        print(f"⚙️  并发任务: {MAX_CONCURRENT_TASKS}")
        print("\n按 Ctrl+C 停止 Bot\n")

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def save_config_example():
    """保存配置示例"""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

    example_config = {
        "bot_token": "YOUR_BOT_TOKEN_HERE",
        "allowed_users": [],  # 空列表允许所有用户，或填入 [123456789, 987654321]
        "_comment": "从 @BotFather 获取 Bot Token"
    }

    example_path = config_dir / "bot_config.example.json"
    with open(example_path, 'w', encoding='utf-8') as f:
        json.dump(example_config, f, indent=2, ensure_ascii=False)

    print(f"✅ 配置示例已创建: {example_path}")
    print("\n请按照以下步骤配置:")
    print("1. 在 Telegram 找到 @BotFather")
    print("2. 发送 /newbot 创建新 bot")
    print("3. 复制获得的 Token")
    print("4. 创建 config/bot_config.json 并填入 Token")


def main():
    """主函数"""
    # 检查依赖
    if not TELEGRAM_AVAILABLE:
        print("❌ 缺少必要依赖")
        save_config_example()
        print("\n请运行: pip install python-telegram-bot")
        return

    # 检查配置
    try:
        VideoBotConfig()
    except ValueError:
        save_config_example()
        return

    # 启动 Bot
    bot = VideoBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n\n👋 Bot 已停止")


if __name__ == "__main__":
    main()
