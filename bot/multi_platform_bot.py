#!/usr/bin/env python3
"""
多平台内容分析 Bot - 扩展版本

基于 video_bot.py，增加了：
1. 集成统一分析入口 (utils/unified_content_analyzer.py)
2. 自动平台检测和路由
3. 支持B站和小红书的用户主页分析
4. 增强的进度通知

使用方法:
    python bot/multi_platform_bot.py

配置:
    1. 创建 config/bot_config.json，填入 Telegram Bot Token
    2. 配置 GEMINI_API_KEY 环境变量
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict

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
UNIFIED_ANALYZER = PROJECT_ROOT / "utils" / "unified_content_analyzer.py"

# ==================== URL检测 ====================

def detect_platform_and_type(url: str) -> Dict[str, str]:
    """
    检测平台和内容类型

    Returns:
        {
            'platform': 'bili' | 'xhs' | 'unknown',
            'type': 'video' | 'image' | 'user',
            'url': url
        }
    """
    url_lower = url.lower()

    # B站检测
    if 'bilibili.com' in url_lower:
        if '/space/' in url_lower or 'acg' in url_lower:
            return {'platform': 'bili', 'type': 'user', 'url': url}
        else:
            return {'platform': 'bili', 'type': 'video', 'url': url}

    # 小红书检测
    elif 'xiaohongshu.com' in url_lower or 'xhslink.com' in url_lower:
        if '/user/profile/' in url_lower:
            return {'platform': 'xhs', 'type': 'user', 'url': url}
        elif '/explore/' in url_lower:
            return {'platform': 'xhs', 'type': 'note', 'url': url}
        else:
            return {'platform': 'xhs', 'type': 'note', 'url': url}

    return {'platform': 'unknown', 'type': 'unknown', 'url': url}


# ==================== 统一分析调用器 ====================

class UnifiedAnalyzerCaller:
    """统一分析入口调用器"""

    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    def _update_progress(self, message: str):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(message)

    def analyze(self, url: str, options: Dict = None) -> Dict:
        """
        调用统一分析入口

        Args:
            url: 内容链接
            options: 选项字典 {
                'count': 处理数量,
                'type': 内容类型,
                'mode': 分析模式,
                'model': Gemini模型
            }

        Returns:
            {
                'success': bool,
                'output': str,
                'error': str
            }
        """
        options = options or {}

        self._update_progress(f"🔍 检测平台和内容类型...")

        # 检测平台和类型
        detection = detect_platform_and_type(url)

        if detection['platform'] == 'unknown':
            return {
                'success': False,
                'output': '',
                'error': f'无法识别的平台: {url}'
            }

        self._update_progress(f"✅ 检测到: {detection['platform']} - {detection['type']}")

        # 构建命令
        cmd = [
            sys.executable,
            str(UNIFIED_ANALYZER),
            '--url', url
        ]

        # 添加选项
        if options.get('count'):
            cmd.extend(['--count', str(options['count'])])

        if options.get('type'):
            cmd.extend(['--type', options['type']])

        if options.get('mode'):
            cmd.extend(['--mode', options['mode']])

        if options.get('model'):
            cmd.extend(['--model', options['model']])

        self._update_progress(f"🚀 开始分析...")

        try:
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=3600,  # 1小时超时
                cwd=PROJECT_ROOT
            )

            if result.returncode == 0:
                self._update_progress(f"✅ 分析完成！")
                return {
                    'success': True,
                    'output': result.stdout,
                    'error': ''
                }
            else:
                self._update_progress(f"❌ 分析失败")
                return {
                    'success': False,
                    'output': result.stdout,
                    'error': result.stderr
                }

        except subprocess.TimeoutExpired:
            self._update_progress(f"⏱️ 分析超时")
            return {
                'success': False,
                'output': '',
                'error': '执行超时（超过1小时）'
            }

        except Exception as e:
            self._update_progress(f"❌ 执行出错: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }


# ==================== Bot 集成 ====================

# 尝试导入 telegram 库
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")


class MultiPlatformBot:
    """多平台内容分析 Bot"""

    def __init__(self):
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError("请先安装 python-telegram-bot")

        # 加载配置
        self.config = self._load_config()

        # 创建输出目录
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 初始化 Telegram Application
        self.application = Application.builder().token(self.config['bot_token']).build()

        # 注册命令处理器
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("analyze", self.cmd_analyze))
        self.application.add_handler(CommandHandler("bili", self.cmd_bili))
        self.application.add_handler(CommandHandler("xhs", self.cmd_xhs))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_text))

    def _load_config(self) -> Dict:
        """加载配置"""
        # 从文件加载
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 如果配置中有Gemini API Key，设置到环境变量
                if 'gemini_api_key' in config and config['gemini_api_key']:
                    os.environ['GEMINI_API_KEY'] = config['gemini_api_key']
                    print("✅ Gemini API Key 已从配置文件加载")
                return config
            except Exception as e:
                print(f"⚠️ 配置文件加载失败: {e}")

        # 从环境变量加载
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ValueError(
                "未配置 Bot Token！\n"
                f"请创建 {CONFIG_PATH} 或设置 TELEGRAM_BOT_TOKEN 环境变量"
            )

        return {'bot_token': bot_token}

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        user = update.effective_user

        welcome_msg = f"""👋 你好，{user.first_name}！

我是**多平台内容分析 Bot**，可以帮你：

🎯 **支持平台**
• B站 (bilibili.com) - 视频分析
• 小红书 (xiaohongshu.com) - 视频和图文分析

🚀 **快速开始**
• 发送任意链接，我自动检测平台
• 或使用命令: /analyze <链接>

