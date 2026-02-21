#!/usr/bin/env python3
"""
小红书AI教授监控系统 - MediaCrawler集成版

这个脚本可以直接分析 MediaCrawler 爬取的小红书数据，
自动识别真实教授账号和中介假信息。

使用方法:
    # 1. 先用 MediaCrawler 爬取数据
    cd MediaCrawler
    python main.py

    # 2. 分析爬取的数据
    python xhs_professor_monitor_integration.py --analyze-data

    # 3. 监控指定用户
    python xhs_professor_monitor_integration.py --add-user "用户主页URL"

    # 4. 查看报告
    python xhs_professor_monitor_integration.py --report
"""

import os
import sys
import json
import csv
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
import sqlite3

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

# 中介检测规则
AGENCY_RULES = {
    'name_patterns': {
        'suspicious': [
            r'\d{4,}$',           # 以4位以上数字结尾
            r'(wx|v|微信|vx|加微)', # 含微信相关
            r'(留学|申请|中介|机构|保录取|内推)',  # 含中介词
        ],
        'safe': [
            r'^[\u4e00-\u9fa5]{2,4}$',  # 纯中文2-4字（可能是真名）
            r'[教授|Prof|Dr\.|博士|PI]',  # 含学术头衔
        ]
    },
    'bio_signals': {
        'agency': [
            'dd', '滴滴', '私信', '加v', '加微', 'vx', '微信',
            '留学', '申请', '中介', '机构', '保offer', '内推',
            '名额有限', '最后', '抓紧', '即将截止',
        ],
        'professor': [
            '教授', '副教授', '助理教授', 'PI', '实验室', 'Lab',
            'University', '大学', '学院', '研究所', '博导',
        ]
    },
    'content_signals': {
        'agency_high': [
            'dd', '滴滴', '滴滴我', '私信了解', '加v咨询',
            '保录取', '保offer', '代申请',
        ],
        'agency_medium': [
            '内推', '推荐', '名额有限', 'funding充足', '人很nice',
            '招人', '招生', '招收', '有偿', '付费',
        ],
        'professor_high': [
            '论文', 'paper', 'research', '顶会', '期刊',
            'CVPR', 'ICCV', 'NeurIPS', 'ICML', 'AAAI',
            '投稿', '发表', '接收', '实验室', '课题组',
        ]
    }
}

# ==================== 数据结构 ====================

@dataclass
class AccountAnalysis:
    """账号分析结果"""
    user_id: str
    name: str
    description: str = ""
    followers_count: int = 0
    posts_count: int = 0

    # 评分
    credibility_score: float = 50.0  # 0-100
    agency_score: float = 0.0        # 0-100，越高越像中介
    professor_score: float = 0.0     # 0-100，越高越像教授

    # 判断
    is_professor: bool = False
    is_agency: bool = False
    confidence: str = "low"  # low, medium, high

    # 详情
    reasons: List[str] = field(default_factory=list)
    suspicious_signals: List[str] = field(default_factory=list)
    professor_signals: List[str] = field(default_factory=list)


# ==================== 分析器 ====================

