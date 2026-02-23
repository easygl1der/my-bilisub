#!/usr/bin/env python3
"""
Telegram Bot - B站首页推荐采集工具

功能：
- 通过 Telegram Bot 触发采集任务
- 支持命令控制和参数配置
- 采集完成后自动发送报告
- 支持 AI 分析功能

使用方法:
    python bot/bili_homepage_bot.py

命令列表:
    /start - 启动机器人，显示使用说明
    /scrape [次数] [--analyze] - 开始采集，默认刷新 10 次，可选 AI 分析
    /stop - 停止当前采集任务
    /analyze [文件] - 对已采集的数据进行 AI 分析
    /history - 查看采集历史
    /help - 显示帮助信息
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        # 如果 stdout 已经关闭或不可用，跳过修复
        pass

# 导入 telegram 库
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, filters, ContextTypes
except ImportError:
    print("❌ 未安装 python-telegram-bot")
    print("请运行: pip install python-telegram-bot")
    sys.exit(1)

# 导入采集模块
try:
    from archive.bili_homepage_scraper import BiliHomepageScraper, save_to_csv, save_to_json
    from analysis.homepage_analyzer import load_videos, analyze_with_gemini, generate_report, calculate_statistics
except ImportError as e:
    print(f"❌ 导入采集模块失败: {e}")
    sys.exit(1)


# ==================== 配置 ====================

CONFIG_PATH = Path(__file__).parent.parent / "config" / "telegram_config.json"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "homepage"
HISTORY_FILE = OUTPUT_DIR / "history.json"

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """加载配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


config = load_config()
BOT_TOKEN = config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')
PROXY_URL = config.get('proxy_url')
ALLOWED_USER_ID = int(config.get('chat_id', 0))  # 限制只有指定用户可以使用

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    sys.exit(1)

# 启用日志
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ==================== 用户状态管理 ====================

class UserManager:
    """用户状态管理"""

    def __init__(self):
        self.active_tasks = {}  # {user_id: task_running}
        self.task_stop_signals = {}  # {user_id: should_stop}

    def start_task(self, user_id: int) -> bool:
        """开始一个任务，返回 False 如果已有任务在运行"""
        if self.active_tasks.get(user_id, False):
            return False
        self.active_tasks[user_id] = True
        self.task_stop_signals[user_id] = False
        return True

    def end_task(self, user_id: int):
        """结束任务"""
        self.active_tasks[user_id] = False

    def stop_task(self, user_id: int) -> bool:
        """停止当前任务"""
        if self.active_tasks.get(user_id, False):
            self.task_stop_signals[user_id] = True
            return True
        return False

    def should_stop(self, user_id: int) -> bool:
        """检查任务是否应该停止"""
        return self.task_stop_signals.get(user_id, False)

    def is_task_running(self, user_id: int) -> bool:
        """检查是否有任务在运行"""
        return self.active_tasks.get(user_id, False)


user_manager = UserManager()


# ==================== 历史记录管理 ====================

class HistoryManager:
    """采集历史管理"""

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self):
        """保存历史记录"""
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def add_record(self, user_id: int, refresh_count: int,
                   video_count: int, csv_path: str, json_path: str,
                   analyze_path: str = None):
        """添加一条历史记录"""
        record = {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "用户ID": user_id,
            "刷新次数": refresh_count,
            "视频数量": video_count,
            "CSV路径": csv_path,
            "JSON路径": json_path,
            "分析报告": analyze_path,
        }
        self.history.append(record)
        self._save_history()

    def get_history(self, user_id: int = None, limit: int = 10) -> List[Dict]:
        """获取历史记录"""
        if user_id:
            user_history = [h for h in self.history if h.get("用户ID") == user_id]
        else:
            user_history = self.history

        # 按时间倒序
        user_history = sorted(user_history,
                             key=lambda x: x.get("时间", ""),
                             reverse=True)

        return user_history[:limit]


