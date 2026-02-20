#!/usr/bin/env python3
"""
配置管理模块
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Any

# 默认配置
DEFAULT_CONFIG = {
    # 监控的博主列表
    "creators": [
        {
            "name": "示例博主",
            "platform": "bilibili",
            "uid": "123456789",
            "category": "科技",
            "enabled": True
        }
    ],

    # 监控设置
    "monitor": {
        "check_interval": 300,          # 检查间隔（秒），默认5分钟
        "max_videos_per_check": 50,     # 每次最多获取视频数
        "lookback_days": 7,             # 首次运行时回溯天数
    },

    # 分析设置
    "analysis": {
        "model": "flash-lite",           # Gemini模型
        "mode": "knowledge",             # 分析模式
        "max_concurrent": 10,            # 并发数
        "auto_analyze": True,            # 自动分析新视频
    },

    # 新闻分类
    "categories": ["科技", "财经", "国际", "民生", "娱乐", "体育", "教育", "其他"],

    # 数据存储
    "database": {
        "path": "data/second_brain.db",
        "backup_enabled": True,
    },

    # 推送设置
    "notification": {
        "enabled": False,
        "email": {
            "enabled": False,
            "to": "",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
        },
        "console": {
            "enabled": True,             # 控制台输出
        }
    },

    # 知识库设置
    "knowledge_base": {
        "output_dir": "knowledge_base",
        "format": "markdown",
    }
}


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or "config/second_brain.yaml"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_path = Path(self.config_path)

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    # 合并默认配置
                    return self._merge_config(DEFAULT_CONFIG, user_config)
            except Exception as e:
                print(f"⚠️ 加载配置文件失败: {e}，使用默认配置")

        return DEFAULT_CONFIG.copy()

    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """递归合并配置"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default=None):
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def save(self):
        """保存配置到文件"""
        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    @property
    def creators(self) -> List[Dict]:
        """获取启用的博主列表"""
        return [c for c in self.config.get('creators', []) if c.get('enabled', True)]

    @property
    def check_interval(self) -> int:
        """获取检查间隔"""
        return self.config.get('monitor', {}).get('check_interval', 300)

    @property
    def database_path(self) -> str:
        """获取数据库路径"""
        return self.config.get('database', {}).get('path', 'data/second_brain.db')
