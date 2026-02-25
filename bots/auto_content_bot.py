#!/usr/bin/env python3
"""
自动内容处理 Bot - 全功能版本

集成 auto_content_workflow.py 的所有功能到 Telegram Bot

功能：
- 视频下载（B站/小红书/YouTube）
- 字幕分析（B站）
- 学习笔记生成（所有平台）
- 评论爬取（B站/小红书）
- 自动处理（智能检测）
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "bot_config.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "bot"
AUTO_CONTENT_SCRIPT = PROJECT_ROOT / "auto_content_workflow.py"


def load_config() -> Dict:
    """加载配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


config = load_config()
BOT_TOKEN = config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = config.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY')

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    print("请在 config/bot_config.json 中配置 bot_token")
    sys.exit(1)


# ==================== 进度管理 ====================

class ProgressTracker:
    """实时进度管理"""

    def __init__(self):
        self.messages = {}  # {user_id: {message_id: text}}

    async def create_progress_message(self, bot, user_id: int,
                              task_type: str,
                              url: str) -> int:
        """创建进度消息，返回 message_id"""
        msg_id = f"{user_id}_{task_type}_{int(datetime.now().timestamp())}"
        self.messages[msg_id] = await bot.send_message(
            user_id,
            f"⏳ 开始处理...\n📋 {task_type}\n🔗 {url[:50]}..."
        )
        return msg_id

    async def update_progress(self, bot, user_id: int,
                         msg_id: int, message: str):
        """更新进度"""
        if msg_id in self.messages:
            try:
                await bot.edit_message_text(msg_id, message)
            except:
                pass

    async def complete_progress(self, bot, user_id: int,
                           msg_id: int, result: Dict):
        """完成进度"""
        status = "✅ 完成" if result['success'] else "❌ 失败"
        await self.update_progress(bot, user_id, msg_id, status)

        if not result['success'] and result['stderr']:
            await bot.send_message(user_id, f"⚠️ 错误信息:\n{result['stderr'][:300]}")


# ==================== 核心调用引擎 ====================

class AutoContentCaller:
    """调用 auto_content_workflow.py 的封装"""

    def __init__(self):
        self.project_root = SCRIPT_DIR

    async def _run_command(self, bot, user_id: int,
                             cmd: list, task_type: str,
                             url: str) -> Optional[Dict]:
        """执行命令并管理进度"""
        # 创建进度消息
        msg_id = await ProgressTracker().create_progress_message(
            bot, user_id, task_type, url
        )

        try:
            # 执行命令（非阻塞，使用 asyncio）
            process = await asyncio.create_subprocess_exec(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                encoding='utf-8',
                cwd=str(self.project_root)
            )

            stdout, stderr = await process.communicate()

            # 格式化结果
            result = {
                'success': process.returncode == 0,
                'stdout': stdout,
                'stderr': stderr
            }

            # 完成进度
            await ProgressTracker().complete_progress(bot, user_id, msg_id, result)

            return result

        except Exception as e:
            error_result = {
                'success': False,
                'stdout': '',
                'stderr': str(e)
            }
            await ProgressTracker().complete_progress(bot, user_id, msg_id, error_result)
            return error_result

    async def download_video(self, bot, user_id: int, url: str, info_only: bool = False):
        """下载视频"""
        cmd = [sys.executable, str(AUTO_CONTENT_SCRIPT), url]
        if info_only:
            cmd.append("--info-only")

        task_type = "视频下载" if not info_only else "获取信息"
        return await self._run_command(bot, user_id, cmd, task_type, url)

    async def extract_subtitle(self, bot, user_id: int, url: str, model: str = 'flash-lite'):
        """提取字幕并分析（仅B站）"""
        cmd = [sys.executable, str(AUTO_CONTENT_SCRIPT),
                 url, "--bili-mode", "subtitle",
                 "--model", model]

        return await self._run_command(bot, user_id, cmd, "字幕分析", url)

    async def generate_notes(self, bot, user_id: int, url: str,
                        keyframes: Optional[int] = None,
                        no_gemini: bool = False,
                        model: str = 'flash-lite'):
        """生成学习笔记"""
        cmd = [sys.executable, str(AUTO_CONTENT_SCRIPT),
                 url, "--generate-notes",
                 "--model", model]

        if keyframes:
            cmd.extend(["--keyframes", str(keyframes)])
        if no_gemini:
            cmd.append("--no-gemini")

        return await self._run_command(bot, user_id, cmd, "学习笔记生成", url)

    async def fetch_comments(self, bot, user_id: int, url: str, count: int = 50):
        """爬取评论"""
        cmd = [sys.executable, str(AUTO_CONTENT_SCRIPT),
                 url, "--fetch-comments", "-c", str(count)]

        return await self._run_command(bot, user_id, cmd, "评论爬取", url)

    async def auto_process(self, bot, user_id: int, url: str,
                        generate_notes: bool = False,
                        fetch_comments: bool = False,
                        comment_count: int = 50):
        """自动处理"""
        cmd = [sys.executable, str(AUTO_CONTENT_SCRIPT), url]

        if generate_notes:
            cmd.append("--generate-notes")
        if fetch_comments:
            cmd.append("--fetch-comments")
            cmd.extend(["-c", str(comment_count)])

        return await self._run_command(bot, user_id, cmd, "自动处理", url)