history_manager = HistoryManager()


# ==================== 采集任务 ====================

async def run_scrape_task(user_id: int, refresh_count: int,
                          analyze: bool = False) -> Dict:
    """
    运行采集任务

    Returns:
        {
            'success': bool,
            'video_count': int,
            'csv_path': str,
            'json_path': str,
            'report_path': str,
            'error': str,
            'report': str,
        }
    """
    result = {
        'success': False,
        'video_count': 0,
        'csv_path': '',
        'json_path': '',
        'report_path': '',
        'error': '',
        'report': '',
    }

    # 进度回调队列
    progress_queue = asyncio.Queue()

    # 创建进度报告任务
    async def progress_reporter():
        while True:
            msg = await progress_queue.get()
            if msg is None:  # 结束信号
                break
            level, message = msg
            try:
                # 简化进度消息
                short_msg = message[:100]
                await send_message(user_id, short_msg)
            except Exception as e:
                logger.error(f"发送进度消息失败: {e}")

    # 进度回调函数
    async def progress_callback(message: str, level: str = "info"):
        await progress_queue.put((level, message))

    # 启动进度报告任务
    reporter_task = asyncio.create_task(progress_reporter())

    try:
        # 创建爬虫实例
        scraper = BiliHomepageScraper(
            max_refresh=refresh_count,
            refresh_interval=3,
            headless=True,  # Bot 模式使用无头模式
            use_cookie=True,
            progress_callback=progress_callback,
        )

        # 启动并采集
        await scraper.start()

        # 检查是否需要停止
        if user_manager.should_stop(user_id):
            await progress_callback("任务已取消", "warning")
            result['error'] = '任务已取消'
            return result

        videos = await scraper.scrape()
        await scraper.close()

        if not videos:
            result['error'] = '未采集到视频'
            return result

        # 保存数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = str(OUTPUT_DIR / f"homepage_videos_{timestamp}.csv")
        json_path = str(OUTPUT_DIR / f"homepage_videos_{timestamp}.json")

        save_to_csv(videos, csv_path)
        save_to_json(videos, json_path)

        result['video_count'] = len(videos)
        result['csv_path'] = csv_path
        result['json_path'] = json_path

        await progress_callback(f"采集完成: {len(videos)} 个视频", "success")

        # AI 分析
        report_path = None
        if analyze:
            await progress_callback("正在进行 AI 分析...", "info")

            from analysis.subtitle_analyzer import GeminiClient
            client = GeminiClient(model='flash-lite')

            # 构建视频列表
            videos_text = ""
            for i, video in enumerate(videos[:50], 1):  # 限制50个
                videos_text += f"{i}. {video.title}\n   UP主: {video.uploader}\n\n"

            prompt = f"""你是一个视频内容分析师。请分析以下B站首页推荐视频列表，将它们分类统计。

视频列表:
{videos_text}

请按以下格式输出（使用 Markdown 格式，简洁版）:

## 📊 视频类型分布
| 类型 | 数量 | 占比 |
|------|------|------|
| ... | ... | ... |

## 🎯 推荐偏好
[简述账号推荐偏好]

## 📺 高频 UP 主
| UP主 | 次数 |
|------|------|
| ... | ... |
"""

            ai_result = client.generate_content(prompt)

            if ai_result['success']:
                result['report'] = ai_result['text']

                # 保存报告
                report_path = str(OUTPUT_DIR / f"homepage_analysis_{timestamp}.md")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(f"# B站首页推荐分析报告\n\n")
                    f.write(f"**采集时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"**刷新次数**: {refresh_count}\n\n")
                    f.write(f"**视频总数**: {len(videos)}\n\n")
                    f.write("---\n\n")
                    f.write(result['report'])

                result['report_path'] = report_path
                await progress_callback(f"AI 分析完成", "success")
            else:
                result['error'] = f"AI 分析失败: {ai_result.get('error', '未知错误')}"

        # 添加历史记录
        history_manager.add_record(
            user_id=user_id,
            refresh_count=refresh_count,
            video_count=len(videos),
            csv_path=csv_path,
            json_path=json_path,
            analyze_path=report_path
        )

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"采集任务异常: {e}", exc_info=True)

    finally:
        # 结束进度报告
        await progress_queue.put(None)
        await reporter_task
        user_manager.end_task(user_id)

    return result


