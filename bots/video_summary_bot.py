#!/usr/bin/env python3
"""
Telegram Bot - 多平台内容总结（B站+小红书）

功能：
- 识别B站视频链接，提取字幕，AI生成总结
- 识别小红书笔记链接，AI分析内容
- 刷B站/小红书主页并生成AI分析报告

使用方法：
    E:\Anaconda\envs\bilisub\python.exe bot\video_summary_bot.py
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

# 导入字幕提取模块
from bilibili_api import video
from workflows.batch_subtitle_fetch import get_credential, format_srt_time
import aiohttp

# ==================== 配置 ====================

CONFIG_PATH = Path(__file__).parent.parent / "config" / "telegram_config.json"
SUBTITLE_OUTPUT_DIR = Path(__file__).parent.parent / "output" / "subtitles"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
BOT_TOKEN = config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')
PROXY_URL = config.get('proxy_url')  # 支持 http://或 socks5:// 代理

if not BOT_TOKEN:
    print("❌ 未配置 Bot Token")
    sys.exit(1)

# 启用日志
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# ==================== 用户状态管理 ====================

class UserManager:
    """用户状态管理"""

    def __init__(self):
        self.user_modes = {}  # {user_id: mode}
        self.active_tasks = {}  # {user_id: task_id}  # 正在进行的任务
        self.task_processes = {}  # {task_id: process}  # 子进程对象
        self.task_stop_signals = {}  # {task_id: bool}  # 停止信号

    def get_mode(self, user_id: int) -> str:
        """获取用户的分析模式"""
        return self.user_modes.get(user_id, 'knowledge')  # 默认 knowledge

    def set_mode(self, user_id: int, mode: str):
        """设置用户的分析模式"""
        self.user_modes[user_id] = mode

    def start_task(self, user_id: int, task_id: str) -> bool:
        """开始一个任务，返回 False 如果已有任务在运行"""
        if user_id in self.active_tasks:
            return False
        self.active_tasks[user_id] = task_id
        self.task_stop_signals[task_id] = False
        return True

    def set_process(self, user_id: int, process):
        """保存子进程对象"""
        if user_id in self.active_tasks:
            task_id = self.active_tasks[user_id]
            self.task_processes[task_id] = process

    def end_task(self, user_id: int):
        """结束任务"""
        if user_id in self.active_tasks:
            task_id = self.active_tasks[user_id]
            # 清理进程记录
            if task_id in self.task_processes:
                del self.task_processes[task_id]
            if task_id in self.task_stop_signals:
                del self.task_stop_signals[task_id]
            del self.active_tasks[user_id]

    async def stop_task(self, user_id: int) -> bool:
        """停止当前任务（终止子进程）"""
        if user_id in self.active_tasks:
            task_id = self.active_tasks[user_id]
            self.task_stop_signals[task_id] = True

            # 终止子进程
            if task_id in self.task_processes:
                process = self.task_processes[task_id]
                try:
                    process.terminate()
                    # 等待最多5秒让进程优雅退出
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        # 如果进程不退出，强制杀死
                        process.kill()
                        await process.wait()
                except Exception as e:
                    # 进程可能已经结束
                    pass
            return True
        return False

    def should_stop(self, task_id: str) -> bool:
        """检查任务是否应该停止"""
        return self.task_stop_signals.get(task_id, False)

user_manager = UserManager()


# ==================== 分析模式提示词 ====================

ANALYSIS_PROMPTS = {
    'simple': """请为以下视频字幕生成简洁的总结：

视频标题: {video_title}
视频链接: {video_url}

字幕内容:
{text}

请生成（简洁明了）：
1. 视频大意（100字以内）
2. 核心观点（3-5个要点）
3. 值得记录的信息""",

    'knowledge': """你是一个专业的视频内容分析师，擅长将视频内容转化为结构化的知识库笔记。请详细分析这个视频，输出用于构建"第二大脑"的笔记。

请严格按照以下格式输出（保持所有标题和符号）：

## 📋 视频基本信息
- **视频标题**: {video_title}
- **视频链接**: {video_url}
- **核心主题**: 一句话概括