# ==================== Bot 主程序 ====================

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("❌ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")
    sys.exit(1)


class AutoContentBot:
    """自动内容处理 Bot"""

    def __init__(self):
        self.config = load_config()
        self.caller = AutoContentCaller()
        self.tracker = ProgressTracker()

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        user_id = update.effective_user.id

        welcome_msg = f"""👋 你好！我是**自动内容处理 Bot**

🎯 **支持平台**
• B站 (bilibili.com) - 视频下载/字幕分析/学习笔记/评论爬取
• 小红书 (xiaohongshu.com) - 视频下载/图文分析/评论爬取
• YouTube - 视频下载/学习笔记

🚀 **快速开始**
• 发送任意链接，自动识别平台并处理
• 或使用命令: /download, /subtitle, /notes, /comments

💡 使用方法
• 直接发送链接即可自动处理
• /download <url> - 下载视频
• /subtitle <url> - B站字幕分析
• /notes <url> - 生成学习笔记
• /comments <url> - 爬取评论
• /auto <url> - 智能处理（下载+笔记+评论）
• /help - 查看帮助

🎁  现在发送一个链接试试吧！"""
        await update.message.reply_text(welcome_msg)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_msg = """📖 **使用帮助**

📋 **基础命令**
• /download <url> - 下载视频
  /subtitle <url> - 字幕分析（仅B站）
  /notes <url> - 生成学习笔记
  /comments <url> - 爬取评论
• /auto <url> - 智能处理（下载+笔记+评论）

💡 **参数说明**
• /download --info-only <url> - 只获取信息不下载
• /notes --keyframes N <url> - 指定关键帧数量
• /notes --no-gemini <url> - 禁用AI智能检测
• /comments -c N <url> - 指定评论数量（默认50）
• /comments --generate-notes <url> - 同时生成笔记

🎯 **示例**
/download https://www.bilibili.com/video/BV1xxx
/notes https://www.xiaohongshu.com/explore/xxx --keyframes 12
/comments https://www.bilibili.com/video/BV1xxx -c 100
/auto https://www.bilibili.com/video/BV1xxx --generate-notes --fetch-comments"""
        await update.message.reply_text(help_msg)

    async def cmd_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """下载视频命令"""
        user_id = update.effective_user.id
        args = context.args

        if not args or len(args) == 0:
            await update.message.reply_text("❌ 请提供链接\n用法: /download <url>")
            return

        url = args[0]
        info_only = '--info-only' in args

        await self.caller.download_video(update, user_id, url, info_only)

    async def cmd_subtitle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """字幕分析命令"""
        user_id = update.effective_user.id
        args = context.args

        if not args or len(args) == 0:
            await update.message.reply_text("❌ 请提供链接\n用法: /subtitle <url>")
            return

        url = args[0]
        model = 'flash-lite'
        if '-m' in args:
            model = args[args.index('-m') + 1]

        await self.caller.extract_subtitle(update, user_id, url, model)

    async def cmd_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """学习笔记命令"""
        user_id = update.effective_user.id
        args = context.args

        if not args or len(args) == 0:
            await update.message.reply_text("❌ 请提供链接\n用法: /notes <url>")
            return

        url = args[0]
        keyframes = None
        no_gemini = False
        model = 'flash-lite'

        # 解析参数
        i = 1
        while i < len(args):
            arg = args[i]
            if arg.startswith('--keyframes'):
                keyframes = int(args[i])
            elif arg == '--no-gemini':
                no_gemini = True
            elif arg.startswith('-m'):
                model = args[i]
            i += 1

        await self.caller.generate_notes(update, user_id, url, keyframes, no_gemini, model)

    async def cmd_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """评论爬取命令"""
        user_id = update.effective_user.id
        args = context.args

        if not args or len(args) == 0:
            await update.message.reply_text("❌ 请提供链接\n用法: /comments <url>")
            return

        url = args[0]
        count = 50

        i = 1
        while i < len(args):
            if args[i].startswith('-c'):
                count = int(args[i])
            i += 1

        await self.caller.fetch_comments(update, user_id, url, count)

    async def cmd_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """自动处理命令"""
        user_id = update.effective_user.id
        args = context.args

        if not args or len(args) == 0:
            await update.message.reply_text("❌ 请提供链接\n用法: /auto <url>")
            return

        url = args[0]
        generate_notes = '--generate-notes' in args
        fetch_comments = '--fetch-comments' in args
        comment_count = 50

        i = 1
        while i < len(args):
            if args[i].startswith('-c'):
                comment_count = int(args[i])
            i += 1

        await self.caller.auto_process(update, user_id, url, generate_notes, fetch_comments, comment_count)

    async def msg_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息（自动识别链接）"""
        user_id = update.effective_user.id
        text = update.message.text.strip()

        # 检测是否是URL
        import re
        url_match = re.search(r'https?://[^\s]+', text)
        if not url_match:
            await update.message.reply_text("💡 请发送有效的链接\n\n示例:\nhttps://www.bilibili.com/video/BV1xxx")
            return

        url = url_match.group(0)

        # 自动处理
        await update.message.reply_text("🔍 检测到链接，正在自动处理...")
        result = await self.caller.auto_process(update, user_id, url, generate_notes=False, fetch_comments=False)

        if result['success']:
            status_msg = "✅ 自动处理完成"
        else:
            status_msg = f"❌ 处理失败\n{result['stderr'][:300] if result['stderr'] else ''}"
            await update.message.reply_text(status_msg)


def main():
    """主程序"""
    print("🚀 自动内容处理 Bot 启动中...")
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✅ Bot Token: {BOT_TOKEN[:20]}...{BOT_TOKEN[-10:]}")
    print(f"✅ Gemini API Key: {GEMINI_API_KEY[:20] if GEMINI_API_KEY else '未配置'}")

    # 创建应用
    builder = Application.builder().token(BOT_TOKEN)

    # 注册命令
    bot = AutoContentBot()
    bot.application = builder.build()

    bot.application.add_handler(CommandHandler("start", bot.cmd_start))
    bot.application.add_handler(CommandHandler("help", bot.cmd_help))
    bot.application.add_handler(CommandHandler("download", bot.cmd_download))
    bot.application.add_handler(CommandHandler("subtitle", bot.cmd_subtitle))
    bot.application.add_handler(CommandHandler("notes", bot.cmd_notes))
    bot.application.add_handler(CommandHandler("comments", bot.cmd_comments))
    bot.application.add_handler(CommandHandler("auto", bot.cmd_auto))
    bot.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.msg_text))

    print("✅ Bot 配置完成")
    print("📝 支持的功能:")
    print("  • 视频下载（所有平台）")
    print("  • 字幕分析（B站）")
    print("  • 学习笔记生成（所有平台）")
    print("  • 评论爬取（B站/小红书）")
    print("  • 自动智能处理")
    print("\n🔄 Bot 正在运行...")

    try:
        bot.application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
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