# ==================== 辅助函数 ====================

async def send_message(user_id: int, text: str, reply_markup=None):
    """发送消息给用户"""
    application = user_manager.application
    try:
        await application.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        # 尝试不使用 Markdown
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup
            )
        except Exception:
            pass


async def send_file(user_id: int, file_path: str, caption: str = ""):
    """发送文件给用户"""
    application = user_manager.application
    try:
        await application.bot.send_document(
            chat_id=user_id,
            document=open(file_path, 'rb'),
            caption=caption
        )
    except Exception as e:
        logger.error(f"发送文件失败: {e}")


# ==================== 命令处理 ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动命令"""
    user_id = update.effective_user.id

    # 检查权限
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ 您没有权限使用此 Bot")
        return

    help_text = """🤖 *B站首页推荐采集 Bot*

欢迎使用！我可以帮您自动采集和分析 B站 首页推荐视频。

*命令列表:*

`/scrape [次数]` - 开始采集（默认 10 次）
`/scrape 10 --analyze` - 采集并 AI 分析
`/stop` - 停止当前任务
`/analyze [文件]` - 分析已有数据
`/history` - 查看采集历史
`/help` - 显示帮助

*使用示例:*
• `/scrape` - 采集 10 次
• `/scrape 20` - 采集 20 次
• `/scrape 5 --analyze` - 采集 5 次并分析

*注意:*
• 采集需要登录 B站 账号（使用 Cookie）
• 采集过程会在后台运行
• 结果会自动发送给您"""

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """采集命令"""
    user_id = update.effective_user.id

    # 检查权限
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ 您没有权限使用此 Bot")
        return

    # 检查是否有任务在运行
    if user_manager.is_task_running(user_id):
        await update.message.reply_text("⚠️ 已有任务在运行，请先等待完成或使用 /stop 停止")
        return

    # 解析参数
    args = context.args or []
    refresh_count = 10
    analyze = False

    for arg in args:
        if arg.isdigit():
            refresh_count = int(arg)
        elif arg == '--analyze':
            analyze = True

    # 限制范围
    if refresh_count < 1:
        refresh_count = 1
    elif refresh_count > 50:
        refresh_count = 50

    await update.message.reply_text(
        f"🚀 开始采集任务\n"
        f"• 刷新次数: {refresh_count}\n"
        f"• AI 分析: {'是' if analyze else '否'}\n\n"
        f"⏳ 采集过程中，结果会陆续发送..."
    )

    # 在后台运行采集任务
    asyncio.create_task(run_scrape_task_wrapper(user_id, refresh_count, analyze))


