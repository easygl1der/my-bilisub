#!/usr/bin/env python3
"""
第二大脑 - 命令行入口

使用示例:
    # 添加博主
    python -m second_brain.cli add bilibili 123456789 "博主名称" --category 科技

    # 列出博主
    python -m second_brain.cli list

    # 检查新视频（单次）
    python -m second_brain.cli check

    # 持续监控
    python -m second_brain.cli monitor

    # 查看统计
    python -m second_brain.cli stats
"""

import sys
import argparse
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description="第二大脑 - 视频监控与新闻分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # ==================== add 命令 ====================
    add_parser = subparsers.add_parser('add', help='添加监控博主')
    add_parser.add_argument('platform', choices=['bilibili', 'xiaohongshu', 'youtube'],
                           help='平台')
    add_parser.add_argument('uid', help='博主UID/用户名')
    add_parser.add_argument('name', help='博主名称')
    add_parser.add_argument('--category', help='内容分类', default='')

    # ==================== list 命令 ====================
    subparsers.add_parser('list', help='列出所有博主')

    # ==================== check 命令 ====================
    check_parser = subparsers.add_parser('check', help='检查新视频（单次）')
    check_parser.add_argument('--config', help='配置文件路径', default='config/second_brain.yaml')

    # ==================== monitor 命令 ====================
    monitor_parser = subparsers.add_parser('monitor', help='持续监控')
    monitor_parser.add_argument('--config', help='配置文件路径', default='config/second_brain.yaml')
    monitor_parser.add_argument('--interval', type=int, help='检查间隔（秒）')

    # ==================== stats 命令 ====================
    subparsers.add_parser('stats', help='显示统计信息')

    # ==================== 解析参数 ====================
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 导入模块（放在这里避免循环导入）
    from second_brain.config import Config
    from second_brain.database import Database
    from second_brain.monitor import (
        add_creator_command,
        list_creators_command,
        check_once_command,
        monitor_command
    )

    # 初始化
    config = Config(args.config) if hasattr(args, 'config') else Config()
    db = Database(config.database_path)

    try:
        # 执行命令
        if args.command == 'add':
            add_creator_command(db, args.platform, args.uid, args.name, args.category)

        elif args.command == 'list':
            list_creators_command(db)

        elif args.command == 'check':
            check_once_command(db, config)

        elif args.command == 'monitor':
            if args.interval:
                config.config['monitor']['check_interval'] = args.interval
            monitor_command(db, config)

        elif args.command == 'stats':
            stats = db.get_stats()
            print(f"\n📊 系统统计\n")
            print(f"{'项目':<20} {'数量'}")
            print("-" * 30)
            print(f"{'监控博主':<20} {stats.get('active_creators', 0)}")
            print(f"{'总视频数':<20} {stats.get('total_videos', 0)}")
            print(f"{'今日视频':<20} {stats.get('today_videos', 0)}")
            print(f"{'已分析视频':<20} {stats.get('analyzed_videos', 0)}")
            print(f"{'待分析视频':<20} {stats.get('pending_analysis', 0)}")
            print(f"{'今日新闻':<20} {stats.get('today_news', 0)}")

    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断")
        return 1
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    # 支持 python -m second_brain.cli 方式调用
    if __name__ == '__main__':
        sys.exit(main())
