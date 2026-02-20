#!/usr/bin/env python3
"""
轻量版视频分析 Bot - 简化版
只保留 AI 视频分析功能
"""

import os
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
import threading

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================
CONFIG_PATH = Path("config/bot_config.json")
OUTPUT_DIR = Path("output/bot")
# =============================================

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
except ImportError:
    print("请安装: pip install python-telegram-bot")
    sys.exit(1)


class AnalysisMode(Enum):
    KNOWLEDGE = "knowledge"
    SUMMARY = "summary"
    HIGHLIGHTS = "highlights"


@dataclass
class Task:
    task_id: str
    user_id: int
    url: str
    mode: Optional[AnalysisMode] = None
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    message_id: Optional[int] = None


# 全局任务存储
tasks: dict[str, Task] = {}
task_counter = 0
task_lock = threading.Lock()


class VideoBotConfig:
    def __init__(self):
        self.bot_token = None
        self.gemini_api_key = None
        self.load()

    def load(self):
        # 从配置文件读取
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.bot_token = data.get('bot_token')
                self.gemini_api_key = data.get('gemini_api_key')
            except:
                pass

        # 环境变量优先
        if not self.bot_token:
            self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get('GEMINI_API_KEY')

        if not self.bot_token:
            raise ValueError("未配置 Bot Token")

        if not self.gemini_api_key:
            print("⚠️ 未配置 Gemini API Key")


class VideoProcessor:
    def __init__(self, task: Task, api_key: str, progress_callback=None):
        self.task = task
        self.api_key = api_key
        self.progress_callback = progress_callback
        self.output_dir = OUTPUT_DIR / task.task_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _update_progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)

    def download_video(self) -> tuple[bool, str]:
        self._update_progress(10, "📥 下载视频中...")

        output_path = self.output_dir / "video.mp4"

        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]/best',
            '-o', str(output_path),
            '--concurrentfragments', '4',
            '--max-filesize', '500M',
            self.task.url
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600,
                cwd=Path(__file__).parent
            )

            if output_path.exists():
                self._update_progress(40, "✅ 下载完成")
                return True, str(output_path)
            return False, result.stderr
        except Exception as e:
            return False, str(e)

    def analyze_video(self, video_path: str) -> tuple[bool, str]:
        self._update_progress(50, "🤖 AI 分析中...")

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')

            # 上传视频
            self._update_progress(60, "📤 上传到 AI...")
            video_file = genai.upload_file(path=video_path)

            # 等待处理
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file.refresh()

            # Prompt
            prompts = {
                AnalysisMode.KNOWLEDGE: """分析这个视频，生成知识型笔记：

1. **核心观点**（3-5个要点）
2. **关键概念**（专业术语解释）
3. **金句摘录**
4. **思维导图**（内容结构）
5. **可行动建议**

用 Markdown 输出。""",

                AnalysisMode.SUMMARY: """总结这个视频：

1. **主要内容**
2. **关键信息**（3-5个要点）
3. **结论/启示**

用 Markdown 输出。""",

                AnalysisMode.HIGHLIGHTS: """提取金句和亮点：

1. **金句**（有深度的句子）
2. **精彩片段**
3. **值得引用的话**

用 Markdown 输出。"""
            }

            prompt = prompts.get(self.task.mode, prompts[AnalysisMode.KNOWLEDGE])

            self._update_progress(80, "🧠 AI 思考中...")

            response = model.generate_content([video_file, prompt])

            # 保存结果
            output_file = self.output_dir / "analysis.md"
            output_file.write_text(response.text, encoding='utf-8')

            self._update_progress(100, "✅ 分析完成！")
            return True, str(output_file)

        except Exception as e:
            return False, str(e)

    def process(self) -> dict:
        result = {"success": False, "error": None, "files": {}}

        # 下载
        success, video_path = self.download_video()
        if not success:
            result["error"] = f"下载失败: {video_path}"
            return result
        result["files"]["video"] = video_path

        # 分析
        success, analysis_path = self.analyze_video(video_path)
        if success:
            result["files"]["analysis"] = analysis_path
            result["success"] = True
        else:
            result["error"] = f"分析失败: {analysis_path}"

        return result