## 📖 视频大意（100-200字）
用精炼的书面语言概括视频核心内容，去除冗余的前情提要和无关信息

## 🎯 核心观点
提取视频的主要观点和论点，每个观点用简洁的语言呈现

## 💎 金句/好词好句提取
从字幕中提取值得记录的精彩句子、深刻观点或好词好句

## 📝 核心内容整理
将视频内容整理成精炼的书面表达，去除口语化冗余，保留核心信息

## ⚠️ 内容质量评估
- 新颖性: 5星评级
- 实用性: 5星评级
- 深度: 5星评级
- 推荐收藏: 是/否

字幕内容:
{text}

---
请确保输出结构完整，每个部分都要有实质内容。""",

    'detailed': """你是一个专业的视频内容分析师。请对这个视频进行全面深入的分析。

视频标题: {video_title}
视频链接: {video_url}

请提供以下详细分析：

## 📋 视频基本信息
- 视频类型: 教育课程/知识科普/新闻评论/产品测评/其他
- 核心主题: 一句话概括
- 内容结构: 流水账式/观点论证式/新闻汇总式/故事叙述式

## 📖 视频大意（200-300字）
用精炼的书面语言概括视频核心内容

## 🎯 核心观点（三段论）
- 大前提: 普遍性前提或背景
- 小前提: 具体情境或条件
- 结论: 最终观点或主张

## 📊 论点论据结构
1. 主要论点
   - 论述内容: 详细说明
   - 支持论据: 数据、案例、逻辑推理
   - 可信度评估: 高/中/低

2. 次要论点（如有）
   - 论述内容: 详细说明
   - 支持论据: 数据、案例、逻辑推理

## 💎 金句/好词好句提取
- 引经据典: 原句
- 故事/案例: 原句或描述
- 精辟论据: 原句
- 深刻观点: 原句
- 好词好句: 原句

## 📝 书面文稿
将视频内容整理成精炼的书面表达文稿，去除所有口语化冗余

## ⚠️ 内容质量分析
- 情绪操控检测: 是/否
- 信息源可信度: 高/中/低
- 知识价值评估: 5星评级

字幕内容:
{text}

---
请确保输出结构完整，每个部分都要有实质内容。""",

    'transcript': """请尽可能详细地提取这个视频中的对话和解说内容，保留重要细节。

视频标题: {video_title}
视频链接: {video_url}

字幕内容:
{text}

