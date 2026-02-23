#!/usr/bin/env python3
"""
多平台内容分析 Bot（基于video_summary_bot.py扩展）

功能：
- B站视频分析（已有功能）
- 小红书视频和图文分析（新增）
- 自动平台检测

使用方法：
    E:\Anaconda\envs\bilisub\python.exe bot\multi_platform_summary_bot.py
"""

import os
import sys
import re
import json
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 导入 telegram 库
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
except ImportError:
    print("❌ 未安装 python-telegram-bot")
    sys.exit(1)

# ==================== 配置 ====================

CONFIG_PATH = Path(__file__).parent.parent / "config" / "bot_config.json"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
BOT_TOKEN = config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')
PROXY_URL = config.get('proxy_url')

# 设置Gemini API Key
if config.get('gemini_api_key'):
    os.environ['GEMINI_API_KEY'] = config['gemini_api_key']
    print("✅ Gemini API Key 已从配置文件加载")

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    sys.exit(1)

# 启用日志
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# ==================== 链接识别 ====================

class MultiPlatformAnalyzer:
    """多平台链接分析器"""

    def analyze(self, url: str) -> dict:
        """分析链接，返回平台和内容类型"""
        url = url.strip()
        result = {
            'platform': 'unknown',
            'type': 'unknown',
            'id': '',
            'url': url
        }

        # B站检测
        if 'bilibili.com' in url or 'b23.tv' in url:
            result['platform'] = 'bilibili'
            # 提取 BV 号
            match = re.search(r'(BV[\w]+)', url, re.IGNORECASE)
            if match:
                result['type'] = 'video'
                result['id'] = match.group(1)

        # 小红书检测
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            result['platform'] = 'xiaohongshu'
            # 提取笔记ID或用户ID
            if '/user/profile/' in url:
                result['type'] = 'user'
                result['id'] = url.split('/user/profile/')[-1].split('?')[0]
            elif '/explore/' in url:
                result['type'] = 'note'
                result['id'] = url.split('/explore/')[-1].split('?')[0]
            else:
                result['type'] = 'note'

        return result


# ==================== Bot 处理器 ====================

analyzer = MultiPlatformAnalyzer()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    welcome_msg = """👋 你好！我是多平台内容分析 Bot

🎯 支持的平台：
• B站 (bilibili.com) - 视频分析
• 小红书 (xiaohongshu.com) - 视频和图文分析

🚀 使用方法：
• 发送任意链接，自动检测平台并分析
• /help - 查看帮助"""

    await update.message.reply_text(welcome_msg)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_msg = """📖 帮助

📋 支持的链接：
• B站: https://www.bilibili.com/video/BV号
• 小红书: https://www.xiaohongshu.com/...

🔧 命令：
• /start - 开始使用
• /help - 查看帮助

💡 使用方法：
直接发送链接即可自动分析！"""

    await update.message.reply_text(help_msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理消息"""
    text = update.message.text

    if not text:
        return

    # 提取链接
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        await update.message.reply_text("❌ 没有检测到有效的链接")
        return

    url = url_match.group(0)

    # 分析链接
    result = analyzer.analyze(url)

    # 发送给用户处理
    if result['platform'] == 'bilibili' and result['type'] == 'video':
        # B站视频 - 使用现有的B站处理逻辑
        await handle_bilibili_video(update, result)
    elif result['platform'] == 'xiaohongshu':
        # 小红书 - 使用统一分析入口
        await handle_xhs_content(update, result)
    else:
        await update.message.reply_text(
            f"⚠️ 暂不支持的平台或内容类型\n\n"
            f"检测结果: {result['platform']} - {result['type']}"
        )


async def handle_bilibili_video(update: Update, result: dict):
    """处理B站视频"""
    status_msg = await update.message.reply_text(
        f"📺 识别到B站视频\n"
        f"BV号: {result['id']}\n\n"
        f"⏳ 正在分析..."
    )

    try:
        import subprocess
        from pathlib import Path

        # 使用统一分析入口
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "utils" / "unified_content_analyzer.py"),
            '--url', result['url'],
            '--mode', 'subtitle'  # 使用字幕模式分析
        ]

        # 执行分析（异步）
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent.parent,
            encoding='utf-8',
            errors='replace'
        )

        # 等待进程完成
        await process.communicate()

        if process.returncode == 0:
            await status_msg.edit_text(
                f"✅ B站视频分析完成！\n\n"
                f"📁 报告已保存到 output/ 目录"
            )
        else:
            await status_msg.edit_text(
                f"⚠️ 分析过程中出现警告\n\n"
                f"💡 请检查日志文件"
            )

    except FileNotFoundError:
        await status_msg.edit_text(
            f"⚠️ B站分析功能需要额外配置\n\n"
            f"💡 命令行版本:\n"
            f"python utils/unified_content_analyzer.py --url \"{result['url']}\""
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ 处理出错: {str(e)[:200]}")


async def handle_xhs_content(update: Update, result: dict):
    """处理小红书内容"""
    content_type_map = {
        'note': '笔记',
        'user': '用户主页',
        'unknown': '内容'
    }

    type_name = content_type_map.get(result['type'], result['type'])

    status_msg = await update.message.reply_text(
        f"📱 识别到小红书{type_name}\n"
        f"ID: {result['id']}\n\n"
        f"⏳ 正在分析..."
    )

    try:
        import subprocess
        from pathlib import Path

        # 使用统一分析入口
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "utils" / "unified_content_analyzer.py"),
            '--url', result['url']
        ]

        # 执行分析（异步）
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent.parent,
            encoding='utf-8',
            errors='replace'
        )

        # 等待进程完成
        await process.communicate()

        if process.returncode == 0:
            await status_msg.edit_text(
                f"✅ 小红书{type_name}分析完成！\n\n"
                f"📁 报告已保存到 output/ 目录"
            )
        else:
            await status_msg.edit_text(
                f"⚠️ 分析过程中出现警告\n\n"
                f"💡 请检查日志文件"
            )

    except FileNotFoundError:
        await status_msg.edit_text(
            f"⚠️ 小红书分析功能需要额外配置\n\n"
            f"💡 命令行版本:\n"
            f"python utils/unified_content_analyzer.py --url \"{result['url']}\""
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ 处理出错: {str(e)[:200]}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """错误处理"""
    logging.error(f"Error: {context.error}")


# ==================== 主程序 ====================

def main():
    print(f"\n{'='*60}")
    print(f"🤖 多平台内容分析 Bot 启动中...")
    print(f"{'='*60}\n")
    print(f"✅ Bot Token: {BOT_TOKEN[:20]}...{BOT_TOKEN[-10:]}")
    print(f"🎯 支持平台: B站、小红书")

    # 创建应用
    builder = Application.builder().token(BOT_TOKEN)

    # 配置代理（如果设置）
    if PROXY_URL:
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(proxy=PROXY_URL)
        builder = builder.connection_pool_request(request)
        print(f"🌐 使用代理: {PROXY_URL}")

    application = builder.build()

    # 注册处理器
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print(f"✅ Bot 配置完成")
    print(f"\n{'='*60}")
    print(f"🔄 Bot 正在运行...")
    print(f"{'='*60}\n")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot 已停止")
