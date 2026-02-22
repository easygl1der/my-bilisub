#!/usr/bin/env python3
"""
B站首页推荐流自动采集工具

功能：
- 使用 Playwright 访问 B 站首页
- 解析推荐视频卡片，提取标题、链接、UP主信息
- 支持多次刷新采集
- 支持命令行模式和 Bot 模式调用
- 可选 AI 分析功能

使用方法:
    # 基本采集
    python bili_homepage_scraper.py --refresh 10

    # 采集 + AI 分析
    python bili_homepage_scraper.py --refresh 10 --analyze

    # 指定输出文件
    python bili_homepage_scraper.py --refresh 5 --output my_homepage.csv

    # 测试模式（只采集一次）
    python bili_homepage_scraper.py --test
"""

import os
import sys
import json
import time
import asyncio
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Callable

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        # 如果 stdout 已经关闭或不可用，跳过修复
        pass

# 导入 Playwright
try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("❌ 未安装 playwright")
    print("请运行: pip install playwright")
    print("然后运行: playwright install chromium")
    sys.exit(1)

# 导入 Cookie 管理器
try:
    from bot.cookie_manager import get_cookie, check_cookie
except ImportError:
    print("⚠️ 无法导入 cookie_manager，将不使用 Cookie 登录")
    get_cookie = None
    check_cookie = None


# ==================== 配置 ====================

SCRAPER_CONFIG = {
    "max_refresh": 10,              # 最大刷新次数
    "refresh_interval": 3,          # 刷新间隔（秒）
    "headless": False,              # 是否无头模式
    "use_cookie": True,             # 是否使用 Cookie 登录
    "cookie_path": "config/cookies.txt",
    "output_dir": "output/homepage",
    "bili_homepage": "https://www.bilibili.com",
}

# B站首页推荐流的 DOM 选择器（根据实际页面结构可能需要调整）
SELECTORS = {
    # 推荐视频卡片容器
    "video_card": "a.bvideo-card",

    # 视频标题
    "title": ".info-title, .title, h3",

    # 视频链接（从卡片的 href 属性获取）
    "link": "href",

    # UP主名称
    "uploader": ".up-name, .author-name, .info--author",

    # UP主链接
    "uploader_link": "href",

    # "换一换"刷新按钮
    "refresh_button": ".refresh-btn, .feed-refresh-btn, button:has-text('换一换')",

    # 需要排除的内容类型
    "exclude_selectors": [
        ".is-live",           # 直播
        ".bangumi-card",      # 番剧
        ".ad-card",           # 广告
    ]
}


# ==================== 数据模型 ====================

class VideoInfo:
    """视频信息"""

    def __init__(self, bvid: str, title: str, uploader: str,
                 uploader_url: str, video_url: str, duration: str = ""):
        self.bvid = bvid
        self.title = title
        self.uploader = uploader
        self.uploader_url = uploader_url
        self.video_url = video_url
        self.duration = duration
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "bvid": self.bvid,
            "title": self.title,
            "uploader": self.uploader,
            "uploader_url": self.uploader_url,
            "video_url": self.video_url,
            "duration": self.duration,
        }

    def __repr__(self):
        return f"VideoInfo(bvid={self.bvid}, title={self.title[:20]}...)"


# ==================== 核心爬虫类 ====================

