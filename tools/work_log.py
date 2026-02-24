#!/usr/bin/env python3
"""
开发工作日志记录工具

用于记录开发过程中的变更，包括功能添加、bug修复、重构等
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_DIR = Path(__file__).parent.parent
LOG_FILE = PROJECT_DIR / "logs" / "work_log.json"
LOG_DIR = LOG_FILE.parent


class WorkLog:
    """工作日志管理类"""

    CHANGE_TYPES = ['feature', 'fix', 'refactor', 'docs', 'test', 'chore']

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.entries = self._load_entries()

    def _load_entries(self) -> List[Dict]:
        """加载日志条目"""
        if not LOG_FILE.exists():
            return []
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  加载日志失败: {e}")
            return []

    def _save_entries(self):
        """保存日志条目"""
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存日志失败: {e}")

    def add_entry(self, change_type: str, description: str, files: List[str] = None,
                  details: str = None, tags: List[str] = None):
        """添加日志条目"""
        if change_type not in self.CHANGE_TYPES:
            print(f"⚠️  无效的变更类型，可选: {', '.join(self.CHANGE_TYPES)}")
            return False

        entry = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S'),
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'change_type': change_type,
            'description': description,
            'files': files or [],
            'details': details or '',
            'tags': tags or []
        }

        self.entries.insert(0, entry)  # 新记录在最前面
        self._save_entries()
        print(f"✅ 日志已添加 (ID: {entry['id']})")
        return True

    def list_entries(self, limit: int = None, change_type: str = None,
                     date: str = None, tag: str = None):
        """列出日志条目"""
        entries = self.entries.copy()

        # 筛选
        if change_type:
            entries = [e for e in entries if e['change_type'] == change_type]
        if date:
            entries = [e for e in entries if e['date'] == date]
        if tag:
            entries = [e for e in entries if tag in e['tags']]

        if limit:
            entries = entries[:limit]

        if not entries:
            print("📭 没有找到日志记录")
            return

        print("\n" + "=" * 80)
        print(f"  工作日志 (共 {len(entries)} 条)")
        print("=" * 80 + "\n")

        for entry in entries:
            self._print_entry(entry)

    def _print_entry(self, entry: Dict):
        """打印单条日志"""
        type_icons = {
            'feature': '✨',
            'fix': '🐛',
            'refactor': '♻️',
            'docs': '📝',
            'test': '🧪',
            'chore': '🔧'
        }
        icon = type_icons.get(entry['change_type'], '📌')

        print(f"{icon} [{entry['date']} {entry['time']}] {entry['description']}")
        print(f"   类型: {entry['change_type']}")
        print(f"   ID: {entry['id']}")

        if entry['files']:
            print(f"   文件: {', '.join(entry['files'])}")

        if entry['tags']:
            print(f"   标签: {', '.join(entry['tags'])}")

        if entry['details']:
            print(f"   详情: {entry['details']}")

        print()

    def export_markdown(self, output_file: str = None):
        """导出为 Markdown 格式"""
        if not output_file:
            output_file = PROJECT_DIR / "logs" / "work_log.md"

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        type_names = {
            'feature': '新功能',
            'fix': 'Bug修复',
            'refactor': '重构',
            'docs': '文档',
            'test': '测试',
            'chore': '杂项'
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 开发工作日志\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            # 按日期分组
            date_groups = {}
            for entry in self.entries:
                date = entry['date']
                if date not in date_groups:
                    date_groups[date] = []
                date_groups[date].append(entry)

            # 写入
            for date in sorted(date_groups.keys(), reverse=True):
                f.write(f"## {date}\n\n")
                for entry in date_groups[date]:
                    type_name = type_names.get(entry['change_type'], entry['change_type'])
                    f.write(f"### [{entry['change_type']}] {entry['description']}\n\n")
                    f.write(f"- **时间**: {entry['time']}\n")
                    f.write(f"- **类型**: {type_name}\n")
                    f.write(f"- **ID**: {entry['id']}\n")

                    if entry['files']:
                        f.write(f"- **涉及文件**: {', '.join(entry['files'])}\n")

                    if entry['tags']:
                        f.write(f"- **标签**: {', '.join(entry['tags'])}\n")

                    if entry['details']:
                        f.write(f"- **详情**: {entry['details']}\n")

                    f.write("\n---\n\n")

        print(f"✅ 已导出到: {output_path}")

    def search(self, keyword: str):
        """搜索日志"""
        results = [e for e in self.entries
                   if keyword.lower() in e['description'].lower() or
                   keyword.lower() in (e.get('details') or '').lower()]

        if not results:
            print(f"📭 没有找到包含 '{keyword}' 的日志")
            return

        print(f"\n🔍 搜索结果: '{keyword}' (共 {len(results)} 条)\n")
        for entry in results:
            self._print_entry(entry)

    def show_stats(self):
        """显示统计信息"""
        if not self.entries:
            print("📭 暂无日志记录")
            return

        print("\n" + "=" * 60)
        print("  工作日志统计")
        print("=" * 60)

        # 总数
        print(f"\n📊 总记录数: {len(self.entries)}")

        # 按类型统计
        print("\n📌 按类型统计:")
        type_names = {
            'feature': '新功能',
            'fix': 'Bug修复',
            'refactor': '重构',
            'docs': '文档',
            'test': '测试',
            'chore': '杂项'
        }
        type_counts = {}
        for entry in self.entries:
            ct = entry['change_type']
            type_counts[ct] = type_counts.get(ct, 0) + 1

        for ct, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            name = type_names.get(ct, ct)
            print(f"   {name}: {count}")

        # 最近7天
        recent_entries = [e for e in self.entries if self._is_recent(e['date'], days=7)]
        print(f"\n📅 最近7天: {len(recent_entries)} 条")

        # 最早和最新记录
        print(f"\n🕐 最早记录: {self.entries[-1]['date']} {self.entries[-1]['time']}")
        print(f"🕐 最新记录: {self.entries[0]['date']} {self.entries[0]['time']}")

        print()

    def _is_recent(self, date_str: str, days: int) -> bool:
        """检查是否是最近几天的记录"""
        try:
            entry_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            delta = (today - entry_date).days
            return 0 <= delta <= days
        except:
            return False


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='开发工作日志记录工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 添加日志
    add_parser = subparsers.add_parser('add', help='添加日志')
    add_parser.add_argument('-t', '--type', required=True,
                           choices=WorkLog.CHANGE_TYPES,
                           help='变更类型')
    add_parser.add_argument('-d', '--description', required=True,
                           help='描述')
    add_parser.add_argument('-f', '--files', nargs='*',
                           help='涉及的文件')
    add_parser.add_argument('--details',
                           help='详细信息')
    add_parser.add_argument('--tags', nargs='*',
                           help='标签')

    # 列出日志
    list_parser = subparsers.add_parser('list', help='列出日志')
    list_parser.add_argument('-n', '--limit', type=int,
                           help='显示数量')
    list_parser.add_argument('-t', '--type',
                           choices=WorkLog.CHANGE_TYPES,
                           help='按类型筛选')
    list_parser.add_argument('--date',
                           help='按日期筛选 (YYYY-MM-DD)')
    list_parser.add_argument('--tag',
                           help='按标签筛选')

    # 搜索
    search_parser = subparsers.add_parser('search', help='搜索日志')
    search_parser.add_argument('keyword', help='搜索关键词')

    # 导出
    export_parser = subparsers.add_parser('export', help='导出为Markdown')
    export_parser.add_argument('-o', '--output',
                             help='输出文件路径')

    # 统计
    subparsers.add_parser('stats', help='显示统计信息')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    log = WorkLog()

    if args.command == 'add':
        log.add_entry(
            change_type=args.type,
            description=args.description,
            files=args.files,
            details=args.details,
            tags=args.tags
        )

    elif args.command == 'list':
        log.list_entries(
            limit=args.limit,
            change_type=args.type,
            date=args.date,
            tag=args.tag
        )

    elif args.command == 'search':
        log.search(args.keyword)

    elif args.command == 'export':
        log.export_markdown(args.output)

    elif args.command == 'stats':
        log.show_stats()


if __name__ == "__main__":
    main()
