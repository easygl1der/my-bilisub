#!/usr/bin/env python3
"""
一键运行小红书教授监控系统

流程：
1. 运行 MediaCrawler 爬取小红书数据
2. 分析爬取的数据
3. 发送 Telegram 通知

使用方法：
    # 手动运行一次
    python run_monitor.py

    # 定时运行（每10分钟）
    python run_monitor.py --interval 600

    # 指定搜索关键词
    python run_monitor.py --keywords "AI教授,ML招生,博士申请"
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ==================== 配置 ====================

# 监控的关键词
DEFAULT_KEYWORDS = "AI教授,ML招生,计算机视觉,博士申请,导师招生,CVPR,ICCV"

# MediaCrawler 路径（从 bot/ 目录回到父目录）
MEDIA_CRAWLER_PATH = Path(__file__).parent.parent / "MediaCrawler"

# 爬取帖子数量
CRAWL_COUNT = 20


# ==================== 工具函数 ====================

def print_banner():
    """打印横幅"""
    print("\n" + "="*60)
    print("🤖 小红书教授监控系统")
    print("="*60)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")


def print_step(step: int, total: int, message: str):
    """打印步骤"""
    print(f"\n[步骤 {step}/{total}] {message}")
    print("-" * 50)


# ==================== 核心功能 ====================

def update_keywords(keywords: str):
    """更新 MediaCrawler 配置中的关键词"""
    config_path = MEDIA_CRAWLER_PATH / "config" / "base_config.py"

    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return False

    # 读取配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换关键词
    import re
    pattern = r'KEYWORDS = "[^"]*"'
    new_line = f'KEYWORDS = "{keywords}"'

    if re.search(pattern, content):
        content = re.sub(pattern, new_line, content)
    else:
        # 如果没找到，添加到文件中
        content = content.replace(
            'PLATFORM = "xhs"',
            f'PLATFORM = "xhs"\nKEYWORDS = "{keywords}"'
        )

    # 写回文件
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 关键词已更新: {keywords}")
    return True


def run_crawler() -> bool:
    """运行 MediaCrawler 爬虫"""
    print_step(1, 3, "📡 启动 MediaCrawler 爬取小红书数据...")

    os.chdir(MEDIA_CRAWLER_PATH)

    try:
        # 使用 uv 运行（如果安装了）
        if (MEDIA_CRAWLER_PATH / "uv.lock").exists():
            print("   使用 uv 运行...")
            result = subprocess.run(
                ["uv", "run", "python", "main.py"],
                capture_output=True,
                encoding='utf-8',
                errors='ignore',
                timeout=600  # 10分钟超时
            )
        else:
            # 使用普通 python
            print("   使用 python 运行...")
            result = subprocess.run(
                [sys.executable, "main.py"],
                capture_output=True,
                encoding='utf-8',
                errors='ignore',
                timeout=600
            )

        # 输出结果
        if result.stdout:
            output = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            print(output)

        if result.returncode == 0:
            print("✅ 爬取完成")
            return True
        else:
            print(f"⚠️ 爬取可能有问题，返回码: {result.returncode}")
            return True  # 继续分析，可能已经有数据了

    except subprocess.TimeoutExpired:
        print("⚠️ 爬取超时，继续分析已有数据...")
        return True
    except FileNotFoundError:
        print("❌ 找不到 python，请检查环境")
        return False
    except Exception as e:
        print(f"❌ 爬取出错: {e}")
        return False
    finally:
        os.chdir(Path(__file__).parent)


def analyze_data() -> bool:
    """分析爬取的数据"""
    print_step(2, 3, "🔍 分析数据并识别教授账号...")

    try:
        script_path = Path(__file__).parent.parent / "platforms" / "xiaohongshu" / "xhs_professor_monitor_integration.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--analyze-data"],
            capture_output=True,
            encoding='utf-8',
            errors='ignore',
            timeout=120
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode == 0:
            print("✅ 分析完成")
            return True
        else:
            print(f"⚠️ 分析可能有问题")
            return False

    except Exception as e:
        print(f"❌ 分析出错: {e}")
        return False


def send_notifications():
    """发送通知（已集成在分析模块中）"""
    print_step(3, 3, "📤 Telegram 通知已自动发送...")
    print("✅ 流程完成！")


def run_once(keywords: str = None):
    """运行一次完整流程"""
    print_banner()

    # 更新关键词
    if keywords:
        update_keywords(keywords)

    # 运行流程
    if not run_crawler():
        print("\n❌ 爬取失败，终止流程")
        return False

    if not analyze_data():
        print("\n❌ 分析失败，终止流程")
        return False

    send_notifications()

    print(f"\n✅ 本次监控完成！时间: {datetime.now().strftime('%H:%M:%S')}\n")
    return True


def run_monitor(interval: int, keywords: str = None):
    """持续监控模式"""
    print_banner()
    print(f"🔄 持续监控模式启动")
    print(f"⏱️  间隔: {interval} 秒 ({interval//60} 分钟)")
    print(f"🔑 关键词: {keywords or DEFAULT_KEYWORDS}")
    print(f"⚠️  按 Ctrl+C 停止监控\n")

    try:
        run_count = 0
        while True:
            run_count += 1
            print(f"\n{'='*60}")
            print(f"🔄 第 {run_count} 次监控")
            print(f"{'='*60}")

            run_once(keywords)

            print(f"\n⏰ 下次运行: {interval} 秒后...")
            print(f"⏰ 预计时间: {datetime.fromtimestamp(time.time() + interval).strftime('%H:%M:%S')}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")
        print(f"📊 总共运行了 {run_count} 次")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书教授监控系统 - 一键运行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 运行一次:
   python run_monitor.py

2. 持续监控（每10分钟）:
   python run_monitor.py --interval 600

3. 自定义关键词:
   python run_monitor.py --keywords "AI教授,ML招生"

4. 只分析已有数据:
   python run_monitor.py --analyze-only
        """
    )

    parser.add_argument('--keywords', default=DEFAULT_KEYWORDS,
                       help=f'搜索关键词，默认: {DEFAULT_KEYWORDS}')

    parser.add_argument('--interval', type=int, default=0,
                       help='监控间隔（秒），设为0则只运行一次，默认600秒（10分钟）')

    parser.add_argument('--analyze-only', action='store_true',
                       help='只分析已有数据，不运行爬虫')

    parser.add_argument('--crawl-only', action='store_true',
                       help='只运行爬虫，不分析')

    args = parser.parse_args()

    if args.analyze_only:
        print_banner()
        analyze_data()
        send_notifications()
    elif args.crawl_only:
        print_banner()
        run_crawler()
    elif args.interval > 0:
        run_monitor(args.interval, args.keywords)
    else:
        run_once(args.keywords)


if __name__ == "__main__":
    main()