请按时间顺序整理，保留完整的对话内容和关键信息。"""
}


# ==================== 链接识别 ====================

class LinkAnalyzer:
    """链接分析器"""

    def analyze(self, url: str) -> dict:
        """分析链接（支持B站和小红书）"""
        url = url.strip()
        result = {'platform': 'unknown', 'type': 'unknown', 'id': '', 'url': url}

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
            elif '/discovery/item/' in url:
                result['type'] = 'note'
                result['id'] = url.split('/discovery/item/')[-1].split('?')[0]
            else:
                result['type'] = 'note'
                # 尝试从URL中提取ID（36位十六进制）
                id_match = re.search(r'([a-f0-9]{32})', url)
                if id_match:
                    result['id'] = id_match.group(1)

        return result


# ==================== 视频总结器 ====================

class VideoSummarizer:
    """视频总结器"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.subtitle_dir = SUBTITLE_OUTPUT_DIR
        self.subtitle_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_subtitle(self, bvid: str) -> dict:
        """提取B站字幕"""
        result = {'success': False, 'srt_path': None, 'error': None}

        try:
            credential = get_credential()
            if not credential:
                result['error'] = '未找到B站Cookie，请配置 cookies_bilibili_api.txt'
                return result

            v = video.Video(bvid=bvid, credential=credential)

            # 获取视频信息
            info = await v.get_info()
            cid = info["cid"]
            title = info.get("title", "unknown")

            # 获取字幕列表
            player_info = await v.get_player_info(cid=cid)
            subtitles = player_info.get("subtitle", {}).get("subtitles", [])

            if not subtitles:
                result['error'] = '该视频无字幕'
                return result

            # 下载字幕
            sub = subtitles[0]
            url = "https:" + sub["subtitle_url"]
            lan = sub['lan']

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json(content_type=None)

            # 保存为 SRT
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            srt_path = self.subtitle_dir / f"{safe_title}_{lan}.srt"

            with open(srt_path, 'w', encoding='utf-8') as f:
                for item in data.get("body", []):
                    start_time = item["from"]
                    end_time = item["to"]
                    content = item["content"]
                    f.write(f"{1}\n")
                    f.write(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n")
                    f.write(f"{content}\n\n")

            result['success'] = True
            result['srt_path'] = str(srt_path)
            result['title'] = title

        except Exception as e:
            result['error'] = str(e)

        return result

    def srt_to_text(self, srt_path: str) -> str:
        """将SRT转换为纯文本"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = []
            for line in content.split('\n'):
                # 跳过序号和时间轴
                if re.match(r'^\d+$', line):
                    continue
                if '-->' in line:
                    continue
                if line.strip():
                    lines.append(line.strip())

            text = ' '.join(lines)
            # 限制长度
            if len(text) > 8000:
                text = text[:8000] + '...'

            return text
        except Exception as e:
            return f"读取字幕失败: {e}"

    async def generate_summary(self, srt_path: str, video_title: str, video_url: str, mode: str = 'knowledge', task_id: str = None) -> dict:
        """使用Gemini生成总结

        Returns:
            {'success': bool, 'text': str, 'error': str, 'stats': dict}
        """
        import time

        try:
            # 导入 Gemini 客户端
            sys.path.insert(0, str(self.project_root))
            from analysis.subtitle_analyzer import GeminiClient

            client = GeminiClient(model='flash-lite')

            # 读取字幕
            text = self.srt_to_text(srt_path)

            # 获取对应模式的提示词
            prompt_template = ANALYSIS_PROMPTS.get(mode, ANALYSIS_PROMPTS['knowledge'])
            prompt = prompt_template.format(
                video_title=video_title,
                video_url=video_url,
                text=text
            )

            # 计时开始
            start_time = time.time()

            result = client.generate_content(prompt)

            # 计时结束
            elapsed_time = time.time() - start_time

            if result['success']:
                stats = {
                    'elapsed_time': elapsed_time,
                    'input_tokens': result.get('input_tokens', 0),
                    'output_tokens': result.get('output_tokens', 0),
                    'total_tokens': result.get('tokens', 0)
                }

                return {
                    'success': True,
                    'text': result['text'],
                    'stats': stats
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', '未知错误'),
                    'stats': {'elapsed_time': elapsed_time}
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stats': {}
            }


# ==================== Bot 处理器 ====================

analyzer = LinkAnalyzer()
summarizer = VideoSummarizer()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    user_id = update.effective_user.id
    current_mode = user_manager.get_mode(user_id)

    welcome_msg = f"""👋 你好！我是多平台内容分析 Bot

🎯 当前模式: {current_mode.upper()}

功能：
• B站视频 - 提取字幕，AI生成总结
• 小红书笔记 - AI分析图文内容
• 刷B站/小红书主页 - 生成AI分析报告

使用方法：
• 发送B站/小红书链接即可开始分析
• 发送 /mode 切换分析模式
• 发送 /scrape_bilibili 刷B站首页推荐
• 发送 /help 查看帮助"""

    await update.message.reply_text(welcome_msg)


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换分析模式"""
    user_id = update.effective_user.id

    # 创建模式选择按钮
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 简洁版", callback_data='mode_simple'),
            InlineKeyboardButton("📚 知识库版", callback_data='mode_knowledge'),
        ],
        [
            InlineKeyboardButton("📊 详细版", callback_data='mode_detailed'),
            InlineKeyboardButton("📄 转录版", callback_data='mode_transcript'),
        ],
    ])

    current_mode = user_manager.get_mode(user_id)
    mode_names = {
        'simple': '简洁版',
        'knowledge': '知识库版',
        'detailed': '详细版',
        'transcript': '转录版'
    }

    help_text = f"""� 分析模式选择

当前模式: **{mode_names.get(current_mode, current_mode).upper()}**

选择模式:"""

    await update.message.reply_text(help_text, reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_msg = """📖 帮助

📋 分析模式说明：
• 简洁版 - 快速总结，100字内大意+核心观点
• 知识库版 - 结构化笔记，适合构建第二大脑
• 详细版 - 全面分析，包含论据结构和质量评估
• 转录版 - 详细提取对话和解说内容

🔧 命令列表：
• /start - 开始使用
• /mode - 切换分析模式
• /stop - 停止当前分析
• /help - 查看帮助

🆕 刷主页功能：
• /scrape_bilibili - 刷B站首页推荐
  格式: /scrape_bilibili [刷新次数] [最大视频数]
  示例: /scrape_bilibili 3 50
  默认: 刷新3次，最多50个视频

• /scrape_xiaohongshu - 刷小红书推荐
  格式: /scrape_xiaohongshu [刷新次数] [最大笔记数]
  示例: /scrape_xiaohongshu 3 50
  默认: 刷新3次，最多50个笔记

💡 使用方法：
• 发送B站视频链接进行视频分析
• 发送小红书笔记链接进行图文分析
• 使用 /scrape_bilibili 自动刷B站首页
• 使用 /scrape_xiaohongshu 自动刷小红书推荐

💡 分析统计：
分析完成后会显示耗时和Token消耗"""

    await update.message.reply_text(help_msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止当前分析"""
    user_id = update.effective_user.id

    if await user_manager.stop_task(user_id):
        await update.message.reply_text("🛑 正在停止任务...")
    else:
        await update.message.reply_text("ℹ️ 当前没有正在进行的任务")


async def cmd_scrape_bilibili(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """刷B站首页推荐"""
    user_id = update.effective_user.id
    task_id = f"bili_scrape_{user_id}"

    # 检查是否已有任务在运行
    if not user_manager.start_task(user_id, task_id):
        await update.message.reply_text("⚠️ 你已有任务在运行中，请先等待完成或使用 /stop 停止")
        return

    # 解析参数
    args = context.args
    refresh_count = 3
    max_videos = 50

    try:
        if args and len(args) >= 1:
            refresh_count = int(args[0])
        if args and len(args) >= 2:
            max_videos = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ 参数错误，格式: /scrape_bilibili [刷新次数] [最大视频数]\n示例: /scrape_bilibili 3 50")
        user_manager.end_task(user_id)
        return

    status_msg = await update.message.reply_text(
        f"🚀 开始刷B站首页推荐\n\n"
        f"📊 配置:\n"
        f"  • 刷新次数: {refresh_count}\n"
        f"  • 最大视频数: {max_videos}\n\n"
        f"⏳ 启动中..."
    )

    try:
        import subprocess
        from datetime import datetime

        # 构建命令
        script_path = Path(__file__).parent.parent / "workflows" / "ai_bilibili_homepage.py"
        cmd = [
            r"E:\Anaconda\envs\bilisub\python.exe",
            str(script_path),
            "--mode", "full",
            "--refresh-count", str(refresh_count),
            "--max-videos", str(max_videos)
        ]

        await status_msg.edit_text(
            f"🚀 开始刷B站首页推荐\n\n"
            f"📊 配置:\n"
            f"  • 刷新次数: {refresh_count}\n"
            f"  • 最大视频数: {max_videos}\n\n"
            f"📡 正在采集首页推荐..."
        )

        # 执行采集脚本
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent)
        )

        # 保存进程对象，以便 /stop 可以终止它
        user_manager.set_process(user_id, process)

        # 等待完成
        try:
            stdout, stderr = await process.communicate()
        except (asyncio.CancelledError, BrokenPipeError, OSError, ProcessLookupError) as e:
            # 进程被终止（可能是用户使用 /stop 命令）
            task_id = user_manager.active_tasks.get(user_id, '')
            if task_id and user_manager.should_stop(task_id):
                await status_msg.edit_text("🛑 任务已停止")
            else:
                await status_msg.edit_text(f"❌ 进程异常终止: {type(e).__name__}")
            return

        if process.returncode == 0:
            # 查找生成的报告文件
            from datetime import datetime
            date_str = datetime.now().strftime('%Y-%m-%d')
            report_path = Path(__file__).parent.parent / "MediaCrawler" / "bilibili_subtitles" / f"homepage_{date_str}_AI总结.md"

            if report_path.exists():
                # 读取报告内容
                with open(report_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()

                # 发送摘要
                summary_lines = []
                for line in report_content.split('\n')[:50]:  # 前50行
                    summary_lines.append(line)
                    if len('\n'.join(summary_lines)) > 3500:  # Telegram消息长度限制
                        break

                summary = '\n'.join(summary_lines)

                await status_msg.edit_text(
                    f"✅ B站首页推荐刷取完成！\n\n"
                    f"📊 采集信息:\n"
                    f"  • 刷新次数: {refresh_count}\n"
                    f"  • 最大视频数: {max_videos}\n\n"
                    f"📝 以下是报告摘要:\n\n"
                    f"{summary}\n\n"
                    f"📁 完整报告已通过文件发送"
                )

                # 发送完整报告文件
                line_count = len(report_content.split('\n'))
                await update.message.reply_document(
                    document=str(report_path),
                    caption=f"📄 B站首页推荐分析报告\n• 刷新次数: {refresh_count}\n• 采集视频数: {line_count} 行",
                    filename=report_path.name
                )
            else:
                await status_msg.edit_text(
                    f"✅ 刷取完成，但未找到报告文件\n\n"
                    f"可能的原因:\n"
                    f"  • 采集失败\n"
                    f"  • AI分析失败\n"
                    f"  • 文件路径错误\n\n"
                    f"请检查控制台日志"
                )
        else:
            error_msg = stderr.decode('utf-8', errors='ignore')[-500:]
            await status_msg.edit_text(
                f"❌ 刷取失败\n\n"
                f"错误信息:\n{error_msg}"
            )

    except Exception as e:
        await status_msg.edit_text(f"❌ 执行出错: {str(e)}")
    finally:
        user_manager.end_task(user_id)


async def handle_xiaohongshu_note(update: Update, result: dict, status_msg):
    """处理小红书笔记（使用unified_content_analyzer）"""
    try:
        import subprocess
        from datetime import datetime

        # 使用统一分析入口
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "utils" / "unified_content_analyzer.py"),
            '--url', result['url']
        ]

        await status_msg.edit_text(
            f"📱 识别到小红书笔记\n"
            f"ID: {result['id']}\n\n"
            f"⏳ 正在分析..."
        )

        # 执行分析
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent),
            encoding='utf-8',
            errors='replace'
        )

        # 等待完成
        await process.communicate()

        if process.returncode == 0:
            await status_msg.edit_text(
                f"✅ 小红书笔记分析完成！\n\n"
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


async def cmd_scrape_xiaohongshu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """刷小红书推荐"""
    user_id = update.effective_user.id
    task_id = f"xhs_scrape_{user_id}"

    # 检查是否已有任务在运行
    if not user_manager.start_task(user_id, task_id):
        await update.message.reply_text("⚠️ 你已有任务在运行中，请先等待完成或使用 /stop 停止")
        return

    # 解析参数
    args = context.args
    refresh_count = 3
    max_notes = 50

    try:
        if args and len(args) >= 1:
            refresh_count = int(args[0])
        if args and len(args) >= 2:
            max_notes = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ 参数错误，格式: /scrape_xiaohongshu [刷新次数] [最大笔记数]\n示例: /scrape_xiaohongshu 3 50")
        user_manager.end_task(user_id)
        return

    status_msg = await update.message.reply_text(
        f"🚀 开始刷小红书推荐\n\n"
        f"📊 配置:\n"
        f"  • 刷新次数: {refresh_count}\n"
        f"  • 最大笔记数: {max_notes}\n\n"
        f"⏳ 启动中..."
    )

    try:
        from datetime import datetime

        # 构建命令（使用新的小红书首页刷取脚本）
        script_path = Path(__file__).parent.parent / "workflows" / "ai_xiaohongshu_homepage.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--mode", "full",
            "--refresh-count", str(refresh_count),
            "--max-notes", str(max_notes)
        ]

        await status_msg.edit_text(
            f"🚀 开始刷小红书推荐\n\n"
            f"📊 配置:\n"
            f"  • 刷新次数: {refresh_count}\n"
            f"  • 最大笔记数: {max_notes}\n\n"
            f"📡 正在采集推荐内容..."
        )

        # 执行采集脚本（设置环境变量禁用缓冲）
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent),
            env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}
        )

        # 保存进程对象，以便 /stop 可以终止它
        user_manager.set_process(user_id, process)

        # 等待完成（添加超时：5分钟）
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        except asyncio.TimeoutError:
            await process.terminate()
            await process.wait()
            await status_msg.edit_text("⚠️ 执行超时（5分钟）\n\n💡 任务可能已完成，请检查报告文件")
            # 尝试读取已生成的报告
            date_str = datetime.now().strftime('%Y-%m-%d')
            report_path = Path(__file__).parent.parent / "output" / "xiaohongshu_homepage" / f"xiaohongshu_homepage_{date_str}_AI报告.md"
            if report_path.exists():
                await status_msg.edit_text(
                    f"⚠️ 执行超时，但发现报告文件\n\n"
                    f"📁 报告已保存: {report_path.name}\n\n"
                    f"请手动查看完整报告"
                )
            return
        except (asyncio.CancelledError, BrokenPipeError, OSError, ProcessLookupError) as e:
            # 进程被终止（可能是用户使用 /stop 命令）
            task_id = user_manager.active_tasks.get(user_id, '')
            if task_id and user_manager.should_stop(task_id):
                await status_msg.edit_text("🛑 任务已停止")
            else:
                await status_msg.edit_text(f"❌ 进程异常终止: {type(e).__name__}")
            return

        stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ''
        stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ''

        # 如果有错误输出，先显示
        if stderr_text:
            await status_msg.edit_text(
                f"⚠️ 执行过程中有警告/错误\n\n"
                f"错误信息:\n{stderr_text[-1000:]}\n\n"
                f"⏳ 正在检查结果..."
            )

        if process.returncode == 0:
            # 查找生成的报告文件
            date_str = datetime.now().strftime('%Y-%m-%d')
            report_path = Path(__file__).parent.parent / "output" / "xiaohongshu_homepage" / f"xiaohongshu_homepage_{date_str}_AI报告.md"

            # 先显示输出信息（方便调试）
            if stdout_text or stderr_text:
                debug_info = ""
                if stderr_text:
                    debug_info += f"stderr:\n{stderr_text[-500:]}\n\n"
                if stdout_text and len(stdout_text) > 2000:
                    debug_info += f"stdout (最后500字符):\n{stdout_text[-500:]}\n\n"

            if report_path.exists():
                # 读取报告内容
                with open(report_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()

                # 发送摘要
                summary_lines = []
                for line in report_content.split('\n')[:50]:  # 前50行
                    summary_lines.append(line)
                    if len('\n'.join(summary_lines)) > 3500:  # Telegram消息长度限制
                        break

                summary = '\n'.join(summary_lines)

                # 构建成功消息
                success_msg = (
                    f"✅ 小红书推荐刷取完成！\n\n"
                    f"📊 采集信息:\n"
                    f"  • 刷新次数: {refresh_count}\n"
                    f"  • 最大笔记数: {max_notes}\n\n"
                )

                # 添加调试信息（如果有）
                if stdout_text or stderr_text:
                    debug_section = ""
                    if stderr_text:
                        debug_section += f"⚠️ 警告信息:\n{stderr_text[-500:]}\n\n"
                    if stdout_text and len(stdout_text) > 2000:
                        debug_section += f"📋 输出摘要:\n{stdout_text[-500:]}\n\n"
                    if len(success_msg) + len(debug_section) < 4000:
                        success_msg += debug_section

                success_msg += f"📝 以下是报告摘要:\n\n{summary}\n\n"
                success_msg += f"📁 完整报告已通过文件发送"

                await status_msg.edit_text(success_msg)

                # 发送完整报告文件
                line_count = len(report_content.split('\n'))
                await update.message.reply_document(
                    document=str(report_path),
                    caption=f"📄 小红书推荐分析报告\n• 刷新次数: {refresh_count}\n• 采集笔记: {line_count} 行",
                    filename=report_path.name
                )
            else:
                await status_msg.edit_text(
                    f"✅ 刷取完成，但未找到报告文件\n\n"
                    f"可能的原因:\n"
                    f"  • 采集失败\n"
                    f"  • AI分析失败\n"
                    f"  • 文件路径错误\n\n"
                    f"请检查控制台日志"
                )
        else:
            error_msg = stderr.decode('utf-8', errors='ignore')[-500:]
            await status_msg.edit_text(
                f"❌ 刷取失败\n\n"
                f"错误信息:\n{error_msg}"
            )

    except FileNotFoundError:
        await status_msg.edit_text(
            f"⚠️ 小红书刷取功能需要额外配置\n\n"
            f"💡 请确保以下文件存在:\n"
            f"  • workflows/ai_xiaohongshu_homepage.py\n"
            f"  • config/cookies.txt (小红书Cookie)"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ 执行出错: {str(e)}")
    finally:
        user_manager.end_task(user_id)


async def btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """按钮回调"""
    query = update.callback_query
    user_id = update.effective_user.id

    if query.data.startswith('mode_'):
        mode = query.data.split('_')[1]
        user_manager.set_mode(user_id, mode)

        mode_names = {
            'simple': '简洁版',
            'knowledge': '知识库版',
            'detailed': '详细版',
            'transcript': '转录版'
        }

        await query.answer()
        await query.edit_message_text(
            f"✅ 模式已切换到: **{mode_names.get(mode, mode).upper()}**\n\n"
            f"现在发送视频链接将使用此模式分析。"
        )


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

    # B站视频处理
    if result['platform'] == 'bilibili' and result['type'] == 'video':
        # 获取用户的分析模式
        user_id = update.effective_user.id
        mode = user_manager.get_mode(user_id)

        # 开始处理
        status_msg = await update.message.reply_text(
            f"📺 识别到B站视频\n"
            f"BV号: {result['id']}\n"
            f"📝 模式: {mode.upper()}\n\n"
            f"📥 正在提取字幕..."
        )

        # 提取字幕
        fetch_result = await summarizer.fetch_subtitle(result['id'])

        if not fetch_result['success']:
            await status_msg.edit_text(f"❌ 字幕提取失败\n\n{fetch_result['error']}")
            return

        await status_msg.edit_text(
            f"✅ 字幕提取成功\n"
            f"标题: {fetch_result['title'][:30]}...\n\n"
            f"🤖 正在AI分析 (模式: {mode.upper()})..."
        )

        # 生成总结（使用用户选择的模式）
        summary = await summarizer.generate_summary(
            fetch_result['srt_path'],
            fetch_result['title'],
            url,
            mode
        )

        # 发送结果
        await status_msg.delete()
        await update.message.reply_text(summary, disable_web_page_preview=True)

    # 小红书笔记处理
    elif result['platform'] == 'xiaohongshu' and result['type'] == 'note':
        status_msg = await update.message.reply_text(
            f"📱 识别到小红书笔记\n"
            f"ID: {result['id']}\n\n"
            f"⏳ 准备分析..."
        )
        await handle_xiaohongshu_note(update, result, status_msg)

    else:
        await update.message.reply_text(
            f"⚠️ 暂不支持的内容类型\n\n"
            f"检测到: {result['platform']} - {result['type']}\n\n"
            f"支持的内容:\n"
            f"• B站视频链接\n"
            f"• 小红书笔记链接"
        )


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

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("mode", cmd_mode))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("scrape_bilibili", cmd_scrape_bilibili))
    application.add_handler(CommandHandler("scrape_xiaohongshu", cmd_scrape_xiaohongshu))
    application.add_handler(CallbackQueryHandler(btn_callback))
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