📝 **命令列表**
• /analyze <链接> - 自动检测平台并分析
• /bili <链接> - B站内容分析
• /xhs <链接> - 小红书内容分析
• /help - 查看详细帮助

💡 **支持的内容**
1. B站用户主页 - 分析多个视频
2. B站单个视频 - 分析单个视频
3. 小红书用户主页 - 分析视频或图文
4. 小红书单个笔记 - 分析视频或图文

现在请发送一个链接试试吧！"""

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_msg = """📖 **使用帮助**

**支持的链接格式**

🎬 **B站**
• 用户主页: https://space.bilibili.com/用户ID
• 单个视频: https://www.bilibili.com/video/BV号

📱 **小红书**
• 用户主页: https://www.xiaohongshu.com/user/profile/用户ID
• 单个笔记: https://www.xiaohongshu.com/explore/笔记ID

**分析模式**

1️⃣ **自动检测** (推荐)
   /analyze <链接>
   • 自动识别平台和类型
   • 选择最合适的分析方式

2️⃣ **B站专用**
   /bili <链接>
   • 视频字幕提取
   • AI 内容分析
   • 支持用户主页批量处理

3️⃣ **小红书专用**
   /xhs <链接>
   • 视频分析
   • 图文分析（含风格检测）
   • 支持用户主页批量处理

**高级选项**

处理数量限制：
• /analyze <链接> --count 10

**注意事项**
• 分析时间取决于内容数量
• 建议每次处理不超过20个内容
• 需要配置 Gemini API Key"""

        await update.message.reply_text(help_msg, parse_mode='Markdown')

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """自动检测并分析"""
        # 提取URL
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ 请提供链接\n\n"
                "用法: /analyze <链接>",
                parse_mode='Markdown'
            )
            return

        url = context.args[0]

        # 检测平台
        detection = detect_platform_and_type(url)

        if detection['platform'] == 'unknown':
            await update.message.reply_text(
                f"❌ 无法识别的平台\n\n"
                f"当前支持的平台:\n"
                f"• B站 (bilibili.com)\n"
                f"• 小红书 (xiaohongshu.com)",
                parse_mode='Markdown'
            )
            return

        # 发送确认消息
        status_msg = await update.message.reply_text(
            f"🔍 检测到: **{detection['platform']}** - **{detection['type']}**\n\n"
            f"⏳ 开始分析，请稍候...",
            parse_mode='Markdown'
        )

        # 创建进度回调
        async def progress_callback(message: str):
            try:
                await status_msg.edit_text(message)
            except:
                pass

        # 执行分析
        caller = UnifiedAnalyzerCaller(
            progress_callback=lambda msg: asyncio.create_task(progress_callback(msg))
        )

        result = caller.analyze(url)

        # 发送结果
        if result['success']:
            await status_msg.edit_text(
                f"✅ 分析完成！\n\n"
                f"📊 结果:\n{result['output'][-500:]}"  # 最后500字符
            )
        else:
            await status_msg.edit_text(
                f"❌ 分析失败\n\n"
                f"错误: {result['error'][-200:]}"
            )

    async def cmd_bili(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """B站专用命令"""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ 请提供B站链接\n\n用法: /bili <链接>")
            return

        url = context.args[0]

        await update.message.reply_text(
            f"🎬 开始分析B站内容...\n\n"
            f"🔗 {url}\n\n"
            f"⏳ 请稍候...",
            parse_mode='Markdown'
        )

        # TODO: 实现B站专用逻辑
        await update.message.reply_text("⚠️ B站专用功能开发中，请使用 /analyze")

    async def cmd_xhs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """小红书专用命令"""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ 请提供B站链接\n\n用法: /bili <链接>")
            return

        url = context.args[0]

        await update.message.reply_text(
            f"🎬 开始分析B站内容...\n\n"
            f"🔗 {url}\n\n"
            f"⏳ 请稍候...",
            parse_mode='Markdown'
        )

        # TODO: 实现B站专用逻辑
        await update.message.reply_text("⚠️ B站专用功能开发中，请使用 /analyze")

    async def cmd_xhs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """小红书专用命令"""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("❌ 请提供小红书链接\n\n用法: /xhs <链接>")
            return

        url = context.args[0]

        await update.message.reply_text(
            f"📱 开始分析小红书内容...\n\n"
            f"🔗 {url}\n\n"
            f"⏳ 请稍候...",
            parse_mode='Markdown'
        )

        # TODO: 实现小红书专用逻辑
        await update.message.reply_text("⚠️ 小红书专用功能开发中，请使用 /analyze")

    async def msg_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息（自动检测）"""
        text = update.message.text.strip()

        # 检查是否是URL
        if not text.startswith('http'):
            await update.message.reply_text(
                "💡 请发送一个视频或笔记链接\n\n"
                "发送 /help 查看帮助"
            )
            return

        # 当作URL处理
        detection = detect_platform_and_type(text)

        if detection['platform'] == 'unknown':
            await update.message.reply_text(
                "❌ 无法识别的链接\n\n"
                "支持的平台: B站、小红书"
            )
            return

        # 自动调用分析
        await self.cmd_analyze(update, context)

    def run(self):
        """启动Bot"""
        try:
            print("🚀 多平台内容分析 Bot 启动中...")
            print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass  # 忽略编码错误

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


# ==================== 主程序 ====================

def main():
    """主函数"""
    if not TELEGRAM_AVAILABLE:
        print("❌ 请先安装 python-telegram-bot:")
        print("   pip install python-telegram-bot")
        return 1

    try:
        bot = MultiPlatformBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Bot 已停止")
    except Exception as e:
        print(f"\n❌ Bot 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