class BiliHomepageScraper:
    """B站首页推荐流爬虫"""

    def __init__(self,
                 max_refresh: int = 10,
                 refresh_interval: int = 3,
                 headless: bool = False,
                 use_cookie: bool = True,
                 progress_callback: Optional[Callable] = None):
        """
        初始化爬虫

        Args:
            max_refresh: 最大刷新次数
            refresh_interval: 刷新间隔（秒）
            headless: 是否无头模式
            use_cookie: 是否使用 Cookie 登录
            progress_callback: 进度回调函数
        """
        self.max_refresh = max_refresh
        self.refresh_interval = refresh_interval
        self.headless = headless
        self.use_cookie = use_cookie
        self.progress_callback = progress_callback

        self.videos: List[VideoInfo] = []
        self.bvid_set = set()  # 用于去重
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def _report_progress(self, message: str, level: str = "info"):
        """报告进度"""
        if self.progress_callback:
            await self.progress_callback(message, level)
        else:
            prefix = {
                "info": "ℹ️",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
            }.get(level, "📌")
            print(f"{prefix} {message}")

    def _extract_bvid(self, url: str) -> Optional[str]:
        """从 URL 中提取 BV 号"""
        if not url:
            return None

        # 匹配 BV 号格式
        match = re.search(r'(BV[\w]+)', url)
        if match:
            return match.group(1)
        return None

    async def _setup_cookies(self):
        """设置 Cookie"""
        if not self.use_cookie:
            return

        if get_cookie is None:
            await self._report_progress("Cookie 管理器不可用", "warning")
            return

        if not check_cookie('bilibili'):
            await self._report_progress("B站 Cookie 未配置", "warning")
            return

        cookie_str = get_cookie('bilibili', 'string')
        if not cookie_str:
            await self._report_progress("获取 Cookie 失败", "warning")
            return

        # 解析 Cookie 字符串
        cookies = []
        for part in cookie_str.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.bilibili.com',
                    'path': '/',
                })

        if cookies:
            await self.page.context.add_cookies(cookies)
            await self._report_progress(f"已设置 {len(cookies)} 个 Cookie", "success")

    async def _parse_video_cards(self) -> List[VideoInfo]:
        """解析当前页面的视频卡片"""
        videos = []

        try:
            # 等待推荐视频加载
            await self.page.wait_for_selector(SELECTORS["video_card"], timeout=10000)

            # 获取所有视频卡片
            cards = await self.page.query_selector_all(SELECTORS["video_card"])

            await self._report_progress(f"找到 {len(cards)} 个视频卡片", "info")

            for card in cards:
                try:
                    # 获取视频链接
                    video_url = await card.get_attribute("href")
                    if not video_url:
                        continue

                    # 处理相对链接
                    if video_url.startswith("//"):
                        video_url = "https:" + video_url
                    elif video_url.startswith("/"):
                        video_url = "https://www.bilibili.com" + video_url

                    # 提取 BV 号
                    bvid = self._extract_bvid(video_url)
                    if not bvid:
                        continue

                    # 去重
                    if bvid in self.bvid_set:
                        continue
                    self.bvid_set.add(bvid)

                    # 获取标题
                    title_elem = await card.query_selector(SELECTORS["title"])
                    title = await title_elem.inner_text() if title_elem else "未知标题"
                    title = title.strip()

                    # 获取 UP 主信息
                    uploader = "未知UP主"
                    uploader_url = ""

                    # 尝试多种选择器
                    for selector in [".up-name", ".author-name", ".info--author"]:
                        uploader_elem = await card.query_selector(selector)
                        if uploader_elem:
                            # 检查是否有链接
                            uploader_link = await uploader_elem.query_selector("a")
                            if uploader_link:
                                uploader = await uploader_link.inner_text()
                                uploader_url_attr = await uploader_link.get_attribute("href")
                                if uploader_url_attr:
                                    if uploader_url_attr.startswith("//"):
                                        uploader_url = "https:" + uploader_url_attr
                                    elif uploader_url_attr.startswith("/"):
                                        uploader_url = "https://www.bilibili.com" + uploader_url_attr
                                    else:
                                        uploader_url = uploader_url_attr
                            else:
                                uploader = await uploader_elem.inner_text()
                            break

                    uploader = uploader.strip()

                    # 检查是否需要排除（直播、番剧等）
                    should_exclude = False
                    for exclude_selector in SELECTORS["exclude_selectors"]:
                        exclude_elem = await card.query_selector(exclude_selector)
                        if exclude_elem:
                            should_exclude = True
                            break

                    if should_exclude:
                        continue

                    # 创建视频信息
                    video = VideoInfo(
                        bvid=bvid,
                        title=title,
                        uploader=uploader,
                        uploader_url=uploader_url,
                        video_url=video_url,
                    )
                    videos.append(video)

                except Exception as e:
                    # 跳过解析失败的卡片
                    continue

        except Exception as e:
            await self._report_progress(f"解析视频卡片失败: {e}", "error")

        return videos

    async def _click_refresh_button(self) -> bool:
        """点击刷新按钮"""
        try:
            # 尝试多种选择器
            for selector in [SELECTORS["refresh_button"], "button:has-text('换一换')",
                           ".refresh-btn", ".feed-refresh"]:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        await button.click()
                        await asyncio.sleep(0.5)
                        return True
                except Exception:
                    continue

            # 如果找不到刷新按钮，尝试直接刷新页面
            await self._report_progress("未找到刷新按钮，尝试直接刷新页面", "warning")
            await self.page.reload()
            return True

        except Exception as e:
            await self._report_progress(f"点击刷新按钮失败: {e}", "error")
            return False

    async def start(self):
        """启动爬虫"""
        self.playwright = await async_playwright().start()

        # 启动浏览器
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )

        # 创建上下文
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 创建页面
        self.page = await context.new_page()

        # 设置 Cookie
        await self._setup_cookies()

        # 访问首页
        await self._report_progress("正在访问 B 站首页...", "info")
        await self.page.goto(SCRAPER_CONFIG["bili_homepage"], wait_until="networkidle")
        await self._report_progress("首页加载完成", "success")

    async def scrape(self) -> List[VideoInfo]:
        """开始采集"""
        if not self.page:
            await self.start()

        all_videos = []

        for i in range(self.max_refresh):
            round_num = i + 1
            await self._report_progress(f"\n--- 第 {round_num}/{self.max_refresh} 轮采集 ---", "info")

            # 解析当前页面
            videos = await self._parse_video_cards()
            await self._report_progress(f"第 {round_num} 轮采集到 {len(videos)} 个新视频", "success")

            all_videos.extend(videos)
            self.videos.extend(videos)

            # 如果不是最后一轮，点击刷新
            if i < self.max_refresh - 1:
                await self._report_progress(f"等待 {self.refresh_interval} 秒后刷新...", "info")
                await asyncio.sleep(self.refresh_interval)

                refresh_success = await self._click_refresh_button()
                if not refresh_success:
                    await self._report_progress("刷新失败，停止采集", "error")
                    break

                # 等待新内容加载
                await asyncio.sleep(2)

        return all_videos

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def get_videos(self) -> List[VideoInfo]:
        """获取采集的视频列表"""
        return self.videos

    def get_unique_count(self) -> int:
        """获取去重后的视频数量"""
        return len(self.bvid_set)