class XHSAccountAnalyzer:
    """小红书账号分析器"""

    def __init__(self):
        self.rules = AGENCY_RULES

    def analyze_from_mc_data(self, data_dir: str = None) -> Dict:
        """分析 MediaCrawler 爬取的数据"""
        if data_dir is None:
            # 从 platforms/xiaohongshu/ 回到父目录的 MediaCrawler/data/xhs
            data_dir = str(Path(__file__).parent.parent.parent / "MediaCrawler" / "data" / "xhs")
        data_path = Path(data_dir)

        if not data_path.exists():
            return {'accounts': [], 'posts': [], 'errors': ['数据目录不存在']}

        accounts = {}
        posts = []

        # 遍历JSON文件
        for json_file in data_path.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 处理不同的数据格式
                items = data if isinstance(data, list) else [data]

                for item in items:
                    # 提取帖子信息
                    post = self._extract_post(item)
                    if post:
                        posts.append(post)

                        # 聚合账号信息
                        user_id = post.get('user_id', '')
                        if user_id and user_id not in accounts:
                            accounts[user_id] = {
                                'user_id': user_id,
                                'name': post.get('author', ''),
                                'description': post.get('user_desc', ''),
                                'posts': []
                            }
                        if user_id in accounts:
                            accounts[user_id]['posts'].append(post)

            except Exception as e:
                pass

        # 分析每个账号
        analyzed_accounts = []
        for user_id, account_data in accounts.items():
            analysis = self.analyze_account(
                user_id=user_id,
                name=account_data['name'],
                description=account_data['description'],
                posts=account_data['posts']
            )
            analyzed_accounts.append(analysis)

        return {
            'accounts': analyzed_accounts,
            'posts': posts,
            'total': len(analyzed_accounts)
        }

    def _extract_post(self, item: Dict) -> Optional[Dict]:
        """从 MediaCrawler 数据中提取帖子信息"""
        # MediaCrawler 可能的字段名
        title = (
            item.get('title') or item.get('note_title') or
            item.get('share_note_title') or ''
        )
        desc = (
            item.get('desc') or item.get('note_desc') or
            item.get('share_note_desc') or item.get('text') or ''
        )

        if not title and not desc:
            return None

        return {
            'post_id': item.get('note_id') or item.get('id') or '',
            'user_id': item.get('user_id') or '',
            'author': item.get('nickname') or item.get('author_name') or '',
            'user_desc': item.get('user_desc') or item.get('user_sign') or '',
            'title': title,
            'desc': desc,
            'likes': item.get('liked_count') or item.get('like_count') or 0,
            'comments': item.get('comment_count') or item.get('comments') or 0,
        }

    def analyze_account(self, user_id: str, name: str, description: str = "",
                       posts: List[Dict] = None) -> AccountAnalysis:
        """分析单个账号"""
        analysis = AccountAnalysis(
            user_id=user_id,
            name=name,
            description=description,
            posts_count=len(posts) if posts else 0
        )

        if not posts:
            posts = []

        # 1. 分析名字
        name_score, name_reasons = self._analyze_name(name)
        analysis.agency_score += name_score['agency']
        analysis.professor_score += name_score['professor']
        analysis.reasons.extend(name_reasons)

        # 2. 分析简介
        bio_score, bio_reasons, bio_suspicious = self._analyze_bio(description)
        analysis.agency_score += bio_score['agency']
        analysis.professor_score += bio_score['professor']
        analysis.reasons.extend(bio_reasons)
        analysis.suspicious_signals.extend(bio_suspicious)

        # 3. 分析发帖内容
        post_score, post_reasons, post_suspicious = self._analyze_posts(posts)
        analysis.agency_score += post_score['agency']
        analysis.professor_score += post_score['professor']
        analysis.reasons.extend(post_reasons)
        analysis.suspicious_signals.extend(post_suspicious)

        # 4. 计算综合可信度
        # 基础分50，教授加分，中介扣分
        analysis.credibility_score = 50 + analysis.professor_score - analysis.agency_score
        analysis.credibility_score = max(0, min(100, analysis.credibility_score))

        # 5. 判断类型
        if analysis.professor_score >= 30 and analysis.agency_score <= 20:
            analysis.is_professor = True
            analysis.confidence = "high" if analysis.credibility_score >= 70 else "medium"

        if analysis.agency_score >= 40:
            analysis.is_agency = True
            analysis.credibility_score = max(0, analysis.credibility_score - 30)

        # 高度可疑：发了多个不同老师的招生信息
        mentioned_professors = self._extract_mentioned_professors(posts)
        if len(mentioned_professors) >= 3:
            analysis.is_agency = True
            analysis.suspicious_signals.append(f"提及{len(mentioned_professors)}位不同的老师")

        return analysis

    def _analyze_name(self, name: str) -> Tuple[Dict, List[str]]:
        """分析账号名"""
        scores = {'agency': 0, 'professor': 0}
        reasons = []

        # 可疑模式
        for pattern in self.rules['name_patterns']['suspicious']:
            if re.search(pattern, name, re.I):
                scores['agency'] += 20
                reasons.append(f"名字含可疑模式: {pattern}")

        # 安全模式
        for pattern in self.rules['name_patterns']['safe']:
            if re.search(pattern, name, re.I):
                scores['professor'] += 15
                reasons.append(f"名字含学术特征: {pattern}")

        return scores, reasons

    def _analyze_bio(self, bio: str) -> Tuple[Dict, List[str], List[str]]:
        """分析简介"""
        scores = {'agency': 0, 'professor': 0}
        reasons = []
        suspicious = []

        if not bio:
            return scores, reasons, suspicious

        bio_lower = bio.lower()

        # 中介信号
        for signal in self.rules['bio_signals']['agency']:
            if signal in bio_lower:
                scores['agency'] += 10
                suspicious.append(f"简介含中介词: {signal}")

        # 教授信号
        for signal in self.rules['bio_signals']['professor']:
            if signal in bio:
                scores['professor'] += 15
                reasons.append(f"简介含学术身份: {signal}")

        return scores, reasons, suspicious

    def _analyze_posts(self, posts: List[Dict]) -> Tuple[Dict, List[str], List[str]]:
        """分析发帖内容"""
        scores = {'agency': 0, 'professor': 0}
        reasons = []
        suspicious = []

        if not posts:
            return scores, reasons, suspicious

        for post in posts:
            content = (post.get('title', '') + ' ' + post.get('desc', '')).lower()

            # 高权重中介信号
            for signal in self.rules['content_signals']['agency_high']:
                if signal in content:
                    scores['agency'] += 15
                    suspicious.append(f"内容含中介词: {signal}")
                    break

            # 中等权重中介信号
            for signal in self.rules['content_signals']['agency_medium']:
                if signal in content:
                    scores['agency'] += 5
                    break

            # 教授信号
            for signal in self.rules['content_signals']['professor_high']:
                if signal.lower() in content:
                    scores['professor'] += 10
                    reasons.append(f"内容含学术词: {signal}")
                    break

        return scores, reasons, suspicious

    def _extract_mentioned_professors(self, posts: List[Dict]) -> List[str]:
        """提取帖子中提及的教授名字"""
        mentioned = set()

        for post in posts:
            content = post.get('title', '') + ' ' + post.get('desc', '')
            # 匹配 "XX教授"、"XX老师"、"XX导师"
            matches = re.findall(r'([\u4e00-\u9fa5]{2,4})(?:教授|老师|导师)', content)
            mentioned.update(matches)

        return list(mentioned)


