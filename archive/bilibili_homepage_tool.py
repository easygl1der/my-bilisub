#!/usr/bin/env python3
"""
B站首页推荐采集与分析一体化工具

功能：
1. 自动爬取B站首页推荐视频
2. 收集视频标题、UP主、链接等完整信息
3. 使用 Gemini API 进行内容分类分析
4. 生成推荐偏好分析报告

使用方法:
    # 基本用法（爬取并分析）
    python bilibili_homepage_tool.py

    # 指定刷新次数和最大视频数
    python bilibili_homepage_tool.py --refresh 15 --max-videos 150

    # 仅爬取不分析
    python bilibili_homepage_tool.py --no-analyze

    # 使用已有数据进行分析
    python bilibili_homepage_tool.py --analyze-only --input output/homepage/homepage_videos_20250222.csv

    # 指定 Gemini 模型
    python bilibili_homepage_tool.py --model flash

    # 输出到指定文件
    python bilibili_homepage_tool.py --output my_report.md
"""

import sys
import json
import csv
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "MediaCrawler"))

# ==================== 配置 ====================

class Config:
    """全局配置"""
    # 首页爬取配置
    HOMEPAGE_URL = "https://www.bilibili.com"
    DEFAULT_REFRESH_COUNT = 10
    DEFAULT_MAX_VIDEOS = 100
    VIDEOS_PER_PAGE = 50

    # 浏览器配置
    HEADLESS = False  # 是否无头模式
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    # 输出配置
    OUTPUT_DIR = PROJECT_ROOT / "output" / "homepage"

    # Playwright配置
    PLAYWRIGHT_TIMEOUT = 30000
    PAGE_LOAD_TIMEOUT = 60000

    # 登录配置
    ENABLE_LOGIN = True  # 是否启用登录
    COOKIE_FILE = PROJECT_ROOT / "config" / "cookies.txt"  # Cookie文件路径
    USER_DATA_DIR = PROJECT_ROOT / "browser_data" / "bilibili_homepage"  # 浏览器用户数据目录


# ==================== 日志工具 ====================

class Logger:
    """简单日志工具"""
    @staticmethod
    def info(msg: str):
        print(f"[INFO] {msg}")

    @staticmethod
    def error(msg: str):
        print(f"[ERROR] {msg}")

    @staticmethod
    def success(msg: str):
        print(f"[SUCCESS] {msg}")

    @staticmethod
    def warning(msg: str):
        print(f"[WARNING] {msg}")


# ==================== 首页爬取器 ====================

