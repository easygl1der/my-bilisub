#!/usr/bin/env python3
"""
数据库模块 - 存储视频和分析记录
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


class Database:
    """数据库管理类"""

    def __init__(self, db_path: str = "data/second_brain.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _init_tables(self):
        """初始化数据表"""
        with self.transaction() as cursor:
            # 博主表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS creators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT,
                    avatar_url TEXT,
                    fans_count INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, uid)
                )
            """)

            # 视频表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER,
                    platform TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    duration INTEGER,
                    published_at TIMESTAMP,
                    thumbnail_url TEXT,
                    video_url TEXT,
                    view_count INTEGER DEFAULT 0,
                    danmaku_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (creator_id) REFERENCES creators(id),
                    UNIQUE(platform, video_id)
                )
            """)

            # 分析状态表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    model TEXT,
                    mode TEXT,
                    output_file TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                )
            """)

            # 新闻表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER,
                    title TEXT NOT NULL,
                    category TEXT,
                    summary TEXT,
                    key_points TEXT,
                    people TEXT,
                    events TEXT,
                    news_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                )
            """)

            # 监控日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitor_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT,
                    action TEXT,
                    count INTEGER DEFAULT 0,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_creator ON videos(creator_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_status(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_date ON news(news_date DESC)")

    # ==================== 博主相关 ====================

    def add_creator(self, platform: str, uid: str, name: str, category: str = "",
                    avatar_url: str = None, fans_count: int = 0, enabled: bool = True) -> int:
        """添加或更新博主"""
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO creators
                (platform, uid, name, category, avatar_url, fans_count, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (platform, uid, name, category, avatar_url, fans_count, int(enabled)))
            return cursor.lastrowid

    def get_creator(self, platform: str, uid: str) -> Optional[Dict]:
        """获取博主信息"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM creators WHERE platform = ? AND uid = ?", (platform, uid))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_creators(self, platform: str = None, enabled_only: bool = True) -> List[Dict]:
        """获取博主列表"""
        cursor = self.conn.cursor()
        if platform:
            if enabled_only:
                cursor.execute("SELECT * FROM creators WHERE platform = ? AND enabled = 1", (platform,))
            else:
                cursor.execute("SELECT * FROM creators WHERE platform = ?", (platform,))
        else:
            if enabled_only:
                cursor.execute("SELECT * FROM creators WHERE enabled = 1")
            else:
                cursor.execute("SELECT * FROM creators")
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 视频相关 ====================

    def add_video(self, creator_id: int, platform: str, video_id: str, title: str,
                  description: str = None, duration: int = None, published_at: str = None,
                  thumbnail_url: str = None, video_url: str = None, view_count: int = 0,
                  danmaku_count: int = 0) -> int:
        """添加视频"""
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO videos
                (creator_id, platform, video_id, title, description, duration, published_at,
                 thumbnail_url, video_url, view_count, danmaku_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (creator_id, platform, video_id, title, description, duration,
                  published_at, thumbnail_url, video_url, view_count, danmaku_count))
            return cursor.lastrowid

    def get_video(self, video_id: str, platform: str) -> Optional[Dict]:
        """获取视频信息"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE platform = ? AND video_id = ?", (platform, video_id))
        row = cursor.fetchone()
        return dict(row) if row else None

    def video_exists(self, video_id: str, platform: str) -> bool:
        """检查视频是否存在"""
        return self.get_video(video_id, platform) is not None

    def get_videos_by_creator(self, creator_id: int, limit: int = 50,
                               offset: int = 0, order_by: str = "published_at DESC") -> List[Dict]:
        """获取博主视频列表"""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            SELECT * FROM videos WHERE creator_id = ?
            ORDER BY {order_by} DESC LIMIT ? OFFSET ?
        """, (creator_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_videos(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """获取最近N小时的视频"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT v.*, c.name as creator_name, c.platform
            FROM videos v
            JOIN creators c ON v.creator_id = c.id
            WHERE datetime(v.published_at) >= datetime('now', '-' || ? || ' hours')
            ORDER BY v.published_at DESC
            LIMIT ?
        """, (hours, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_unanalyzed_videos(self, limit: int = 100) -> List[Dict]:
        """获取未分析的视频"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT v.* FROM videos v
            LEFT JOIN analysis_status a ON v.id = a.video_id
            WHERE a.id IS NULL OR a.status != 'completed'
            ORDER BY v.published_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 分析状态相关 ====================

    def create_analysis_status(self, video_id: int, status: str = "pending") -> int:
        """创建分析状态记录"""
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO analysis_status (video_id, status)
                VALUES (?, ?)
            """, (video_id, status))
            return cursor.lastrowid

    def update_analysis_status(self, video_id: int, status: str,
                               output_file: str = None, error_message: str = None,
                               model: str = None, mode: str = None):
        """更新分析状态"""
        with self.transaction() as cursor:
            if status == "completed":
                cursor.execute("""
                    UPDATE analysis_status
                    SET status = ?, output_file = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                """, (status, output_file, video_id))
            elif status == "failed":
                cursor.execute("""
                    UPDATE analysis_status
                    SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                """, (status, error_message, video_id))
            else:
                cursor.execute("""
                    UPDATE analysis_status
                    SET status = ?, model = ?, mode = ?
                    WHERE video_id = ?
                """, (status, model, mode, video_id))

    # ==================== 新闻相关 ====================

    def save_news(self, video_id: int, title: str, category: str, summary: str,
                  key_points: list = None, people: list = None, events: list = None,
                  news_date: str = None) -> int:
        """保存新闻"""
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO news
                (video_id, title, category, summary, key_points, people, events, news_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (video_id, title, category, summary,
                  json.dumps(key_points or [], ensure_ascii=False),
                  json.dumps(people or [], ensure_ascii=False),
                  json.dumps(events or [], ensure_ascii=False),
                  news_date))
            return cursor.lastrowid

    def get_news_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的新闻"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.*, v.title as video_title, c.name as creator_name
            FROM news n
            JOIN videos v ON n.video_id = v.id
            JOIN creators c ON v.creator_id = c.id
            WHERE n.news_date = ?
            ORDER BY n.id
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_news(self, days: int = 1) -> List[Dict]:
        """获取最近N天的新闻"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT n.*, v.title as video_title, c.name as creator_name
            FROM news n
            JOIN videos v ON n.video_id = v.id
            JOIN creators c ON v.creator_id = c.id
            WHERE date(n.news_date) >= date('now', '-' || ? || ' days')
            ORDER BY n.news_date DESC, n.id DESC
        """, (days,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 日志相关 ====================

    def log(self, platform: str, action: str, count: int = 0, details: str = None):
        """记录日志"""
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO monitor_logs (platform, action, count, details)
                VALUES (?, ?, ?, ?)
            """, (platform, action, count, details))

    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """获取最近日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM monitor_logs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 统计相关 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        cursor = self.conn.cursor()

        stats = {}

        # 博主统计
        cursor.execute("SELECT COUNT(*) FROM creators WHERE enabled = 1")
        stats['active_creators'] = cursor.fetchone()[0]

        # 视频统计
        cursor.execute("SELECT COUNT(*) FROM videos")
        stats['total_videos'] = cursor.fetchone()[0]

        # 今日视频
        cursor.execute("SELECT COUNT(*) FROM videos WHERE date(published_at) = date('now')")
        stats['today_videos'] = cursor.fetchone()[0]

        # 分析统计
        cursor.execute("SELECT COUNT(*) FROM analysis_status WHERE status = 'completed'")
        stats['analyzed_videos'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM analysis_status WHERE status = 'pending'")
        stats['pending_analysis'] = cursor.fetchone()[0]

        # 新闻统计
        cursor.execute("SELECT COUNT(*) FROM news WHERE news_date = date('now')")
        stats['today_news'] = cursor.fetchone()[0]

        return stats

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