# ==================== 数据库管理 ====================

class MonitorDatabase:
    """监控数据库"""

    def __init__(self, db_path: str = "data/professor_monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """初始化表"""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                name TEXT,
                description TEXT,
                credibility_score REAL DEFAULT 50,
                agency_score REAL DEFAULT 0,
                professor_score REAL DEFAULT 0,
                is_professor INTEGER DEFAULT 0,
                is_agency INTEGER DEFAULT 0,
                confidence TEXT DEFAULT 'low',
                reasons TEXT,
                suspicious_signals TEXT,
                posts_count INTEGER DEFAULT 0,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE,
                user_id TEXT,
                title TEXT,
                description TEXT,
                likes INTEGER DEFAULT 0,
                is_recruitment INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES accounts(user_id)
            )
        """)

        self.conn.commit()

    def save_account(self, analysis: AccountAnalysis):
        """保存账号分析"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO accounts
            (user_id, name, description, credibility_score, agency_score, professor_score,
             is_professor, is_agency, confidence, reasons, suspicious_signals, posts_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.user_id, analysis.name, analysis.description,
            analysis.credibility_score, analysis.agency_score, analysis.professor_score,
            int(analysis.is_professor), int(analysis.is_agency), analysis.confidence,
            json.dumps(analysis.reasons, ensure_ascii=False),
            json.dumps(analysis.suspicious_signals, ensure_ascii=False),
            analysis.posts_count
        ))
        self.conn.commit()

    def get_accounts(self, filter_type: str = None) -> List[Dict]:
        """获取账号列表"""
        cursor = self.conn.cursor()

        if filter_type == 'professor':
            cursor.execute("SELECT * FROM accounts WHERE is_professor = 1 ORDER BY credibility_score DESC")
        elif filter_type == 'agency':
            cursor.execute("SELECT * FROM accounts WHERE is_agency = 1 ORDER BY credibility_score ASC")
        elif filter_type == 'suspicious':
            cursor.execute("SELECT * FROM accounts WHERE credibility_score < 50 ORDER BY credibility_score ASC")
        else:
            cursor.execute("SELECT * FROM accounts ORDER BY credibility_score DESC")

        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """关闭数据库"""
        self.conn.close()


# ==================== 报告生成 ====================

class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def generate_report(analyses: List[AccountAnalysis], output_path: str = "professor_monitor_report.md"):
        """生成分析报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 小红书教授账号监控报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            # 统计
            professors = [a for a in analyses if a.is_professor]
            agencies = [a for a in analyses if a.is_agency]
            suspicious = [a for a in analyses if a.credibility_score < 50 and not a.is_agency]

            f.write("## 📊 统计概览\n\n")
            f.write(f"- 总分析账号: {len(analyses)}\n")
            f.write(f"- ✅ 疑似真实教授: {len(professors)}\n")
            f.write(f"- ⚠️ 疑似中介账号: {len(agencies)}\n")
            f.write(f"- ❓ 可疑账号: {len(suspicious)}\n\n")

            # 真实教授列表
            if professors:
                f.write("## ✅ 疑似真实教授账号\n\n")
                for a in sorted(professors, key=lambda x: x.credibility_score, reverse=True):
                    f.write(f"### {a.name} (可信度: {a.credibility_score:.0f}/100)\n\n")
                    f.write(f"- **用户ID**: {a.user_id}\n")
                    f.write(f"- **置信度**: {a.confidence}\n")
                    if a.description:
                        f.write(f"- **简介**: {a.description[:100]}...\n")
                    if a.reasons:
                        f.write(f"- **判断依据**: {', '.join(a.reasons[:3])}\n")
                    f.write(f"- **发帖数**: {a.posts_count}\n\n")

            # 中介列表
            if agencies:
                f.write("## ⚠️ 疑似中介账号\n\n")
                for a in sorted(agencies, key=lambda x: a.credibility_score):
                    f.write(f"### {a.name} (可信度: {a.credibility_score:.0f}/100)\n\n")
                    f.write(f"- **用户ID**: {a.user_id}\n")
                    if a.suspicious_signals:
                        f.write(f"- **可疑信号**: {', '.join(a.suspicious_signals[:5])}\n")
                    f.write(f"- **发帖数**: {a.posts_count}\n\n")

            # 可疑账号
            if suspicious:
                f.write("## ❓ 需要进一步确认的账号\n\n")
                for a in sorted(suspicious, key=lambda x: x.credibility_score)[:10]:
                    f.write(f"- {a.name} (可信度: {a.credibility_score:.0f}/100)\n")

        print(f"📄 报告已保存: {output_path}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书AI教授监控系统 - MediaCrawler集成版",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--analyze-data', action='store_true',
                       help='分析 MediaCrawler 爬取的数据')
    parser.add_argument('--data-dir', default='MediaCrawler/data/xhs',
                       help='MediaCrawler 数据目录')

    parser.add_argument('--add-user', metavar='USER_ID',
                       help='添加监控用户')
    parser.add_argument('--name', metavar='NAME',
                       help='用户名称')
    parser.add_argument('--bio', metavar='BIO',
                       help='用户简介')

    parser.add_argument('--report', action='store_true',
                       help='生成分析报告')

    parser.add_argument('--list', nargs='?', const='all',
                       choices=['all', 'professor', 'agency', 'suspicious'],
                       help='列出已分析的账号')

    parser.add_argument('--output', default='professor_monitor_report.md',
                       help='报告输出文件')

    args = parser.parse_args()

    analyzer = XHSAccountAnalyzer()
    db = MonitorDatabase()

    # 分析 MediaCrawler 数据
    if args.analyze_data:
        print("\n" + "="*60)
        print("🔍 分析 MediaCrawler 数据")
        print("="*60)

        result = analyzer.analyze_from_mc_data(args.data_dir)

        if not result['accounts']:
            print(f"\n❓ 未找到可分析的数据")
            print(f"   请确认 MediaCrawler 已正确爬取数据到 {args.data_dir}")
            return

        print(f"\n✅ 找到 {result['total']} 个账号")

        for analysis in result['accounts']:
            db.save_account(analysis)
            status = "✅教授" if analysis.is_professor else ("⚠️中介" if analysis.is_agency else "❓未知")
            print(f"   [{status}] {analysis.name}: {analysis.credibility_score:.0f}/100")

        # 生成报告
        ReportGenerator.generate_report(result['accounts'], args.output)

        return

    # 生成报告
    if args.report:
        accounts = db.get_accounts()
        analyses = []
        for acc in accounts:
            analysis = AccountAnalysis(
                user_id=acc['user_id'],
                name=acc['name'],
                description=acc['description'],
                credibility_score=acc['credibility_score'],
                agency_score=acc['agency_score'],
                professor_score=acc['professor_score'],
                is_professor=bool(acc['is_professor']),
                is_agency=bool(acc['is_agency']),
                confidence=acc['confidence'],
                posts_count=acc['posts_count']
            )
            if acc['reasons']:
                analysis.reasons = json.loads(acc['reasons'])
            if acc['suspicious_signals']:
                analysis.suspicious_signals = json.loads(acc['suspicious_signals'])
            analyses.append(analysis)

        ReportGenerator.generate_report(analyses, args.output)
        return

    # 列出账号
    if args.list:
        filter_type = 'professor' if args.list == 'professor' else args.list
        accounts = db.get_accounts(filter_type)

        print(f"\n📋 账号列表 ({len(accounts)} 个)\n")

        for acc in accounts:
            status = "✅" if acc['is_professor'] else ("⚠️" if acc['is_agency'] else "❓")
            print(f"  {status} {acc['name']}: {acc['credibility_score']:.0f}/100 "
                  f"(教授:{acc['professor_score']:.0f}, 中介:{acc['agency_score']:.0f})")

        return

    # 手动添加用户
    if args.add_user:
        analysis = analyzer.analyze_account(
            user_id=args.add_user,
            name=args.name or "未知用户",
            description=args.bio or ""
        )
        db.save_account(analysis)

        print(f"\n📊 分析结果:")
        print(f"   名称: {analysis.name}")
        print(f"   可信度: {analysis.credibility_score:.0f}/100")
        print(f"   判定: {'✅教授' if analysis.is_professor else ('⚠️中介' if analysis.is_agency else '❓未知')}")
        if analysis.reasons:
            print(f"   依据: {', '.join(analysis.reasons[:3])}")
        return

    # 显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
