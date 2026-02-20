#!/usr/bin/env python3
"""
小红书AI教授监控系统

功能：
1. 监控指定关键词（AI、教授、招生等）
2. 甄别中介假信息
3. 账号可信度分析（筛选真正教授账号）
4. 实时通知

中介特征检测：
- 文案问题：大量使用"dd"、"私信"、"老师"等中介常用词
- 账号行为：发布多种不同老师的招生信息
- 缺乏个人身份信息

使用方法:
    python xhs_professor_monitor.py --keywords "AI教授,ML招生" --check
    python xhs_professor_monitor.py --analyze-user "用户主页链接"
    python xhs_professor_monitor.py --monitor
"""

import os
import sys
import json
import time
import asyncio
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

# 中介常用关键词（用于检测）
AGENCY_KEYWORDS = {
    'contact': ['dd', '滴滴', '滴滴我', '私信', '私聊', '加v', '加微', '联系',
                'vx', 'VX', 'v信', 'WeChat', 'wx', '微信', '鸽鸽', '大哥'],
    'recruitment': ['招人', '招生', '招收', '名额', '位置', '坑位', '推荐',
                    '内推', '保录取', '保offer', '代申请', '中介', '机构'],
    'professor_ref': ['老师', '大牛', '大佬', '导师', 'PI', '方向很好',
                      '人很nice', '愿意帮学生', 'funding充足'],
    'urgency': ['名额有限', '最后', '抓紧', '即将截止', '马上', '立刻',
                '错过等一年', '手慢无'],
}

# 真实教授的正面信号
PROFESSOR_INDICATORS = {
    'identity': ['教授', '副教授', '助理教授', 'PI', '实验室', 'Lab',
                 'University', '大学', '学院', '研究所'],
    'research': ['论文', 'paper', '研究', 'research', '项目', 'project',
                 '投稿', '发表', '顶会', '期刊', 'CVPR', 'ICCV', 'NeurIPS',
                 'ICML', 'AAAI', 'IJCAI', 'ACL', 'EMNLP'],
    'student': ['招生', '招博', '招硕', '研究生', '博士生', '硕士生',
                'RA', '研究助理', '实习生'],
}

# 可疑的账号特征
SUSPICIOUS_PATTERNS = {
    'random_numbers': re.compile(r'.*\d{4,}$'),  # 以4位以上数字结尾
    'weixin_in_name': re.compile(r'(wx|v|微信|vx)', re.I),  # 名字含微信
    'agency_in_name': re.compile(r'(留学|申请|中介|机构|保录取)', re.I),  # 名字含中介词
}

# ==================== 数据结构 ====================

@dataclass
class AccountProfile:
    """账号画像"""
    user_id: str
    name: str
    description: str = ""
    posts_count: int = 0
    followers_count: int = 0
    posts: List[Dict] = field(default_factory=list)

    # 分析结果
    credibility_score: float = 0.0  # 0-100
    is_professor: bool = False
    is_agency: bool = False
    confidence: str = "low"  # low, medium, high

    # 特征标记
    has_personal_identity: bool = False
    has_research_content: bool = False
    has_multiple_professors: bool = False
    has_contact_info: bool = False
    agency_word_count: int = 0
    professor_word_count: int = 0


@dataclass
class PostAnalysis:
    """帖子分析结果"""
    post_id: str
    title: str
    content: str
    author: str

    # 分类
    is_recruitment: bool = False
    is_professor_post: bool = False
    is_agency_post: bool = False
    confidence: float = 0.0

    # 关键提取
    professor_name: str = ""
    university: str = ""
    research_area: str = ""
    contact_method: str = ""

    # 可疑标记
    suspicious_signals: List[str] = field(default_factory=list)


# ==================== 可信度分析器 ====================

