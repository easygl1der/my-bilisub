#!/usr/bin/env python3
"""
Telegram 通知模块

用于发送小红书教授监控系统的实时通知
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional
from datetime import datetime


class TelegramNotifier:
    """Telegram 通知器"""

    def __init__(self, token: str = None, chat_id: str = None, config_path: str = None):
        """
        初始化通知器

        Args:
            token: Bot Token（可选，优先从配置文件读取）
            chat_id: Chat ID（可选，优先从配置文件读取）
            config_path: 配置文件路径（默认为 config/telegram_config.json）
        """
        if config_path is None:
            # 从 bot/ 目录运行，需要相对路径调整
            script_dir = Path(__file__).parent
            config_path = script_dir.parent / "config" / "telegram_config.json"

        self.token = token
        self.chat_id = chat_id
        self.config_path = Path(config_path)

        # 如果没有提供参数，尝试从配置文件读取
        if not self.token or not self.chat_id:
            self._load_config()

        if not self.token or not self.chat_id:
            raise ValueError(
                "Token 和 Chat ID 未配置！\n"
                f"请创建 {self.config_path} 文件，或通过参数传入。\n"
                "格式: {\"bot_token\": \"xxx\", \"chat_id\": \"xxx\"}"
            )

        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def _load_config(self):
        """从配置文件加载"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.token = config.get('bot_token')
                self.chat_id = config.get('chat_id')
            except Exception as e:
                print(f"⚠️ 配置文件读取失败: {e}")

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        发送消息

        Args:
            text: 消息内容
            parse_mode: 解析模式 (Markdown, HTML, None)

        Returns:
            是否发送成功
        """
        url = f"{self.api_url}/sendMessage"

        data = {
            "chat_id": str(self.chat_id),
            "text": text
        }

        if parse_mode:
            data["parse_mode"] = parse_mode

        try:
            # 使用 urllib 发送 POST 请求
            headers = {'Content-Type': 'application/json'}
            json_data = json.dumps(data).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=json_data,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get("ok"):
                return True
            else:
                print(f"⚠️ 发送失败: {result.get('description')}")
                return False

        except urllib.error.URLError as e:
            print(f"⚠️ 网络错误: {e}")
            return False
        except Exception as e:
            print(f"⚠️ 发送异常: {e}")
            return False

    def send_professor_post(self, professor_name: str, university: str,
                           research_area: str, post_title: str, post_url: str,
                           credibility_score: float = 0) -> bool:
        """
        发送教授新帖子通知

        Args:
            professor_name: 教授名称
            university: 大学
            research_area: 研究方向
            post_title: 帖子标题
            post_url: 帖子链接
            credibility_score: 可信度评分

        Returns:
            是否发送成功
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        message = f"""🔔 *小红书教授新帖通知*

📅 时间: `{timestamp}`

👨‍🏫 *教授*: {professor_name}
🏫 *学校*: {university}
🔬 *方向*: {research_area}
📊 *可信度*: {credibility_score:.0f}/100

📝 *帖子*: {post_title}

🔗 [查看帖子]({post_url})

---
✅ 此账号已通过AI甄别，确认为真实教授账号"""

        return self.send_message(message)

    def send_daily_summary(self, new_professor_posts: int, blocked_agency_posts: int,
                          top_professors: list) -> bool:
        """
        发送每日汇总

        Args:
            new_professor_posts: 新增教授帖子数
            blocked_agency_posts: 拦截的中介帖子数
            top_professors: 热门教授列表

        Returns:
            是否发送成功
        """
        date = datetime.now().strftime("%Y-%m-%d")

        message = f"""📊 *每日监控汇总* - `{date}`

📈 *今日统计*
• 真实教授发帖: `{new_professor_posts}` 条
• 拦截中介帖: `{blocked_agency_posts}` 条
• 净化率: `{blocked_agency_posts/(new_professor_posts+blocked_agency_posts)*100:.1f}%` if (new_professor_posts+blocked_agency_posts) > 0 else "0%`

"""

        if top_professors:
            message += "✨ *热门教授账号*\n"
            for i, prof in enumerate(top_professors[:5], 1):
                message += f"{i}. {prof.get('name', 'N/A')} ({prof.get('credibility_score', 0):.0f}分)\n"

        message += "\n💡 回复 `/help` 查看更多命令"

        return self.send_message(message)

    def send_alert(self, title: str, message: str) -> bool:
        """
        发送紧急提醒

        Args:
            title: 标题
            message: 消息内容

        Returns:
            是否发送成功
        """
        text = f"🚨 *{title}*\n\n{message}"
        return self.send_message(text)

    def test_connection(self) -> bool:
        """测试连接"""
        message = f"""✅ *Telegram 通知测试成功*

🤖 小红书教授监控系统已连接

🕐 测试时间: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

你将很快收到真实教授的招生通知！"""

        return self.send_message(message)


def save_config(token: str, chat_id: str, config_path: str = None):
    """保存配置到文件"""
    if config_path is None:
        # 从 bot/ 目录运行，需要相对路径调整
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / "config" / "telegram_config.json"

    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "bot_token": token,
        "chat_id": chat_id
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ 配置已保存: {config_path}")


if __name__ == "__main__":
    import sys

    # Windows编码修复
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # 测试发送
    notifier = TelegramNotifier(
        token="8475725570:AAFaM7Y1i7Gcfp_wqfjQZfh0zh61ZyAjFfg",
        chat_id="8021896102"
    )

    print("🧪 发送测试消息...")
    if notifier.test_connection():
        print("✅ 测试成功！请检查 Telegram")
    else:
        print("❌ 测试失败")