class VideoBotLite:
    def __init__(self):
        self.config = VideoBotConfig()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 创建 Application
        self.application = Application.builder().token(self.config.bot_token).build()

        # 注册处理器
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CallbackQueryHandler(self.btn_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_url))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        msg = f"""👋 你好，{user.first_name}！

我是**视频分析 Bot**，用 AI 分析视频。

🎬 支持平台：B站、小红书、YouTube

📝 使用方法：
1. 发送视频链接
2. 选择分析模式
3. 等待 AI 分析完成

💡 发送 /help 查看详细帮助"""
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """📖 **使用帮助**

**支持链接**
• B站: bilibili.com / b23.tv
• 小红书: xiaohongshu.com
• YouTube: youtube.com

**分析模式**
📚 知识型笔记 - 核心观点、概念、金句
📝 内容总结 - 简洁摘要
💎 金句提取 - 精彩句子

**注意**
• 视频 < 500MB
• 分析耗时 1-5 分钟"""
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        with task_lock:
            user_tasks = [t for t in tasks.values() if t.user_id == user_id]

        if not user_tasks:
            await update.message.reply_text("📭 没有任务")
            return

        msg = "📋 **你的任务**\n\n"
        for t in user_tasks[:5]:
            status_emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌"}.get(t.status, "❓")
            mode_name = {AnalysisMode.KNOWLEDGE: "知识笔记", AnalysisMode.SUMMARY: "总结", AnalysisMode.HIGHLIGHTS: "金句"}.get(t.mode, "未知")
            msg += f"{status_emoji} `{t.task_id}` - {mode_name}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    async def btn_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id

        # 处理模式选择
        if data.startswith("mode_"):
            parts = data.split('_')
            task_id = parts[1]
            mode_str = parts[2]

            with task_lock:
                task = tasks.get(task_id)
                if not task or task.user_id != user_id:
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

            mode_name = {"knowledge": "知识型笔记", "summary": "内容总结", "highlights": "金句提取"}[mode_str]

            await query.edit_message_text(
                f"✅ 已选择: **{mode_name}**\n\n⏳ 开始处理...",
                parse_mode='Markdown'
            )

            # 开始处理
            asyncio.create_task(self.process_task(task))

        # 处理取消
        elif data.startswith("cancel_"):
            task_id = data.split('_')[1]
            with task_lock:
                if task_id in tasks and tasks[task_id].user_id == user_id:
                    del tasks[task_id]
                    await query.edit_message_text("❌ 任务已取消")
                    return
            await query.edit_message_text("⚠️ 任务不存在")

    async def msg_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()

        if not any(d in url for d in ['bilibili.com', 'b23.tv', 'xiaohongshu.com', 'youtube.com']):
            await update.message.reply_text("⚠️ 不支持的链接\n\n请发送: B站/小红书/YouTube 视频")
            return

        user = update.effective_user

        # 创建任务
        global task_counter
        with task_lock:
            task_counter += 1
            task_id = f"task_{task_counter}"
            task = Task(task_id=task_id, user_id=user.id, url=url)
            tasks[task_id] = task

        # 发送选择菜单
        keyboard = [
            [
                InlineKeyboardButton("📚 知识型笔记", callback_data=f"mode_{task_id}_knowledge"),
                InlineKeyboardButton("📝 内容总结", callback_data=f"mode_{task_id}_summary"),
            ],
            [
                InlineKeyboardButton("💎 金句提取", callback_data=f"mode_{task_id}_highlights"),
                InlineKeyboardButton("❌ 取消", callback_data=f"cancel_{task_id}"),
            ]
        ]

        await update.message.reply_text(
            f"🎬 收到视频！\n\n{url[:80]}...\n\n请选择分析模式:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def process_task(self, task: Task):
        def progress_cb(percent, msg):
            if task.message_id:
                asyncio.create_task(self._update_progress(task, percent, msg))

        # 发送开始通知
        await self.application.bot.send_message(
            chat_id=task.user_id,
            text=f"🔄 开始分析 `{task.task_id}`",
            parse_mode='Markdown'
        )

        # 处理
        processor = VideoProcessor(task, self.config.gemini_api_key, progress_cb)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, processor.process)

        # 更新状态
        with task_lock:
            task.status = "completed" if result["success"] else "failed"

        # 发送结果
        if result["success"]:
            analysis_path = result["files"].get("analysis")
            if analysis_path and Path(analysis_path).exists():
                content = Path(analysis_path).read_text(encoding='utf-8')
                preview = content[:1500] + "..." if len(content) > 1500 else content

                await self.application.bot.send_message(
                    chat_id=task.user_id,
                    text=f"✅ **分析完成！**\n\n{preview}",
                    parse_mode='Markdown'
                )
            else:
                await self.application.bot.send_message(
                    chat_id=task.user_id,
                    text="✅ 分析完成，但结果文件未找到"
                )
        else:
            await self.application.bot.send_message(
                chat_id=task.user_id,
                text=f"❌ 任务失败\n\n{result.get('error', '未知错误')}"
            )

    async def _update_progress(self, task: Task, percent: int, message: str):
        try:
            if task.message_id:
                progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
                await self.application.bot.edit_message_text(
                    chat_id=task.user_id,
                    message_id=task.message_id,
                    text=f"🔄 `{task.task_id}`\n\n进度: {percent}%\n[{progress_bar}]\n\n{message}",
                    parse_mode='Markdown'
                )
        except:
            pass

    def run(self):
        print("🚀 视频分析 Bot 启动...")
        print(f"📁 输出: {OUTPUT_DIR}")
        print("\n按 Ctrl+C 停止\n")
        self.application.run_polling()


def main():
    try:
        bot = VideoBotLite()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot 已停止")


if __name__ == "__main__":
    main()