# ==================== 数据存储 ====================

def save_to_csv(videos: List[VideoInfo], output_path: str):
    """保存视频信息到 CSV 文件"""
    import csv

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        if not videos:
            return

        writer = csv.DictWriter(f, fieldnames=list(videos[0].to_dict().keys()))
        writer.writeheader()

        for video in videos:
            writer.writerow(video.to_dict())

    print(f"✅ 数据已保存到: {output_file}")


def save_to_json(videos: List[VideoInfo], output_path: str):
    """保存视频信息到 JSON 文件"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "视频总数": len(videos),
        "唯一视频数": len(set(v.bvid for v in videos)),
        "视频列表": [v.to_dict() for v in videos]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 数据已保存到: {output_file}")


# ==================== AI 分析 ====================

async def analyze_with_ai(videos: List[VideoInfo], model: str = 'flash-lite') -> str:
    """使用 Gemini API 分析视频类型

    Args:
        videos: 视频列表
        model: Gemini 模型

    Returns:
        分析报告文本
    """
    try:
        from analysis.gemini_subtitle_summary import GeminiClient, GEMINI_MODELS
    except ImportError:
        return "❌ 无法导入 Gemini 客户端，请检查 analysis/gemini_subtitle_summary.py 是否存在"

    if not videos:
        return "❌ 没有视频可供分析"

    # 构建视频列表文本
    videos_text = ""
    for i, video in enumerate(videos, 1):
        videos_text += f"{i}. {video.title}\n   UP主: {video.uploader}\n   链接: {video.video_url}\n\n"

    prompt = f"""你是一个视频内容分析师。请分析以下B站首页推荐视频列表，将它们分类统计。

视频列表:
{videos_text}

请按以下格式输出（使用 Markdown 格式）:

## 视频类型分布
| 类型 | 数量 | 占比 |
|------|------|------|
| ... | ... | ... |

## 推荐偏好分析
[描述账号的推荐偏好，偏向哪些类型的内容]

## 高频 UP 主
| UP主 | 出现次数 |
|------|----------|
| ... | ... |

