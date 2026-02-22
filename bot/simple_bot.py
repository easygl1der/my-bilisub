#!/usr/bin/env python3
"""
简单的 Telegram Bot - 链接识别功能

使用方法：
1. 设置 config/telegram_config.json 中的 bot_token
2. 运行: python bot/simple_bot.py
3. 在 Telegram 中发送链接给 Bot
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

# 尝试导入 telegram 库
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("❌ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")
    sys.exit(1)

# ==================== 配置 ====================

CONFIG_PATH = Path(__file__).parent.parent / "config" / "telegram_config.json"

def load_config():
    """加载配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
BOT_TOKEN = config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    print(f"请在 {CONFIG_PATH} 中配置 bot_token")
    sys.exit(1)

# 启用日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==================== 链接识别器 ====================

class LinkAnalyzer:
    """链接分析器"""

    def __init__(self):
        self.patterns = {
            'bilibili': {
                'video': r'bilibili\.com/video/(BV[\w]+|av[\d]+)',
                'user': r'bilibili\.com/(space/|u/)?(\d+)',
                'user2': r'space\.bilibili\.com/(\d+)',
            },
            'xiaohongshu': {
                'note': r'xiaohongshu\.com/explore/([a-f0-9]+)',
                'user': r'xiaohongshu\.com/user/profile/([a-f0-9]+)',
            },
            'youtube': {
                'video': r'(youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
                'channel': r'youtube\.com/(channel/[\w-]+|c/[\w-]+|user/[\w-]+|@[\w-]+)',
            }
        }

    def analyze(self, url: str) -> dict:
        """分析链接，返回平台和类型"""
        url = url.strip()
        result = {
            'platform': 'unknown',
            'type': 'unknown',
            'id': '',
            'original_url': url
        }

        # B站
        if 'bilibili.com' in url or 'b23.tv' in url:
            result['platform'] = 'bilibili'
            video_match = re.search(self.patterns['bilibili']['video'], url)
            if video_match:
                result['type'] = 'video'
                result['id'] = video_match.group(1)
            else:
                user_match = re.search(self.patterns['bilibili']['user2'], url)
                if not user_match:
                    user_match = re.search(self.patterns['bilibili']['user'], url)
                if user_match:
                    result['type'] = 'user'
                    result['id'] = user_match.group(1)

        # 小红书
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            result['platform'] = 'xiaohongshu'
            note_match = re.search(self.patterns['xiaohongshu']['note'], url)
            if note_match:
                result['type'] = 'note'
                result['id'] = note_match.group(1)
            else:
                user_match = re.search(self.patterns['xiaohongshu']['user'], url)
                if user_match:
                    result['type'] = 'user'
                    result['id'] = user_match.group(1)

        # YouTube
        elif 'youtube.com' in url or 'youtu.be' in url:
            result['platform'] = 'youtube'
            video_match = re.search(self.patterns['youtube']['video'], url)
            if video_match:
                result['type'] = 'video'
                result['id'] = video_match.group(2)
            else:
                channel_match = re.search(self.patterns['youtube']['channel'], url)
                if channel_match:
                    result['type'] = 'channel'
                    result['id'] = channel_match.group(0)

        return result

    def format_result(self, result: dict) -> str:
        """格式化分析结果为 Telegram 消息"""
        platform_emoji = {
            'bilibili': '📺',
            'xiaohongshu': '📕',
            'youtube': '▶️',
            'unknown': '❓'
        }

        type_text = {
            'video': '视频链接',
            'note': '笔记链接',
            'user': '用户主页',
            'channel': '频道主页',
            'unknown': '未知类型'
        }

        emoji = platform_emoji.get(result['platform'], '❓')
        type_name = type_text.get(result['type'], '未知类型')

        lines = [
            f"{emoji} 识别结果",
            f"",
            f"平台: {result['platform'].upper()}",
            f"类型: {type_name}",
        ]

        if result['id']:
            lines.append(f"ID: {result['id']}")

        lines.append(f"")
        lines.append(f"链接: {result['original_url']}")

        return "\n".join(lines)


# ==================== Bot 处理器 ====================

analyzer = LinkAnalyzer()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    welcome_msg = """👋 你好！我是链接识别 Bot

我可以识别以下平台的链接：

📺 B站
• 视频链接 (BV号)
• 用户主页

📕 小红书
• 笔记链接
• 用户主页

▶️ YouTube
• 视频链接
• 频道主页

🔗 使用方法
直接发送链接给我，我会自动识别并返回信息！

---
/test_bot.py - 简单测试版本"""

    await update.message.reply_text(welcome_msg, disable_web_page_preview=True)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_msg = """📖 帮助

支持的链接格式：

B站:
• 视频: bilibili.com/video/BV...
• 用户: space.bilibili.com/123456

小红书:
• 笔记: xiaohongshu.com/explore/...
• 用户: xiaohongshu.com/user/profile/...

YouTube:
• 视频: youtube.com/watch?v=... 或 youtu.be/...
• 频道: youtube.com/@username

直接发送链接即可！"""

    await update.message.reply_text(help_msg, disable_web_page_preview=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理普通消息（链接识别）"""
    text = update.message.text

    if not text:
        await update.message.reply_text("❓ 请发送一个链接")
        return

    # 提取链接
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        await update.message.reply_text(
            "❌ 没有检测到有效的链接\n\n"
            "请发送完整的 URL（以 http:// 或 https:// 开头）"
        )
        return

    url = url_match.group(0)

    # 发送"正在识别"消息
    status_msg = await update.message.reply_text("🔍 正在识别链接...")

    # 分析链接
    result = analyzer.analyze(url)

    # 删除状态消息
    await status_msg.delete()

    if result['platform'] == 'unknown':
        await update.message.reply_text(
            f"❌ 无法识别此链接\n\n"
            f"链接: {url[:50]}...\n\n"
            f"目前支持的平台：B站、小红书、YouTube"
        )
    else:
        response = analyzer.format_result(result)
        await update.message.reply_text(response, disable_web_page_preview=True)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """错误处理"""
    logging.error(f"Update {update} caused error {context.error}")


# ==================== 主程序 ====================

def main():
    """主入口"""
    print(f"\n{'='*60}")
    print(f"🤖 链接识别 Bot 启动中...")
    print(f"{'='*60}\n")

    print(f"✅ Bot Token: {BOT_TOKEN[:20]}...{BOT_TOKEN[-10:]}")

    # 创建应用
    application = Application.builder().token(BOT_TOKEN).build()

    # 添加处理器
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 添加错误处理器
    application.add_error_handler(error_handler)

    print(f"✅ Bot 配置完成")
    print(f"📝 在 Telegram 中搜索你的 Bot 并发送 /start 开始使用")
    print(f"\n{'='*60}")
    print(f"🔄 Bot 正在运行... (按 Ctrl+C 停止)")
    print(f"{'='*60}\n")

    # 启动轮询
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot 已停止")
