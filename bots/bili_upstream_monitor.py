#!/usr/bin/env python3
"""
B站UP主监控系统

功能：
- 定时监控指定UP主的新视频
- 自动提取字幕并生成AI摘要
- 通过Telegram发送通知
"""

import sys
import json
import asyncio
import argparse
import re
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 导入现有模块
from second_brain.monitor import BilibiliAPI, VideoMonitor
from second_brain.database import Database
from bots.telegram_notifier import TelegramNotifier


class BiliUpstreamMonitor:
    """B站UP主监控器"""

    def __init__(self, config_path: str = None, db_path: str = None):
        """
        初始化监控器

        Args:
            config_path: 配置文件路径 (默认: config/bili_monitor.json)
            db_path: 数据库路径 (默认: data/second_brain.db)
        """
        # 加载配置
        self.config = self._load_config(config_path)

        # 初始化数据库
        self.db = Database(db_path or self.config.get('database.path', 'data/second_brain.db'))

        # 初始化通知器
        if self.config.get('notifications.enabled', True):
            self.notifier = TelegramNotifier()
        else:
            self.notifier = None

        # 监控间隔 (秒)
        self.check_interval = self.config.get('monitor.interval', 300)  # 默认5分钟

        # 分析配置
        self.auto_analyze = self.config.get('analysis.auto_analyze', True)
        self.analysis_model = self.config.get('analysis.model', 'flash-lite')
        self.analysis_mode = self.config.get('analysis.mode', 'knowledge')

        # 初始化监控器
        self.monitor = VideoMonitor(self.db)

    def _load_config(self, config_path: str = None) -> dict:
        """加载配置文件"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "bili_monitor.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                f"请创建配置文件或使用 --init 命令初始化"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_creators(self) -> list:
        """
        从配置文件加载UP主列表

        Returns:
            UP主列表
        """
        creators_list = self.config.get('creators', [])

        # 添加到数据库（如果不存在）
        creators = []
        for creator_info in creators_list:
            if not creator_info.get('enabled', True):
                continue

            # 检查是否已在数据库中
            existing = self.db.get_creator('bilibili', creator_info['uid'])
            if existing:
                creator_info['db_id'] = existing['id']
            else:
                # 获取UP主信息
                api_info = BilibiliAPI.get_user_info(creator_info['uid'])
                if api_info:
                    creator_info['db_id'] = self.db.add_creator(
                        platform='bilibili',
                        uid=creator_info['uid'],
                        name=api_info.get('name', creator_info.get('name', '')),
                        category=creator_info.get('category', ''),
                        avatar_url=api_info.get('avatar'),
                        fans_count=api_info.get('fans', 0),
                        enabled=True
                    )
                else:
                    # API失败，使用配置文件中的信息
                    creator_info['db_id'] = self.db.add_creator(
                        platform='bilibili',
                        uid=creator_info['uid'],
                        name=creator_info.get('name', ''),
                        category=creator_info.get('category', ''),
                        enabled=True
                    )

            # 添加 platform 字段
            creator_info['platform'] = 'bilibili'
            creators.append(creator_info)

        return creators

    async def analyze_video(self, video: dict, creator: dict) -> dict:
        """
        分析单个视频

        Args:
            video: 视频信息
            creator: UP主信息

        Returns:
            分析结果
        """
        print(f"\n{'='*60}")
        print(f"🤖 开始分析视频")
        print(f"{'='*60}")
        print(f"📺 UP主: {creator['name']}")
        print(f"🎬 视频: {video['title'][:50]}...")
        print(f"🔗 链接: {video['url']}")

        # 动态导入 auto_bili_workflow
        try:
            from workflows.auto_bili_workflow import process_single_video

            # 调用工作流处理视频
            success = await process_single_video(
                video['url'],
                model=self.analysis_model
            )

            result = {
                'success': success,
                'video_id': video['video_id'],
                'video_url': video['url'],
                'title': video['title'],
            }

            # 更新分析状态
            if success:
                self.db.update_analysis_status(
                    video['db_id'],
                    status='completed',
                    model=self.analysis_model,
                    mode=self.analysis_mode
                )
            else:
                self.db.update_analysis_status(
                    video['db_id'],
                    status='failed',
                    error_message='Analysis failed'
                )

            return result

        except Exception as e:
            print(f"❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'video_id': video['video_id'],
                'error': str(e)
            }

    def send_notification(self, video: dict, creator: dict, summary: dict = None):
        """
        发送通知

        Args:
            video: 视频信息
            creator: UP主信息
            summary: 分析摘要 (可选)
        """
        if not self.notifier:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 构建通知消息
        message = f"""🔔 *B站UP主新视频通知*

