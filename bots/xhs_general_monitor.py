import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

# ==================== 配置区 ====================
# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
# MediaCrawler 目录
MC_DIR = ROOT_DIR / "MediaCrawler"
# 监控历史文件（用于去重）
HISTORY_FILE = ROOT_DIR / "config" / "xhs_monitor_history.json"
# Telegram 配置路径
TG_CONFIG_PATH = ROOT_DIR / "config" / "telegram_config.json"

class XHSGeneralMonitor:
    """通用小红书监控器"""
    
    def __init__(self, keywords=None, user_ids=None):
        self.keywords = keywords or []
        self.user_ids = user_ids or []
        self.history = self._load_history()
        
    def _load_history(self):
        """加载已发现的笔记 ID 历史"""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_history(self):
        """保存历史记录"""
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(self.history), f, ensure_ascii=False, indent=2)

    async def run_scrape(self):
        """调用 MediaCrawler 进行爬取"""
        # 修改 MediaCrawler 的 base_config.py 中的关键词
        self._update_mc_config()
        
        print(f"📡 正在运行 MediaCrawler 爬取关键词: {','.join(self.keywords)}")
        
        # 切换到 MediaCrawler 目录运行
        original_cwd = os.getcwd()
        os.chdir(MC_DIR)
        
        try:
            # 使用 subprocess 运行 main.py
            # 模式设置为 search, 平台设置为 xhs
            cmd = [sys.executable, "main.py"]
            # 注意：实际运行中可能需要通过环境变量或直接修改 config 传入参数
            # 这里假设 MediaCrawler 的 config 会读取 base_config.py
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"⚠️ 爬虫退出代码: {process.returncode}")
                # print(stderr.decode())
            
        finally:
            os.chdir(original_cwd)

    def _update_mc_config(self):
        """修改 MediaCrawler 配置"""
        config_path = MC_DIR / "config" / "base_config.py"
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换关键词和平台
        import re
        content = re.sub(r'PLATFORM = "[^"]+"', 'PLATFORM = "xhs"', content)
        content = re.sub(r'KEYWORDS = "[^"]+"', f'KEYWORDS = "{",".join(self.keywords)}"', content)
        content = re.sub(r'CRAWLER_TYPE = "[^"]+"', 'CRAWLER_TYPE = "search"', content)
        # 设置排序为“最新”
        if 'SORT_TYPE = "time_descending"' not in content:
            # 假设 xhs_config.py 或 base_config.py 中有这个参数
             content = re.sub(r'SORT_TYPE = "[^"]*"', 'SORT_TYPE = "time_descending"', content)

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def discover_new_notes(self):
        """分析采集到的数据，找出新帖子"""
        # 数据通常保存在 MediaCrawler/data/xhs 下
        data_dir = MC_DIR / "data" / "xhs"
        new_notes = []
        
        if not data_dir.exists():
            print("⚠️ 未找到采集数据目录")
            return new_notes

        for json_file in data_dir.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                items = data if isinstance(data, list) else [data]
                for item in items:
                    note_id = item.get('note_id') or item.get('id')
                    if note_id and note_id not in self.history:
                        new_notes.append(item)
                        self.history.add(note_id)
            except Exception:
                continue
        
        if new_notes:
            self._save_history()
        
        return new_notes

    async def notify(self, new_notes):
        """发送通知"""
        if not new_notes:
            print("📭 没有发现新帖子")
            return

        # 尝试使用现有的 telegram_notifier
        sys.path.insert(0, str(ROOT_DIR / "bots"))
        try:
            from telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            
            for note in new_notes:
                title = note.get('title', '无标题')
                author = note.get('nickname', '未知博主')
                note_id = note.get('note_id') or note.get('id')
                url = f"https://www.xiaohongshu.com/explore/{note_id}"
                
                msg = f"🔔 *新帖子提醒*\n\n" \
                      f"📝 *标题*: {title}\n" \
                      f"👤 *博主*: {author}\n" \
                      f"🔗 [点击查看]({url})"
                
                notifier.send_message(msg)
                print(f"✅ 已发送通知: {title}")
        except Exception as e:
            print(f"❌ 发送通知失败: {e}")
            # 降级：只打印到控制台
            for note in new_notes:
                print(f"NEW POST: {note.get('title')} by {note.get('nickname')}")

async def main():
    # 示例运行
    monitor = XHSGeneralMonitor(keywords=["AI教授", "计算机视觉"])
    await monitor.run_scrape()
    new_notes = monitor.discover_new_notes()
    await monitor.notify(new_notes)

if __name__ == "__main__":
    asyncio.run(main())