class BilibiliHomepageCrawler:
    """B站首页推荐爬取器"""

    def __init__(self, refresh_count: int = 10, max_videos: int = 100,
                 headless: bool = False, auto_login: bool = True):
        self.refresh_count = refresh_count
        self.max_videos = max_videos
        self.headless = headless
        self.auto_login = auto_login
        self.all_videos = []
        self.seen_bvids = set()

    async def crawl(self) -> List[Dict]:
        """
        爬取B站首页推荐视频

        Returns:
            视频列表，每个视频包含:
            - bvid: 视频BV号
            - title: 视频标题
            - uploader: UP主名称
            - uploader_url: UP主主页链接
            - video_url: 视频链接
            - cover_url: 封面链接
            - timestamp: 采集时间戳
        """
        try:
            from playwright.async_api import async_playwright

            Logger.info("=" * 60)
            Logger.info("🚀 启动浏览器...")
            Logger.info("=" * 60)

            # 检查 Cookie 文件
            cookies = self._load_cookies()
            if cookies:
                Logger.info(f"✅ 已加载 {len(cookies)} 个 Cookie")
            else:
                Logger.warning("⚠️  未找到 Cookie，将使用未登录状态爬取")

            async with async_playwright() as p:
                # 启动浏览器，使用持久化上下文以保存登录状态
                user_data_dir = str(Config.USER_DATA_DIR)
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=self.headless,
                    channel="chrome",
                    viewport={"width": 1920, "height": 1080},
                    user_agent=Config.USER_AGENT,
                )

                # 如果有 Cookie 文件，添加到上下文
                if cookies:
                    await browser.add_cookies(cookies)

                page = browser.pages[0] if browser.pages else await browser.new_page()

                Logger.info("✅ 浏览器启动成功")
                Logger.info("")

                # 检查登录状态
                await page.goto(Config.HOMEPAGE_URL, wait_until="networkidle", timeout=Config.PAGE_LOAD_TIMEOUT)
                await asyncio.sleep(2)

                # 检查是否已登录
                is_logged_in = await self._check_login_status(page)
                if is_logged_in:
                    Logger.success("✅ 已检测到登录状态")
                else:
                    Logger.warning("⚠️  未检测到登录状态")
                    # 如果启用了自动登录且不是无头模式，尝试手动登录
                    if self.auto_login and not self.headless:
                        Logger.info("🔄 请在浏览器中手动登录B站...")
                        Logger.info("   登录成功后，程序将自动继续...")
                        Logger.info("   （如需跳过，请按 Ctrl+C）")
                        try:
                            # 等待用户登录（最多等待2分钟）
                            for i in range(120):
                                await asyncio.sleep(1)
                                is_logged_in = await self._check_login_status(page)
                                if is_logged_in:
                                    Logger.success("✅ 登录成功！")
                                    break
                                if i % 10 == 0 and i > 0:
                                    Logger.info(f"   等待登录中... ({i}/120秒)")
                            else:
                                Logger.warning("⏱️  等待登录超时，将使用未登录状态继续")
                        except KeyboardInterrupt:
                            Logger.info("⏭️  用户跳过登录，继续执行...")
                    else:
                        Logger.info("   提示：可以将 Cookie 保存到 config/cookies.txt 文件中以获取个性化推荐")
                        Logger.info("   或使用 --no-login 跳过登录提示")

                Logger.info("")
                Logger.info("=" * 60)
                Logger.info(f"📺 开始爬取首页推荐 (刷新{self.refresh_count}次, 最多{self.max_videos}个视频)")
                Logger.info("=" * 60)
                Logger.info("")

                # 多次刷新获取推荐
                for i in range(self.refresh_count):
                    await self._crawl_single_refresh(page, i + 1)

                    # 检查是否达到最大数量
                    if len(self.all_videos) >= self.max_videos:
                        Logger.info(f"✅ 已达到最大视频数限制: {self.max_videos}")
                        break

                    # 滚动页面等待加载更多
                    if i < self.refresh_count - 1:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(2)

                await browser.close()

            Logger.info("")
            Logger.info("=" * 60)
            Logger.success(f"✅ 爬取完成! 共收集 {len(self.all_videos)} 个视频")
            Logger.info("=" * 60)

            return self.all_videos

        except ImportError:
            Logger.error("❌ 未安装 playwright，请先安装: pip install playwright && playwright install chromium")
            return []
        except Exception as e:
            Logger.error(f"❌ 爬取失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_cookies(self):
        """从文件加载 Cookie"""
        cookie_file = Config.COOKIE_FILE
        if not cookie_file.exists():
            return []

        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_str = f.read().strip()

            if not cookie_str:
                return []

            # 解析 Cookie 字符串
            cookies = []
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    name, value = item.split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.bilibili.com',
                        'path': '/',
                    })

            return cookies

        except Exception as e:
            Logger.warning(f"⚠️  加载 Cookie 失败: {e}")
            return []

    async def _check_login_status(self, page):
        """检查是否已登录"""
        try:
            # 检查页面是否有用户头像或登录按钮
            await page.wait_for_selector(".header-entry-mini, .nav-user-info", timeout=5000)
            return True
        except:
            # 检查是否有登录按钮
            try:
                login_btn = await page.query_selector(".header-login-entry")
                if login_btn:
                    return False
            except:
                pass
            return False

    async def _crawl_single_refresh(self, page, refresh_num: int):
        """单次刷新爬取"""
        try:
            Logger.info(f"[{refresh_num}/{self.refresh_count}] 刷新页面...")

            # 访问首页
            await page.goto(Config.HOMEPAGE_URL, wait_until="networkidle", timeout=Config.PAGE_LOAD_TIMEOUT)
            await asyncio.sleep(2)

            # 等待视频卡片加载
            try:
                await page.wait_for_selector("a[href*='/video/BV']", timeout=10000)
            except:
                Logger.warning("未检测到视频卡片，尝试继续...")

            # 获取所有视频卡片
            video_cards = await page.query_selector_all("a[href*='/video/BV']")
            Logger.info(f"[{refresh_num}/{self.refresh_count}] 发现 {len(video_cards)} 个视频卡片")

            # 解析视频信息
            for idx, card in enumerate(video_cards[:Config.VIDEOS_PER_PAGE]):
                try:
                    video_info = await self._parse_video_card(card)
                    if video_info and video_info['bvid'] not in self.seen_bvids:
                        self.seen_bvids.add(video_info['bvid'])
                        self.all_videos.append(video_info)
                        Logger.info(f"  [{len(self.all_videos)}/{self.max_videos}] {video_info['title'][:40]}... @ {video_info['uploader']}")

                        if len(self.all_videos) >= self.max_videos:
                            break

                except Exception as e:
                    Logger.warning(f"  解析视频卡片失败: {e}")
                    continue

        except Exception as e:
            Logger.error(f"刷新 {refresh_num} 失败: {e}")

    async def _parse_video_card(self, card):
        """解析单个视频卡片"""
        try:
            # 获取视频链接
            href = await card.get_attribute("href")
            if not href or "/video/BV" not in href:
                return None

            # 提取BV号
            if "/video/BV" in href:
                bvid_part = href.split("/video/BV")[-1].split("?")[0].split("/")[0]
                bvid = "BV" + bvid_part
            else:
                return None

            # 检查是否是直播或广告
            is_live = await card.query_selector(".is-live")
            is_ad = await card.query_selector(".ad-card")
            if is_live or is_ad:
                return None

            # 获取视频标题 - 尝试多个选择器
            title = ""
            title_selectors = [
                ".info-title",
                ".title",
                "h3",
                ".video-title",
                "[class*='title']"
            ]
            for selector in title_selectors:
                title_elem = await card.query_selector(selector)
                if title_elem:
                    title = await title_elem.inner_text()
                    if title.strip():
                        break

            # 如果没找到标题，尝试获取属性
            if not title.strip():
                title = await card.get_attribute("title") or ""

            # 获取UP主信息
            uploader = ""
            uploader_url = ""
            uploader_selectors = [
                ".up-name",
                ".author-name",
                ".info--author a",
                ".author",
                "[class*='author'] a",
                "[class*='up']"
            ]
            for selector in uploader_selectors:
                uploader_elem = await card.query_selector(selector)
                if uploader_elem:
                    uploader = await uploader_elem.inner_text()
                    uploader_href = await uploader_elem.get_attribute("href")
                    if uploader_href:
                        uploader_url = uploader_href if uploader_href.startswith("http") else "https:" + uploader_href
                    if uploader.strip():
                        break

            # 获取封面
            cover_url = ""
            cover_elem = await card.query_selector("img")
            if cover_elem:
                cover_url = await cover_elem.get_attribute("src") or ""
                # 处理相对路径
                if cover_url and not cover_url.startswith("http"):
                    cover_url = urljoin("https:", cover_url)

            # 构建完整视频URL
            video_url = f"https://www.bilibili.com/video/{bvid}"

            return {
                "bvid": bvid,
                "title": title.strip(),
                "uploader": uploader.strip(),
                "uploader_url": uploader_url.strip(),
                "video_url": video_url,
                "cover_url": cover_url.strip(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        except Exception as e:
            Logger.warning(f"解析视频卡片失败: {e}")
            return None


# ==================== 数据存储 ====================

class DataStorage:
    """数据存储工具"""

    @staticmethod
    def save_to_csv(videos: List[Dict], output_path: str):
        """保存为CSV格式"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not videos:
            Logger.warning("没有视频数据可保存")
            return

        fieldnames = ['bvid', 'title', 'uploader', 'uploader_url', 'video_url', 'cover_url', 'timestamp']

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(videos)

        Logger.success(f"✅ CSV文件已保存: {output_file}")

    @staticmethod
    def save_to_json(videos: List[Dict], output_path: str):
        """保存为JSON格式"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "视频数量": len(videos),
            "视频列表": videos
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        Logger.success(f"✅ JSON文件已保存: {output_file}")

    @staticmethod
    def load_from_csv(csv_path: str) -> List[Dict]:
        """从CSV读取"""
        videos = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                videos.append({
                    'bvid': row.get('bvid', ''),
                    'title': row.get('title', ''),
                    'uploader': row.get('uploader', ''),
                    'uploader_url': row.get('uploader_url', ''),
                    'video_url': row.get('video_url', ''),
                    'cover_url': row.get('cover_url', ''),
                    'timestamp': row.get('timestamp', ''),
                })
        return videos

    @staticmethod
    def load_from_json(json_path: str) -> List[Dict]:
        """从JSON读取"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('视频列表', [])


# ==================== AI分析 ====================

class GeminiAnalyzer:
    """Gemini AI分析器"""

    def __init__(self, model: str = 'flash-lite'):
        self.model = model

    def analyze(self, videos: List[Dict]) -> Dict:
        """
        使用Gemini分析视频类型

        Returns:
            {'report': str, 'success': bool, 'error': str, 'tokens': int}
        """
        if not videos:
            return {
                'report': '没有视频可供分析',
                'success': False,
                'error': '视频列表为空'
            }

        # 导入Gemini客户端
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "analysis"))
            from gemini_subtitle_summary import GeminiClient
        except ImportError:
            return {
                'report': '',
                'success': False,
                'error': '无法导入Gemini客户端，请确保analysis/gemini_subtitle_summary.py存在'
            }

        # 构建视频列表文本
        videos_text = self._format_videos(videos)

        # 构建提示词
        prompt = f"""你是一个视频内容分析师。请分析以下B站首页推荐视频列表，将它们分类统计。

视频列表:
{videos_text}

请按以下格式输出（使用 Markdown 格式）:

## 视频类型分布
| 类型 | 数量 | 占比 |
|------|------|------|
| AI/大模型/科技 | XX | XX% |
| 知识/社科/人文 | XX | XX% |
| ... | ... | ... |

请根据视频标题和 UP 主准确分类，确保总数等于 {len(videos)}。

## 推荐偏好分析
[描述账号的推荐偏好，偏向哪些类型的内容]
- 主要兴趣领域: ...
- 内容深度: ...
- 视频风格: ...

## 高频 UP 主
| UP主 | 出现次数 | 代表内容 |
|------|----------|----------|
| ... | ... | ... |

## 内容特色分析
[分析推荐内容的特点，如:]
- 视频长度特点
- UP 主类型（个人/机构）
- 内容时效性
- 其他显著特征

## 建议与洞察
[基于分析结果给出建议]

---

**视频分类参考**:
- AI/大模型/科技: AI工具、大模型、编程、科技资讯
- 知识/社科/人文: 历史、哲学、社会观察、人文科普
- 财经/职场: 理财、职业发展、创业、商业分析
- Vlog/旅行: 生活记录、旅行、日常分享
- 数码评测: 手机、电脑、外设评测
- 游戏娱乐: 游戏视频、娱乐内容
- 动漫/影视: 动漫、电影、剧集相关
- 音乐/舞蹈: 音乐翻唱、舞蹈
- 美食/生活: 美食、生活技巧
- 社会纪实: 社会新闻、纪实报道
- 其他: 无法归类的"""

        try:
            client = GeminiClient(model=self.model)
            result = client.generate_content(prompt)

            if result['success']:
                return {
                    'report': result['text'],
                    'success': True,
                    'tokens': result.get('tokens', 0),
                }
            else:
                return {
                    'report': '',
                    'success': False,
                    'error': result.get('error', '未知错误')
                }

        except Exception as e:
            return {
                'report': '',
                'success': False,
                'error': str(e)
            }

    def _format_videos(self, videos: List[Dict]) -> str:
        """格式化视频列表"""
        text = ""
        for i, video in enumerate(videos, 1):
            text += f"{i}. 标题: {video.get('title', '未知')}\n"
            text += f"   UP主: {video.get('uploader', '未知')}\n"
            text += f"   链接: {video.get('video_url', '')}\n\n"
        return text


# ==================== 统计分析 ====================

def calculate_statistics(videos: List[Dict]) -> Dict:
    """计算基础统计数据"""
    if not videos:
        return {}

    # 统计UP主出现次数
    uploader_count = {}
    for video in videos:
        uploader = video.get('uploader', '未知UP主')
        uploader_count[uploader] = uploader_count.get(uploader, 0) + 1

    # 排序
    top_uploaders = sorted(uploader_count.items(), key=lambda x: x[1], reverse=True)

    return {
        '总视频数': len(videos),
        '唯一UP主数': len(uploader_count),
        '高频UP主': top_uploaders,
    }


# ==================== 报告生成 ====================

def generate_report(videos: List[Dict], ai_report: str,
                    stats: Dict, model: str) -> str:
    """生成完整分析报告"""
    from analysis.gemini_subtitle_summary import GEMINI_MODELS

    report_lines = [
        "# B站首页推荐分析报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**分析视频数**: {len(videos)}",
        f"**使用模型**: {GEMINI_MODELS.get(model, model)}",
        "",
        "---",
        "",
        "## 基础统计",
        "",
        f"- **总视频数**: {stats.get('总视频数', 0)}",
        f"- **唯一UP主数**: {stats.get('唯一UP主数', 0)}",
        "",
        "## 高频 UP 主 (前10)",
        "",
        "| UP主 | 出现次数 |",
        "|------|----------|",
    ]

    for uploader, count in stats.get('高频UP主', [])[:10]:
        report_lines.append(f"| {uploader} | {count} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## AI 分析报告",
        "",
        ai_report,
        "",
        "---",
        "",
        "## 附录: 完整视频列表",
        "",
    ])

    for i, video in enumerate(videos, 1):
        report_lines.append(f"{i}. **{video.get('title', '未知')}**")
        report_lines.append(f"   - UP主: {video.get('uploader', '未知')}")
        report_lines.append(f"   - BV号: {video.get('bvid', '')}")
        report_lines.append(f"   - 链接: {video.get('video_url', '')}")
        report_lines.append("")

    return "\n".join(report_lines)


# ==================== 主程序 ====================

async def main_async(args):
    """异步主函数"""
    # 确保输出目录存在
    Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = []

    # 如果是仅分析模式，从文件读取
    if args.analyze_only:
        if not args.input:
            Logger.error("❌ --analyze-only 模式需要指定 --input 参数")
            return

        Logger.info("=" * 60)
        Logger.info("📂 从文件读取数据...")
        Logger.info("=" * 60)

        input_path = Path(args.input)
        if not input_path.exists():
            Logger.error(f"❌ 文件不存在: {args.input}")
            return

        if input_path.suffix == '.csv':
            videos = DataStorage.load_from_csv(args.input)
        elif input_path.suffix == '.json':
            videos = DataStorage.load_from_json(args.input)
        else:
            Logger.error(f"❌ 不支持的文件格式: {input_path.suffix}")
            return

        if not videos:
            Logger.error("❌ 没有读取到视频数据")
            return

        Logger.success(f"✅ 成功读取 {len(videos)} 个视频")

    # 否则进行爬取
    else:
        crawler = BilibiliHomepageCrawler(
            refresh_count=args.refresh,
            max_videos=args.max_videos,
            headless=args.headless,
            auto_login=not args.no_login
        )
        videos = await crawler.crawl()

        # 保存爬取的数据
        if videos:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = Config.OUTPUT_DIR / f"homepage_videos_{timestamp}.csv"
            json_path = Config.OUTPUT_DIR / f"homepage_videos_{timestamp}.json"

            DataStorage.save_to_csv(videos, str(csv_path))
            DataStorage.save_to_json(videos, str(json_path))

    # 分析
    if not args.no_analyze and videos:
        # 计算统计
        stats = calculate_statistics(videos)

        Logger.info("")
        Logger.info("=" * 60)
        Logger.info("📊 基础统计:")
        Logger.info("=" * 60)
        Logger.info(f"  总视频数: {stats['总视频数']}")
        Logger.info(f"  唯一UP主数: {stats['唯一UP主数']}")
        Logger.info(f"  高频UP主 (前5):")
        for uploader, count in stats['高频UP主'][:5]:
            Logger.info(f"    {uploader}: {count} 次")

        Logger.info("")
        Logger.info("=" * 60)
        Logger.info("🤖 正在进行 AI 分析...")
        Logger.info("=" * 60)

        analyzer = GeminiAnalyzer(model=args.model)
        result = analyzer.analyze(videos)

        if not result['success']:
            Logger.error(f"❌ AI 分析失败: {result.get('error', '未知错误')}")
            return

        Logger.success(f"✅ 分析完成 (使用 tokens: {result.get('tokens', 0)})")

        # 生成报告
        report = generate_report(videos, result['report'], stats, args.model)

        # 保存报告
        if args.output:
            output_path = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.OUTPUT_DIR / f"homepage_analysis_{timestamp}.md"

        report_file = Path(output_path)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        Logger.success(f"✅ 报告已保存: {report_file}")

        # 打印报告摘要
        Logger.info("")
        Logger.info("=" * 60)
        Logger.info("📋 分析报告摘要:")
        Logger.info("=" * 60)
        preview = result['report'][:2000]
        print(preview)
        if len(result['report']) > 2000:
            print("...")
            print(f"\n(完整报告请查看: {report_file})")

    Logger.info("")
    Logger.info("=" * 60)
    Logger.success("✅ 全部完成!")
    Logger.info("=" * 60)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="B站首页推荐采集与分析一体化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 基本用法（爬取并分析）
    python bilibili_homepage_tool.py

    # 指定刷新次数和最大视频数
    python bilibili_homepage_tool.py --refresh 15 --max-videos 150

    # 仅爬取不分析
    python bilibili_homepage_tool.py --no-analyze

    # 使用已有数据进行分析
    python bilibili_homepage_tool.py --analyze-only --input output/homepage/homepage_videos_20250222.csv

    # 指定 Gemini 模型
    python bilibili_homepage_tool.py --model flash

    # 无头模式运行
    python bilibili_homepage_tool.py --headless
        """
    )

    # 爬取参数
    parser.add_argument('-r', '--refresh', type=int, default=Config.DEFAULT_REFRESH_COUNT,
                        help=f'首页刷新次数（默认: {Config.DEFAULT_REFRESH_COUNT}）')
    parser.add_argument('-M', '--max-videos', type=int, default=Config.DEFAULT_MAX_VIDEOS,
                        help=f'最大采集视频数（默认: {Config.DEFAULT_MAX_VIDEOS}）')
    parser.add_argument('--headless', action='store_true',
                        help='使用无头模式（后台运行浏览器）')
    parser.add_argument('--no-login', action='store_true',
                        help='跳过登录提示，直接使用未登录状态爬取')

    # 分析参数
    parser.add_argument('--no-analyze', action='store_true',
                        help='跳过AI分析，仅爬取数据')
    parser.add_argument('--analyze-only', action='store_true',
                        help='仅分析模式，不进行爬取')
    parser.add_argument('-i', '--input', type=str,
                        help='输入文件路径（用于--analyze-only模式）')
    parser.add_argument('-m', '--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')

    # 输出参数
    parser.add_argument('-o', '--output', type=str,
                        help='输出报告路径')

    args = parser.parse_args()

    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