📅 时间: `{timestamp}`

👤 *UP主*: {creator['name']}
📂 *分类*: {creator.get('category', 'N/A')}
🎬 *视频*: {video['title']}

🔗 [观看视频]({video['url']})
"""

        # 如果有分析摘要，添加到通知
        if summary and summary.get('success'):
            # 尝试读取生成的摘要文件
            try:
                subtitle_dir = Path(__file__).parent.parent / "output" / "subtitles" / re.sub(r'[<>:"/\\|?*]', '_', creator['name'])
                summary_files = list(subtitle_dir.glob("*_AI总结.md"))
                if summary_files:
                    with open(summary_files[-1], 'r', encoding='utf-8') as f:
                        summary_content = f.read()

                    # 提取摘要部分（跳过标题）
                    lines = []
                    in_summary = False
                    for line in summary_content.split('\n'):
                        if '视频大意' in line or '核心观点' in line or '摘要' in line:
                            in_summary = True
                        if in_summary:
                            lines.append(line)
                            if len(lines) > 10:  # 限制行数
                                break

                    summary_text = '\n'.join(lines)
                    if len(summary_text) > 300:
                        summary_text = summary_text[:300] + '...'

                    message += f"\n📝 *AI摘要*:\n{summary_text}"
            except Exception as e:
                print(f"⚠️ 读取摘要文件失败: {e}")

        # 发送通知
        self.notifier.send_message(message, parse_mode="Markdown")
        print(f"✅ 通知已发送")

    async def on_new_videos(self, new_videos: list, creators: list):
        """
        新视频回调处理

        Args:
            new_videos: 新视频列表
            creators: UP主列表
        """
        if not new_videos:
            return

        print(f"\n{'='*60}")
        print(f"🎉 发现 {len(new_videos)} 个新视频！")
        print(f"{'='*60}")

        for video in new_videos:
            creator = next((c for c in creators if c.get('db_id') == video.get('creator_id')), None)
            if not creator:
                print(f"⚠️ 未找到UP主信息: {video}")
                continue

            # 创建分析状态
            self.db.create_analysis_status(video['id'], status='pending')

            # 自动分析
            if self.auto_analyze:
                try:
                    result = await self.analyze_video(video, creator)

                    # 发送通知
                    self.send_notification(video, creator, result)

                except Exception as e:
                    print(f"❌ 处理视频失败: {e}")
                    # 即使处理失败，也发送通知
                    self.send_notification(video, creator)
            else:
                # 不自动分析，只发送通知
                self.send_notification(video, creator)

    def run_once(self):
        """运行一次检查"""
        print(f"\n{'='*70}")
        print(f"🔍 B站UP主监控系统")
        print(f"{'='*70}")

        # 加载UP主列表
        creators = self.load_creators()
        if not creators:
            print("❌ 没有启用的UP主，请检查配置文件")
            return

        print(f"📺 监控UP主: {len(creators)} 个")
        for creator in creators:
            print(f"  • {creator['name']} ({creator['uid']})")

        # 运行检查
        stats = self.monitor.run_once(creators)

        # 获取新视频并处理
        new_videos = self.db.get_unanalyzed_videos(limit=100)
        if new_videos:
            # 过滤出最近的新视频（10分钟内）
            import time
            recent_videos = [v for v in new_videos
                           if v.get('published_at') and
                           (datetime.now() - datetime.fromisoformat(v['published_at'])).total_seconds() < 600]

            if recent_videos:
                # 异步处理
                asyncio.run(self.on_new_videos(recent_videos, creators))

        print(f"\n📊 统计信息:")
        print(f"  • 检查UP主: {stats['total_creators']} 个")
        print(f"  • 新增视频: {stats['new_videos']} 个")
        print(f"  • 耗时: {stats['elapsed_time']:.1f} 秒")

    def run_loop(self, max_iterations: int = None):
        """
        持续监控循环

        Args:
            max_iterations: 最大迭代次数 (None=无限)
        """
        # 加载UP主列表
        creators = self.load_creators()
        if not creators:
            print("❌ 没有启用的UP主，请检查配置文件")
            return

        # 定义回调
        def callback(new_videos):
            # 只处理最近的新视频
            if new_videos:
                recent_videos = [v for v in new_videos
                               if v.get('published_at') and
                               (datetime.now() - datetime.fromisoformat(v['published_at'])).total_seconds() < 600]
                if recent_videos:
                    asyncio.run(self.on_new_videos(recent_videos, creators))

        # 启动监控循环
        self.monitor.run_loop(
            creators=creators,
            interval=self.check_interval,
            callback=callback,
            max_iterations=max_iterations
        )


def init_config(config_path: str = None):
    """
    初始化配置文件

    Args:
        config_path: 配置文件路径 (默认: config/bili_monitor.json)
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "bili_monitor.json"
    else:
        config_path = Path(config_path)

    # 默认配置
    default_config = {
        "creators": [
            {
                "uid": "123456789",  # 替换为实际UID
                "name": "示例UP主",
                "category": "新闻",
                "enabled": True
            }
        ],
        "monitor": {
            "interval": 300,  # 5分钟
            "check_limit": 50,
            "timeout": 15
        },
        "analysis": {
            "auto_analyze": True,
            "model": "flash-lite",  # flash, flash-lite, pro
            "mode": "knowledge",  # simple, knowledge, detailed
            "fallback_enabled": True
        },
        "notifications": {
            "enabled": True,
            "telegram": {
                "send_summary": True,
                "summary_length": 300,
                "send_full_report": False
            }
        },
        "database": {
            "path": "data/second_brain.db"
        }
    }

    # 保存配置
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)

    print(f"✅ 配置文件已创建: {config_path}")
    print(f"📝 请编辑配置文件，添加要监控的UP主信息")