## 内容特色分析
[分析推荐内容的特点，如视频长度、更新时间、主题特点等]

视频类型参考分类:
- AI/大模型/科技
- 知识/社科/人文
- 财经/职场
- Vlog/旅行
- 数码评测
- 游戏娱乐
- 动漫/影视
- 音乐/舞蹈
- 美食/生活
- 社会纪实
- 其他

请确保分类准确，统计数据真实。"""

    try:
        client = GeminiClient(model=model)
        result = client.generate_content(prompt)

        if result['success']:
            return result['text']
        else:
            return f"❌ AI 分析失败: {result.get('error', '未知错误')}"

    except Exception as e:
        return f"❌ AI 分析异常: {str(e)}"


# ==================== 主程序 ====================

async def main_async(args):
    """异步主函数"""
    # 创建爬虫实例
    scraper = BiliHomepageScraper(
        max_refresh=args.refresh,
        refresh_interval=args.interval,
        headless=args.headless,
        use_cookie=not args.no_cookie,
    )

    try:
        # 启动爬虫
        await scraper.start()

        # 开始采集
        videos = await scraper.scrape()

        # 输出结果
        print("\n" + "=" * 60)
        print(f"📊 采集完成!")
        print(f"  总计采集: {len(videos)} 个视频")
        print(f"  唯一视频: {scraper.get_unique_count()} 个")
        print("=" * 60)

        # 保存数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(SCRAPER_CONFIG["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成输出文件名
        if args.output:
            csv_path = args.output
            json_path = args.output.replace('.csv', '.json')
        else:
            csv_path = output_dir / f"homepage_videos_{timestamp}.csv"
            json_path = output_dir / f"homepage_videos_{timestamp}.json"

        save_to_csv(videos, csv_path)
        save_to_json(videos, json_path)

        # AI 分析
        if args.analyze:
            print("\n" + "=" * 60)
            print("🤖 正在进行 AI 分析...")
            print("=" * 60)

            report = await analyze_with_ai(videos, args.model)

            # 保存分析报告
            report_path = output_dir / f"homepage_analysis_{timestamp}.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"# B站首页推荐分析报告\n\n")
                f.write(f"**采集时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**刷新次数**: {args.refresh}\n\n")
                f.write(f"**视频总数**: {len(videos)}\n\n")
                f.write(f"**唯一视频数**: {scraper.get_unique_count()}\n\n")
                f.write("---\n\n")
                f.write(report)

            print(f"\n✅ 分析报告已保存到: {report_path}")

            # 打印报告摘要
            print("\n" + "=" * 60)
            print("📋 分析报告:")
            print("=" * 60)
            print(report[:1000])
            if len(report) > 1000:
                print("...")
                print(f"\n(完整报告请查看: {report_path})")

    finally:
        await scraper.close()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="B站首页推荐流自动采集工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 基本采集
    python bili_homepage_scraper.py --refresh 10

    # 采集 + AI 分析
    python bili_homepage_scraper.py --refresh 10 --analyze

    # 指定输出文件
    python bili_homepage_scraper.py --refresh 5 --output my_homepage.csv

    # 测试模式（只采集一次）
    python bili_homepage_scraper.py --test

    # 无头模式
    python bili_homepage_scraper.py --refresh 5 --headless
        """
    )

    parser.add_argument('-r', '--refresh', type=int, default=10,
                        help='刷新次数（默认: 10）')
    parser.add_argument('-i', '--interval', type=int, default=3,
                        help='刷新间隔秒数（默认: 3）')
    parser.add_argument('-o', '--output', type=str,
                        help='输出文件路径（默认: output/homepage/homepage_videos_时间戳.csv）')
    parser.add_argument('--analyze', action='store_true',
                        help='采集完成后进行 AI 分析')
    parser.add_argument('--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('--headless', action='store_true',
                        help='无头模式（不显示浏览器窗口）')
    parser.add_argument('--no-cookie', action='store_true',
                        help='不使用 Cookie 登录')
    parser.add_argument('--test', action='store_true',
                        help='测试模式（只采集一次）')

    args = parser.parse_args()

    # 测试模式
    if args.test:
        args.refresh = 1
        args.headless = False
        print("🧪 测试模式：只采集一次，显示浏览器窗口")

    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