class CredibilityAnalyzer:
    """账号可信度分析器"""

    def __init__(self):
        self.agency_keywords = AGENCY_KEYWORDS
        self.professor_indicators = PROFESSOR_INDICATORS
        self.suspicious_patterns = SUSPICIOUS_PATTERNS

    def analyze_account(self, profile: AccountProfile) -> AccountProfile:
        """分析账号可信度"""
        # 1. 检查账号名
        name_score = self._analyze_name(profile.name)

        # 2. 检查简介
        bio_score, bio_signals = self._analyze_bio(profile.description)

        # 3. 检查发帖模式
        post_score, post_signals = self._analyze_posts(profile.posts)

        # 4. 计算综合得分
        base_score = 50
        profile.credibility_score = min(100, max(0, base_score + name_score + bio_score + post_score))

        # 5. 判断账号类型
        profile.has_personal_identity = bio_signals.get('has_identity', False)
        profile.has_research_content = post_signals.get('has_research', False)
        profile.has_multiple_professors = post_signals.get('multiple_professors', False)
        profile.has_contact_info = bio_signals.get('has_contact', False)
        profile.agency_word_count = post_signals.get('agency_words', 0)
        profile.professor_word_count = post_signals.get('professor_words', 0)

        # 判断是否是教授
        if (profile.has_personal_identity and
            profile.has_research_content and
            not profile.has_multiple_professors and
            profile.credibility_score >= 70):
            profile.is_professor = True
            profile.confidence = "high" if profile.credibility_score >= 85 else "medium"

        # 判断是否是中介
        if (profile.has_multiple_professors or
            profile.agency_word_count >= 3 or
            profile.has_contact_info and not profile.has_personal_identity):
            profile.is_agency = True
            profile.credibility_score = max(0, profile.credibility_score - 40)

        return profile

    def _analyze_name(self, name: str) -> int:
        """分析账号名，返回得分调整"""
        score = 0

        # 可疑模式
        if self.suspicious_patterns['random_numbers'].match(name):
            score -= 20
        if self.suspicious_patterns['weixin_in_name'].search(name):
            score -= 30
        if self.suspicious_patterns['agency_in_name'].search(name):
            score -= 40

        # 正面信号：看起来像真实姓名
        if len(name) >= 2 and len(name) <= 6 and name.isalpha():
            score += 10

        # 包含教授头衔
        if any(ind in name for ind in ['教授', 'Prof', 'Dr.', '博士']):
            score += 15

        return score

    def _analyze_bio(self, bio: str) -> Tuple[int, Dict]:
        """分析简介，返回得分调整和信号"""
        score = 0
        signals = {
            'has_identity': False,
            'has_contact': False,
            'agency_words': 0,
        }

        if not bio:
            return score, signals

        bio_lower = bio.lower()

        # 检查身份信息
        for ind in self.professor_indicators['identity']:
            if ind in bio:
                signals['has_identity'] = True
                score += 20
                break

        # 检查联系方式
        for contact in self.agency_keywords['contact']:
            if contact in bio_lower:
                signals['has_contact'] = True
                signals['agency_words'] += 1
                score -= 15

        # 中介词
        for agency in self.agency_keywords['recruitment']:
            if agency in bio:
                signals['agency_words'] += 1
                score -= 10

        return score, signals

    def _analyze_posts(self, posts: List[Dict]) -> Tuple[int, Dict]:
        """分析发帖模式"""
        score = 0
        signals = {
            'has_research': False,
            'multiple_professors': False,
            'agency_words': 0,
            'professor_words': 0,
        }

        if not posts:
            return score, signals

        # 统计帖子中提到的不同"老师"
        mentioned_professors = set()

        for post in posts:
            content = post.get('title', '') + ' ' + post.get('desc', '')
            content_lower = content.lower()

            # 检测研究内容
            for research in self.professor_indicators['research']:
                if research.lower() in content_lower:
                    signals['has_research'] = True
                    signals['professor_words'] += 1
                    score += 5
                    break

            # 检测中介词
            for agency in self.agency_keywords['recruitment']:
                if agency in content:
                    signals['agency_words'] += 1
                    score -= 3

            # 检测联系方式
            for contact in self.agency_keywords['contact']:
                if contact in content_lower:
                    signals['agency_words'] += 1
                    score -= 5

            # 提取老师名字（简单模式：XXX老师、XXX教授等）
            professor_matches = re.findall(r'([\u4e00-\u9fa5]{2,4})(?:老师|教授|导师)', content)
            mentioned_professors.update(professor_matches)

        # 如果提到了多个不同的老师，很可能是中介
        if len(mentioned_professors) >= 3:
            signals['multiple_professors'] = True
            score -= 30

        return score, signals

    def analyze_post(self, post: Dict) -> PostAnalysis:
        """分析单条帖子"""
        title = post.get('title', '')
        content = post.get('desc', '') or post.get('content', '')
        full_text = title + ' ' + content
        author = post.get('author', '')

        analysis = PostAnalysis(
            post_id=post.get('id', ''),
            title=title,
            content=content,
            author=author
        )

        # 检查是否是招生贴
        for word in self.professor_indicators['student'] + ['招生', '招收']:
            if word in full_text:
                analysis.is_recruitment = True
                break

        # 检查中介特征
        agency_signals = 0
        for category, keywords in self.agency_keywords.items():
            for kw in keywords:
                if kw in full_text.lower():
                    agency_signals += 1
                    analysis.suspicious_signals.append(f"{category}: {kw}")

        # 检查教授特征
        professor_signals = 0
        for category, keywords in self.professor_indicators.items():
            for kw in keywords:
                if kw.lower() in full_text.lower():
                    professor_signals += 1

        # 判断置信度
        if agency_signals >= 3:
            analysis.is_agency_post = True
            analysis.confidence = agency_signals * 0.15
        elif professor_signals >= 2 and agency_signals <= 1:
            analysis.is_professor_post = True
            analysis.confidence = professor_signals * 0.2

        # 提取信息
        analysis.professor_name = self._extract_professor_name(full_text)
        analysis.university = self._extract_university(full_text)
        analysis.research_area = self._extract_research_area(full_text)
        analysis.contact_method = self._extract_contact(full_text)

        return analysis

    def _extract_professor_name(self, text: str) -> str:
        """提取教授名字"""
        # 尝试匹配 "XX教授"、"XX老师" 等
        patterns = [
            r'([\u4e00-\u9fa5]{2,4})教授',
            r'([\u4e00-\u9fa5]{2,4})老师',
            r'([\u4e00-\u9fa5]{2,4})导师',
            r'PI\s*:\s*([A-Z][a-z]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _extract_university(self, text: str) -> str:
        """提取大学信息"""
        # 常见大学模式
        patterns = [
            r'([\u4e00-\u9fa5]{2,6}大学)',
            r'([\u4e00-\u9fa5]{2,6}学院)',
            r'([A-Z][a-z]+\s*[Uu]niversity)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return ""

    def _extract_research_area(self, text: str) -> str:
        """提取研究方向"""
        areas = []
        research_keywords = [
            '机器学习', '深度学习', '计算机视觉', '自然语言处理', 'NLP',
            '强化学习', '推荐系统', '数据挖掘', '知识图谱', '大模型', 'LLM',
            'Machine Learning', 'Deep Learning', 'CV', 'NLP', 'AI'
        ]
        for kw in research_keywords:
            if kw.lower() in text.lower() and kw not in areas:
                areas.append(kw)
        return ', '.join(areas[:3])

    def _extract_contact(self, text: str) -> str:
        """提取联系方式"""
        contacts = []
        for kw in self.agency_keywords['contact']:
            if kw in text.lower():
                contacts.append(kw)
        return ', '.join(contacts[:3])


# ==================== MediaCrawler 集成 ====================

class XHSCrawler:
    """小红书爬虫封装（基于MediaCrawler）"""

    def __init__(self):
        # 从 platforms/xiaohongshu/ 回到父目录的 MediaCrawler
        self.mc_path = Path(__file__).parent.parent.parent / "MediaCrawler"
        self.cookies_path = self.mc_path / "xhs_cookies.json"

    def load_cookies(self) -> Optional[str]:
        """加载cookies"""
        if not self.cookies_path.exists():
            return None

        try:
            with open(self.cookies_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookies = data.get('cookies', [])
            if cookies:
                return '; '.join([f"{c['name']}={c['value']}" for c in cookies])
        except Exception as e:
            print(f"  ⚠️ Cookie加载失败: {e}")
        return None

    def search_posts(self, keyword: str, count: int = 20) -> List[Dict]:
        """搜索帖子（需要配置MediaCrawler）"""
        print(f"\n📡 搜索关键词: {keyword}")
        print(f"   提示: 需要先在 MediaCrawler/config/base_config.py 中配置搜索参数")
        print(f"   然后运行: cd MediaCrawler && python main.py")
        print(f"   结果将保存在 MediaCrawler/output/xhs/search/")

        # 返回模拟数据用于演示
        return self._get_mock_posts()

    def get_user_posts(self, user_id: str, count: int = 30) -> List[Dict]:
        """获取用户帖子"""
        print(f"\n📡 获取用户帖子: {user_id}")
        print(f"   提示: 需要配置 MediaCrawler 的 XHS_CREATOR_ID_LIST")
        return []

    def _get_mock_posts(self) -> List[Dict]:
        """获取模拟帖子数据（用于测试）"""
        return [
            {
                'id': '001',
                'title': '【招生】2025年AI/ML方向博士招生',
                'desc': 'XX大学XX教授课题组招收2025年入学的博士研究生。研究方向：计算机视觉、深度学习。有意者请dd我了解详情。',
                'author': '留学小助手',
                'likes': 128,
                'comments': 45,
            },
            {
                'id': '002',
                'title': 'CVPR 2024 论文分享：我们的工作被接收了！',
                'desc': '很高兴我们的论文"Deep Learning for Vision"被CVPR 2024接收！感谢团队成员的努力。附上论文链接和代码仓库。',
                'author': '张教授',
                'likes': 523,
                'comments': 89,
            },
            {
                'id': '003',
                'title': '【推荐】哈佛大学XX教授招人啦！funding充足！',
                'desc': '哈佛大学XX教授招收ML方向全奖博士。教授人很nice，funding充足，名额有限，感兴趣的dd我内推！',
                'author': '北美申请酱',
                'likes': 234,
                'comments': 67,
            },
        ]


# ==================== 数据库存储 ====================

class MonitorDatabase:
    """监控数据库"""

    def __init__(self, db_path: str = "data/professor_monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """初始化表"""
        import sqlite3
        cursor = self.conn.cursor()

        # 账号表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                name TEXT,
                description TEXT,
                credibility_score REAL DEFAULT 0,
                is_professor INTEGER DEFAULT 0,
                is_agency INTEGER DEFAULT 0,
                confidence TEXT,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 帖子表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE,
                user_id TEXT,
                title TEXT,
                content TEXT,
                is_recruitment INTEGER DEFAULT 0,
                is_professor_post INTEGER DEFAULT 0,
                is_agency_post INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0,
                professor_name TEXT,
                university TEXT,
                research_area TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES accounts(user_id)
            )
        """)

        # 监控关键词表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE,
                enabled INTEGER DEFAULT 1,
                last_checked TIMESTAMP,
                hit_count INTEGER DEFAULT 0
            )
        """)

        # 通知记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                notification_type TEXT,
                message TEXT,
                sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_recruitment ON posts(is_recruitment)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_professor ON accounts(is_professor)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_agency ON accounts(is_agency)")

        self.conn.commit()

    def save_account(self, profile: AccountProfile) -> int:
        """保存账号分析结果"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO accounts
            (user_id, name, description, credibility_score, is_professor, is_agency,
             confidence, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (profile.user_id, profile.name, profile.description,
              profile.credibility_score, int(profile.is_professor),
              int(profile.is_agency), profile.confidence))
        self.conn.commit()
        return cursor.lastrowid

    def save_post(self, analysis: PostAnalysis, user_id: str) -> int:
        """保存帖子分析结果"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO posts
            (post_id, user_id, title, content, is_recruitment, is_professor_post,
             is_agency_post, confidence, professor_name, university, research_area)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (analysis.post_id, user_id, analysis.title, analysis.content,
              int(analysis.is_recruitment), int(analysis.is_professor_post),
              int(analysis.is_agency_post), analysis.confidence,
              analysis.professor_name, analysis.university, analysis.research_area))
        self.conn.commit()
        return cursor.lastrowid

    def get_professor_posts(self, hours: int = 24) -> List[Dict]:
        """获取最近的教授发帖"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.*, a.name as author_name, a.credibility_score
            FROM posts p
            JOIN accounts a ON p.user_id = a.user_id
            WHERE a.is_professor = 1
            AND datetime(p.created_at) >= datetime('now', '-' || ? || ' hours')
            ORDER BY p.created_at DESC
        """, (hours,))
        return [dict(row) for row in cursor.fetchall()]

    def get_agency_accounts(self) -> List[Dict]:
        """获取已识别的中介账号"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts
            WHERE is_agency = 1
            ORDER BY credibility_score ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """关闭数据库"""
        if self.conn:
            self.conn.close()


# ==================== 监控器 ====================

class ProfessorMonitor:
    """教授帖子监控器"""

    def __init__(self, enable_notification: bool = True):
        self.analyzer = CredibilityAnalyzer()
        self.crawler = XHSCrawler()
        self.db = MonitorDatabase()
        self.notifier = None

        # 初始化通知器
        if enable_notification:
            try:
                from telegram_notifier import TelegramNotifier
                self.notifier = TelegramNotifier()
                print("✅ Telegram 通知已启用")
            except Exception as e:
                print(f"⚠️ 通知初始化失败: {e}")
                print(f"   监控将继续运行，但不会发送通知")

    def check_user(self, user_id: str, user_name: str = "",
                   description: str = "", posts: List[Dict] = None) -> AccountProfile:
        """检查单个用户"""
        print(f"\n{'='*60}")
        print(f"🔍 分析账号: @{user_name}")
        print(f"{'='*60}")

        # 创建账号画像
        profile = AccountProfile(
            user_id=user_id,
            name=user_name,
            description=description,
            posts=posts or []
        )

        # 分析可信度
        profile = self.analyzer.analyze_account(profile)

        # 打印结果
        self._print_profile_result(profile)

        # 保存到数据库
        self.db.save_account(profile)

        return profile

    def analyze_post(self, post: Dict, user_id: str = "unknown") -> PostAnalysis:
        """分析单条帖子"""
        analysis = self.analyzer.analyze_post(post)
        self.db.save_post(analysis, user_id)
        return analysis

    def scan_and_alert(self, posts: List[Dict], auto_notify: bool = True) -> List[PostAnalysis]:
        """扫描帖子并筛选真实教授发帖"""
        print(f"\n📊 扫描 {len(posts)} 条帖子...")

        professor_posts = []
        agency_posts = []
        notified_count = 0

        for post in posts:
            analysis = self.analyzer.analyze_post(post)

            if analysis.is_professor_post and not analysis.is_agency_post:
                professor_posts.append(analysis)
            elif analysis.is_agency_post:
                agency_posts.append(analysis)

        print(f"\n✅ 发现 {len(professor_posts)} 条疑似真实教授发帖")
        print(f"⚠️ 发现 {len(agency_posts)} 条疑似中介发帖")

        # 发送通知
        if auto_notify and self.notifier:
            notified_count = self._send_professor_post_notifications(professor_posts)

        print(f"📤 已发送 {notified_count} 条通知到 Telegram")

        return professor_posts

    def _send_professor_post_notifications(self, analyses: List[PostAnalysis]) -> int:
        """发送教授帖子通知"""
        count = 0

        for analysis in analyses:
            # 只对高可信度的帖子发送通知
            if analysis.confidence >= 0.6:
                # 构造帖子链接
                post_url = f"https://www.xiaohongshu.com/explore/{analysis.post_id}"

                success = self.notifier.send_professor_post(
                    professor_name=analysis.author,
                    university=analysis.university or "未知",
                    research_area=analysis.research_area or "AI/ML",
                    post_title=analysis.title,
                    post_url=post_url,
                    credibility_score=analysis.confidence * 100
                )

                if success:
                    count += 1

        return count

    def _print_profile_result(self, profile: AccountProfile):
        """打印账号分析结果"""
        print(f"\n📋 账号分析结果:")
        print(f"   名称: {profile.name}")
        print(f"   可信度评分: {profile.credibility_score:.1f}/100")

        status = []
        if profile.is_professor:
            status.append("✅ 疑似真实教授")
        if profile.is_agency:
            status.append("⚠️ 疑似中介账号")

        if status:
            print(f"   判定: {' | '.join(status)} (置信度: {profile.confidence})")
        else:
            print(f"   判定: ❓ 无法确定")

        print(f"\n📊 特征分析:")
        print(f"   有个人身份信息: {'✅' if profile.has_personal_identity else '❌'}")
        print(f"   有研究内容: {'✅' if profile.has_research_content else '❌'}")
        print(f"   提及多位教授: {'⚠️' if profile.has_multiple_professors else '✅'}")
        print(f"   有联系方式: {'⚠️' if profile.has_contact_info else '✅'}")
        print(f"   中介词数量: {profile.agency_word_count}")
        print(f"   教授相关词: {profile.professor_word_count}")


# ==================== 命令行工具 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书AI教授监控系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析单个账号:
   python xhs_professor_monitor.py --analyze-user USER_ID --name "用户名"

2. 批量分析帖子:
   python xhs_professor_monitor.py --analyze-file posts.json

3. 监控模式:
   python xhs_professor_monitor.py --monitor --interval 300

4. 查看已识别的中介:
   python xhs_professor_monitor.py --list-agency
        """
    )

    parser.add_argument('--analyze-user', metavar='USER_ID',
                       help='分析指定用户')
    parser.add_argument('--name', metavar='NAME',
                       help='用户名')
    parser.add_argument('--bio', metavar='BIO',
                       help='用户简介')

    parser.add_argument('--analyze-file', metavar='FILE',
                       help='分析文件中的帖子数据 (JSON)')

    parser.add_argument('--keywords', metavar='KEYWORDS',
                       help='监控关键词（逗号分隔）')

    parser.add_argument('--monitor', action='store_true',
                       help='启动持续监控模式')
    parser.add_argument('--interval', type=int, default=300,
                       help='监控间隔（秒），默认300')

    parser.add_argument('--list-agency', action='store_true',
                       help='列出已识别的中介账号')

    parser.add_argument('--list-professors', action='store_true',
                       help='列出已识别的教授账号')

    parser.add_argument('--test', action='store_true',
                       help='运行测试模式（使用模拟数据）')

    args = parser.parse_args()

    monitor = ProfessorMonitor()

    # 列出中介
    if args.list_agency:
        agencies = monitor.db.get_agency_accounts()
        print(f"\n⚠️ 已识别的中介账号 ({len(agencies)} 个):\n")
        for a in agencies:
            print(f"  - {a['name']} (评分: {a['credibility_score']:.0f})")
        return

    # 列出教授
    if args.list_professors:
        cursor = monitor.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_professor = 1")
        professors = [dict(row) for row in cursor.fetchall()]
        print(f"\n✅ 已识别的教授账号 ({len(professors)} 个):\n")
        for p in professors:
            print(f"  - {p['name']} (评分: {p['credibility_score']:.0f}, 置信度: {p['confidence']})")
        return

    # 分析用户
    if args.analyze_user:
        monitor.check_user(
            user_id=args.analyze_user,
            user_name=args.name or "未知用户",
            description=args.bio or ""
        )
        return

    # 测试模式
    if args.test:
        print("\n" + "="*60)
        print("🧪 测试模式 - 使用模拟数据")
        print("="*60)

        # 模拟数据
        test_cases = [
            {
                'name': '张教授AI',
                'description': 'XX大学计算机系教授，研究方向：深度学习、计算机视觉',
                'posts': [
                    {'title': 'CVPR 2024 论文分享', 'desc': '我们的论文被接收了！'},
                    {'title': '实验室招生', 'desc': '2025年招收博士研究生'},
                ]
            },
            {
                'name': '留学申请中介8866',
                'description': '专注英美申请，dd我了解详情',
                'posts': [
                    {'title': '哈佛大学AI教授招人', 'desc': 'XX教授人很nice，名额有限dd我'},
                    {'title': 'MIT ML方向内推', 'desc': 'XX教授funding充足，有需要的联系'},
                    {'title': '斯坦福CV实验室招生', 'desc': 'XX导师愿意帮学生，私信了解'},
                ]
            },
            {
                'name': '学术资讯搬运工',
                'description': '分享最新学术资讯',
                'posts': [
                    {'title': 'ICML 2024 最佳论文解读',
                        'desc': '本届ICML的最佳论文是...'},
                ]
            },
        ]

        for i, case in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"测试用例 {i}: {case['name']}")
            print(f"{'='*60}")

            profile = AccountProfile(
                user_id=f"test_{i}",
                name=case['name'],
                description=case['description'],
                posts=[{'title': p['title'], 'desc': p['desc']} for p in case['posts']]
            )

            profile = monitor.analyzer.analyze_account(profile)
            monitor._print_profile_result(profile)
            monitor.db.save_account(profile)

        print(f"\n{'='*60}")
        print("✅ 测试完成")
        print(f"{'='*60}")

        # 显示总结
        print(f"\n📊 测试总结:")
        cursor = monitor.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_professor = 1")
        prof_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_agency = 1")
        agency_count = cursor.fetchone()[0]
        print(f"   识别为教授: {prof_count} 个")
        print(f"   识别为中介: {agency_count} 个")

        return

    # 如果没有指定操作，显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