def main():
    parser = argparse.ArgumentParser(
        description="B站UP主监控系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 初始化配置文件
  python bots/bili_upstream_monitor.py --init

  # 单次检查
  python bots/bili_upstream_monitor.py --once

  # 持续监控 (默认5分钟间隔)
  python bots/bili_upstream_monitor.py --loop

  # 指定监控间隔为10分钟
  python bots/bili_upstream_monitor.py --loop --interval 600

  # 自定义配置文件
  python bots/bili_upstream_monitor.py --config my_config.json --loop
        """
    )

    parser.add_argument("--init", action="store_true",
                       help="初始化配置文件")
    parser.add_argument("--config", "-c",
                       help="配置文件路径")
    parser.add_argument("--once", action="store_true",
                       help="运行一次检查")
    parser.add_argument("--loop", action="store_true",
                       help="持续监控")
    parser.add_argument("--interval", "-i", type=int,
                       help="检查间隔 (秒)")
    parser.add_argument("--max-iterations", type=int,
                       help="最大迭代次数")

    args = parser.parse_args()

    # 初始化配置
    if args.init:
        init_config(args.config)
        return 0

    # 运行监控
    try:
        monitor = BiliUpstreamMonitor(config_path=args.config)

        if args.once:
            monitor.run_once()
        elif args.loop:
            if args.interval:
                monitor.check_interval = args.interval
            monitor.run_loop(max_iterations=args.max_iterations)
        else:
            parser.print_help()
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