async def run_scrape_task_wrapper(user_id: int, refresh_count: int, analyze: bool):
    """包装采集任务，处理结果发送"""
    result = await run_scrape_task(user_id, refresh_count, analyze)

    if result['success']:
        # 发送结果摘要
        summary = f"""✅ *采集完成！*

📊 *统计信息:*
• 视频总数: {result['video_count']}
• CSV 文件: `{Path(result['csv_path']).name}`"
        """

        if result.get('report_path'):
            summary += f"\n• 分析报告: `{Path(result['report_path']).name}`"

        if result.get('report'):
            summary += f"\n\n📋 *分析摘要:*\n\n{result['report'][:500]}"

        await send_message(user_id, summary)

        # 发送文件
        try:
            await send_file(user_id, result['csv_path'], "📊 采集数据 (CSV)")
        except Exception:
            pass

        if result.get('report_path'):
            try:
                await send_file(user_id, result['report_path'], "📋 AI 分析报告")
            except Exception:
                pass
    else:
        await send_message(user_id, f"❌ 采集失败: {result.get('error', '未知错误')}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止命令"""
    user_id = update.effective_user.id

    if user_manager.stop_task(user_id):
        await update.message.reply_text("🛑 正在停止任务...")
    else:
        await update.message.reply_text("ℹ️ 没有正在运行的任务")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """分析命令"""
    user_id = update.effective_user.id

    # 检查权限
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ 您没有权限使用此 Bot")
        return

    args = context.args

    if not args:
        # 显示最近的采集历史
        history = history_manager.get_history(user_id, limit=5)
        if not history:
            await update.message.reply_text("📭 暂无采集历史")
            return

        msg = "📜 *最近的采集记录:*\n\n"
        for i, record in enumerate(history, 1):
            msg += f"{i}. {record['时间']}\n"
            msg += f"   视频: {record['视频数量']} | 刷新: {record['刷新次数']}次\n"
            msg += f"   文件: `{Path(record['CSV路径']).name}`\n\n"

        msg += "💡 使用 `/analyze 文件路径` 来分析指定文件"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    # 分析指定文件
    file_path = ' '.join(args)
    file_path = str(OUTPUT_DIR / file_path) if not Path(file_path).is_absolute() else file_path

    await update.message.reply_text(f"🔍 正在分析文件: `{Path(file_path).name}`")

    try:
        videos = load_videos(file_path)
        if not videos:
            await update.message.reply_text("❌ 文件中没有视频数据")
            return

        stats = calculate_statistics(videos)
        ai_result = analyze_with_gemini(videos, model='flash-lite')

        if ai_result['success']:
            report = ai_result['report']
            await send_message(user_id, f"📋 *分析报告*\n\n{report[:1000]}")

            # 保存并发送完整报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = str(OUTPUT_DIR / f"homepage_analysis_{timestamp}.md")
            full_report = generate_report(videos, report, stats, 'flash-lite')

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(full_report)

            await send_file(user_id, report_path, "📋 完整分析报告")
        else:
            await update.message.reply_text(f"❌ 分析失败: {ai_result.get('error')}")

    except Exception as e:
        await update.message.reply_text(f"❌ 分析异常: {str(e)}")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """历史命令"""
    user_id = update.effective_user.id

    # 检查权限
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ 您没有权限使用此 Bot")
        return

    history = history_manager.get_history(user_id, limit=10)

    if not history:
        await update.message.reply_text("📭 暂无采集历史")
        return

    msg = "📜 *采集历史* (最近10条)\n\n"
    for i, record in enumerate(history, 1):
        msg += f"*{i}. {record['时间']}*\n"
        msg += f"📊 视频: {record['视频数量']} | 刷新: {record['刷新次数']}次\n"
        msg += f"📁 `{Path(record['CSV路径']).name}`\n"
        if record.get('分析报告'):
            msg += f"📋 有分析报告\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    await start_command(update, context)


# ==================== 主程序 ====================

def main():
    """启动 Bot"""
    # 构建应用
    builder = (
        Application.builder()
        .token(BOT_TOKEN)
    )

    # 如果配置了代理，使用代理
    if PROXY_URL:
        import httpx
        builder = builder.http_client(httpx.AsyncClient(proxy=PROXY_URL))
        logger.info(f"使用代理: {PROXY_URL}")

    application = builder.build()

    # 保存应用实例
    user_manager.application = application

    # 添加命令处理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scrape", scrape_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("help", help_command))

    # 启动 Bot
    print("=" * 60)
    print("🤖 B站首页推荐采集 Bot")
    print("=" * 60)
    print(f"✅ Bot 已启动")
    print(f"📝 Token: {BOT_TOKEN[:20]}...")
    if ALLOWED_USER_ID:
        print(f"👤 允许用户: {ALLOWED_USER_ID}")
    print("=" * 60)

    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
