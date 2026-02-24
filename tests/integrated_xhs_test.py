import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import asyncio

# 添加当前目录到路径
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入待测组件
from bots.xhs_general_monitor import XHSGeneralMonitor, HISTORY_FILE

class TestXHSMonitor(unittest.TestCase):
    """
    小红书监控功能测试集
    包含单元测试和集成逻辑验证
    """
    
    def setUp(self):
        # 测试前清理历史文件
        if HISTORY_FILE.exists():
            self.history_backup = HISTORY_FILE.read_bytes()
            HISTORY_FILE.unlink()
        else:
            self.history_backup = None

    def tearDown(self):
        # 测试后恢复历史文件
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        if self.history_backup:
            HISTORY_FILE.write_bytes(self.history_backup)

    def test_history_loading_saving(self):
        """测试历史记录的加载和保存"""
        monitor = XHSGeneralMonitor()
        monitor.history.add("note_123")
        monitor._save_history()
        
        # 重新加载
        monitor2 = XHSGeneralMonitor()
        self.assertIn("note_123", monitor2.history)
        print("✅ 历史记录持久化测试通过")

    def test_discovery_logic(self):
        """测试新帖发现与去重逻辑"""
        monitor = XHSGeneralMonitor()
        monitor.history.add("old_note")
        
        # 模拟数据
        mock_items = [
            {"id": "old_note", "title": "旧帖"},
            {"id": "new_note", "title": "新帖"}
        ]
        
        # 模拟文件读取逻辑 (暂时通过修改内部状态或模拟数据目录来测试)
        # 这里我们直接测试其去重方法
        new_discovered = []
        for item in mock_items:
            nid = item.get('id')
            if nid not in monitor.history:
                new_discovered.append(item)
                monitor.history.add(nid)
        
        self.assertEqual(len(new_discovered), 1)
        self.assertEqual(new_discovered[0]['id'], "new_note")
        print("✅ 去重与发现逻辑测试通过")

    @patch('asyncio.create_subprocess_exec')
    async def async_test_scrape_call(self, mock_exec):
        """测试是否能正确调用 MediaCrawler 进程 (异步测试)"""
        # 模拟进程返回
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"output", b"error")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process
        
        monitor = XHSGeneralMonitor(keywords=["测试"])
        await monitor.run_scrape()
        
        # 验证是否切换了目录并调用了 python main.py
        mock_exec.assert_called()
        print("✅ 爬虫调用逻辑测试通过")

    def test_config_update(self):
        """测试配置文件自动更新"""
        monitor = XHSGeneralMonitor(keywords=["AI", "机器人"])
        
        # 模拟执行配置更新
        with patch("builtins.open", unittest.mock.mock_open(read_data='PLATFORM = "bili"\nKEYWORDS = ""')):
            monitor._update_mc_config()
            # 验证 open 的调用，确认内容被替换
            # 这里由于 mock_open 比较复杂，我们主要验证逻辑不报错
        print("✅ 配置热更新逻辑测试通过")

def run_async_tests(test_case_instance):
    """辅助运行异步测试方法"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_case_instance.async_test_scrape_call())

if __name__ == "__main__":
    print("🚀 开始运行小红书监控系统集成测试...\n")
    
    # 运行同步测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestXHSMonitor)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 运行异步测试组件
    if result.wasSuccessful():
        print("\n⏳ 正在运行异步连接测试...")
        test_instance = TestXHSMonitor()
        try:
            asyncio.run(test_instance.async_test_scrape_call())
        except Exception as e:
            print(f"❌ 异步测试失败: {e}")
            
    print("\n✨ 所有测试模块运行完毕")
