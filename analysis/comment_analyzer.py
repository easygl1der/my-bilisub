#!/usr/bin/env python3
"""
社交媒体评论区观点分析工具

功能：
1. 支持小红书、Reddit 等平台评论爬取
2. 按点赞数筛选高质量评论
3. 使用 AI (GLM/Gemini) 分析评论观点和论证质量
4. 过滤引战、无关、低质量评论
5. 生成结构化的观点分析报告

使用示例:
    # 分析小红书笔记评论
    python comment_analyzer.py -xhs "笔记URL" -o output.md

    # 分析 MediaCrawler 导出的评论
    python comment_analyzer.py -csv MediaCrawler/output/xhs/search/comments.csv -o output.md

    # 指定使用 GLM API
    python comment_analyzer.py -csv comments.csv --ai glm -o output.md
"""

import os
import sys
import time
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import requests

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

# Gemini 模型配置
GEMINI_MODELS = {
    'flash-lite': 'gemini-2.5-flash-lite',
    'flash': 'gemini-2.5-flash',
    'pro': 'gemini-2.5-pro',
}

# GLM 模型配置
GLM_MODELS = {
    'flash': 'glm-4-flash',
    'air': 'glm-4-air',
    'plus': 'glm-4-plus',
    'std': 'glm-4',
}

# 分析提示词
ANALYSIS_PROMPT = """你是一个专业的评论区观点分析师，擅长从评论中提取有价值的信息和观点。

请对以下评论列表进行分析，每条评论都标注了点赞数。

## 任务要求

1. **过滤低质量评论**：排除以下类型的评论
   - 引战、人身攻击、情绪宣泄
   - 无意义的灌水（"好"、"顶"、"666"等）
   - 与主题无关的内容
   - 纯粹的表情符号或重复内容

2. **评估论证质量**：对保留的评论进行评分
   - 论据是否充分（有事实、数据、逻辑推理）
   - 观点是否清晰明确
   - 是否有独到的见解
   - 是否提供了有用的信息

3. **观点聚类**：将相似观点归类

## 输出格式

请严格按照以下格式输出：

## 📊 分析概览
- 总评论数: [数量]
- 高质量评论数: [数量]
- 主要观点类别: [数量] 类

## 🎯 核心观点（按价值排序）

### 观点 1: [观点标题]
- **支持度**: ⭐⭐⭐⭐⭐ (5/5)
- **代表性评论**: "[引用最有力的一条评论]"
- **点赞数**: XXXX
- **论证质量**: [高/中/低]
- **分析**: [为什么这个观点有价值，论证是否扎实]

**相关评论摘要**:
- 评论1 (XXX赞): "[摘要]"
- 评论2 (XXX赞): "[摘要]"

### 观点 2: [观点标题]
[同上格式]

## 💎 值得关注的见解
[列出1-3条特别有洞察力的评论及其分析]

## ⚠️ 争议点/不同观点
[如果存在明显的对立观点，列出双方论据]

## 📝 总结
[用100-200字总结评论区的主要观点和共识]

---

## 待分析的评论列表：

{comments}

---

请开始分析。记住：只保留有实质内容的评论，重点关注点赞数高且论证充分的观点。
"""


# ==================== API 配置 ====================

def get_glm_api_key() -> str:
    """获取 GLM API Key"""
    # 优先从环境变量
    api_key = os.environ.get('ZHIPU_API_KEY') or os.environ.get('GLM_API_KEY')
    if api_key:
        return api_key

    # 从 config_api.py 获取
    try:
        from config.config_api import API_CONFIG
        api_key = API_CONFIG.get('zhipu', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


def get_gemini_api_key() -> str:
    """获取 Gemini API Key"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        return api_key

    try:
        from config_api import API_CONFIG
        api_key = API_CONFIG.get('gemini', {}).get('api_key')
        if api_key:
            return api_key
    except ImportError:
        pass

    return None


def call_glm_api(prompt: str, model: str = 'glm-4-flash') -> Tuple[str, dict]:
    """调用 GLM API"""
    api_key = get_glm_api_key()
    if not api_key:
        raise ValueError("未找到 GLM API Key")

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "top_p": 0.7,
        "max_tokens": 4000
    }

    response = requests.post(url, headers=headers, json=data, timeout=60)
    response.raise_for_status()
    result = response.json()

    content = result['choices'][0]['message']['content']

    # Token 信息
    token_info = {
        'prompt_tokens': result.get('usage', {}).get('prompt_tokens', 0),
        'candidates_tokens': result.get('usage', {}).get('completion_tokens', 0),
        'total_tokens': result.get('usage', {}).get('total_tokens', 0),
    }

    return content, token_info


def call_gemini_api(prompt: str, model: str = 'gemini-2.5-flash-lite') -> Tuple[str, dict]:
    """调用 Gemini API"""
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("未找到 Gemini API Key")

    import google.generativeai as genai
    genai.configure(api_key=api_key)

    gemini_model = genai.GenerativeModel(model)
    response = gemini_model.generate_content(prompt)

    token_info = {
        'prompt_tokens': 0,
        'candidates_tokens': 0,
        'total_tokens': 0
    }

    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        token_info['prompt_tokens'] = response.usage_metadata.prompt_token_count or 0
        token_info['candidates_tokens'] = response.usage_metadata.candidates_token_count or 0
        token_info['total_tokens'] = response.usage_metadata.total_token_count or 0

    return response.text, token_info


# ==================== 数据源 ====================

class CommentSource:
    """评论数据源基类"""

    def fetch_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """获取评论列表"""
        raise NotImplementedError


class CsvCommentSource(CommentSource):
    """CSV 文件评论数据源 - 支持 MediaCrawler 输出"""

    def __init__(self):
        self.pandas = None
        self._check_pandas()

    def _check_pandas(self):
        try:
            import pandas as pd
            self.pandas = pd
        except ImportError:
            pass

    def fetch_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """从 CSV/JSON 文件读取评论"""
        file_path = Path(url)

        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return []

        print(f"📂 从文件读取评论...")

        if file_path.suffix == '.json':
            return self._load_json(file_path, max_comments)
        elif file_path.suffix == '.csv':
            return self._load_csv(file_path, max_comments)
        else:
            print("❌ 不支持的文件格式，请使用 .csv 或 .json")
            return []

    def _load_json(self, file_path: Path, max_comments: int) -> List[Dict]:
        """加载 JSON 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        comments = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('comments', data.get('data', []))
        else:
            return []

        for item in items[:max_comments]:
            comments.append(self._normalize_comment(item))

        print(f"   ✅ 读取到 {len(comments)} 条评论")
        return comments

    def _load_csv(self, file_path: Path, max_comments: int) -> List[Dict]:
        """加载 CSV 文件"""
        if not self.pandas:
            print("⚠️  pandas 未安装，尝试使用 Python 内置 csv 模块")
            return self._load_csv_builtin(file_path, max_comments)

        try:
            df = self.pandas.read_csv(file_path)
            comments = []

            for _, row in df.head(max_comments).iterrows():
                comment = self._normalize_comment(row.to_dict())
                if comment.get('content'):
                    comments.append(comment)

            print(f"   ✅ 读取到 {len(comments)} 条评论")
            return comments
        except Exception as e:
            print(f"   ⚠️  pandas 读取失败: {e}，尝试使用内置 csv 模块")
            return self._load_csv_builtin(file_path, max_comments)

    def _load_csv_builtin(self, file_path: Path, max_comments: int) -> List[Dict]:
        """使用内置 csv 模块加载"""
        import csv
        comments = []

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_comments:
                    break
                comment = self._normalize_comment(row)
                if comment.get('content'):
                    comments.append(comment)

        print(f"   ✅ 读取到 {len(comments)} 条评论")
        return comments

    def _normalize_comment(self, item: Dict) -> Dict:
        """标准化评论格式 - 支持多种字段名"""
        # 内容字段 - 支持中英文
        content = (
            item.get('content') or item.get('text') or item.get('comment') or item.get('note_comment') or
            item.get('评论内容') or item.get('正文') or item.get('评论') or
            item.get('comment_text') or item.get('body') or ''
        )

        # 点赞字段 - 支持多种格式
        likes_field = (
            item.get('likes') or item.get('like_count') or item.get('likeCount') or
            item.get('sub_comment_count') or item.get('点赞数') or item.get('点赞') or
            item.get('liked_count') or item.get('score') or 0
        )

        # 处理点赞数
        try:
            likes = int(str(likes_field).replace(',', '').strip())
        except:
            likes = 0

        # 作者字段
        author = (
            item.get('author') or item.get('nickname') or item.get('user_name') or
            item.get('用户名') or item.get('昵称') or item.get('ip_location') or '[未知]'
        )

        return {
            'content': str(content).strip(),
            'likes': likes,
            'author': str(author),
            'platform': item.get('platform', 'csv')
        }


class MediaCrawlerSource(CommentSource):
    """MediaCrawler 输出目录数据源"""

    def __init__(self):
        self.media_crawler_path = Path(__file__).parent.parent / "MediaCrawler"

    def fetch_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """从 MediaCrawler 输出目录读取评论"""
        # url 可能是平台名称 (xhs, reddit 等)
        platform = url.lower().replace('-', '').replace('_', '')
        platform_map = {
            'xhs': 'xhs',
            'xiaohongshu': 'xhs',
            'reddit': 'reddit',
            'bili': 'bili',
            'bilibili': 'bili',
            'zhihu': 'zhihu',
        }

        platform = platform_map.get(platform, url)

        # 查找评论文件
        output_dir = self.media_crawler_path / "output" / platform
        if not output_dir.exists():
            print(f"❌ 未找到 MediaCrawler 输出目录: {output_dir}")
            return []

        # 查找 comments 文件
        comments_file = None
        for ext in ['csv', 'json']:
            candidate = output_dir / "search" / f"comments.{ext}"
            if candidate.exists():
                comments_file = candidate
                break

        if not comments_file:
            # 尝试查找任何评论文件
            for f in output_dir.rglob("*comment*"):
                if f.suffix in ['.csv', '.json']:
                    comments_file = f
                    break

        if not comments_file:
            print(f"❌ 在 {output_dir} 中未找到评论文件")
            print(f"   💡 请先运行 MediaCrawler 爬取评论")
            return []

        print(f"📂 找到评论文件: {comments_file.relative_to(self.media_crawler_path)}")

        # 使用 CsvCommentSource 加载
        csv_source = CsvCommentSource()
        return csv_source.fetch_comments(str(comments_file), max_comments)


class RedditCommentSource(CommentSource):
    """Reddit 评论数据源"""

    def __init__(self):
        self.praw = None
        self._check_praw()

    def _check_praw(self):
        try:
            import praw
            self.praw = praw
        except ImportError:
            pass

    def fetch_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """从 Reddit 获取评论"""
        if not self.praw:
            print("⚠️  PRAW 未安装")
            print("   安装: pip install praw")
            return []

        print(f"📱 尝试从 Reddit 获取评论...")

        client_id = os.environ.get('REDDIT_CLIENT_ID')
        client_secret = os.environ.get('REDDIT_CLIENT_SECRET')

        if not client_id or not client_secret:
            print("❌ 未配置 Reddit API 凭证")
            print("   请设置环境变量 REDDIT_CLIENT_ID 和 REDDIT_CLIENT_SECRET")
            return []

        try:
            reddit = self.praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent='CommentAnalyzer/1.0'
            )

            match = re.search(r'/comments/([a-z0-9]+)', url)
            if match:
                submission = reddit.submission(id=match.group(1))
            else:
                submission = reddit.submission(url=url)

            submission.comments.replace_more(limit=0)

            comments = []
            for comment in submission.comments.list()[:max_comments]:
                if hasattr(comment, 'body') and hasattr(comment, 'score'):
                    comments.append({
                        'content': comment.body,
                        'likes': comment.score,
                        'author': str(comment.author) if comment.author else '[deleted]',
                        'platform': 'reddit'
                    })

            print(f"   ✅ 获取到 {len(comments)} 条评论")
            return comments

        except Exception as e:
            print(f"❌ Reddit 爬取失败: {e}")
            return []


class XhsCommentSource(CommentSource):
    """小红书评论数据源 - 通过 MediaCrawler"""

    def __init__(self):
        self.media_crawler_path = Path(__file__).parent.parent / "MediaCrawler"
        self.has_crawler = (self.media_crawler_path / "main.py").exists()

    def fetch_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """从小红书获取评论"""
        if not self.has_crawler:
            print("❌ MediaCrawler 不可用")
            return []

        print(f"📱 尝试从小红书获取评论...")
        print(f"   URL: {url}")

        # 检查是否已有缓存数据
        source = MediaCrawlerSource()
        comments = source.fetch_comments('xhs', max_comments)

        if comments:
            print(f"   ✅ 使用缓存的评论数据")
            return comments

        # 尝试运行 MediaCrawler
        print(f"\n   💡 未找到缓存的评论数据")
        print(f"   运行以下命令爬取小红书评论：")
        print(f"   ──────────────────────────────────────")
        print(f"   1. 编辑 MediaCrawler/config/base_config.py:")
        print(f"      - 设置 PLATFORM = \"xhs\"")
        print(f"      - 设置 CRAWLER_TYPE = \"detail\"")
        print(f"      - 设置 ENABLE_GET_COMMENTS = True")
        print(f"      - 设置 CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = {max_comments}")
        print(f"      - 在 XHS_SPECIFIED_NOTE_URL_LIST 添加笔记 URL")
        print(f"   ")
        print(f"   2. 运行爬虫:")
        print(f"      cd MediaCrawler && python main.py")
        print(f"   ")
        print(f"   3. 爬取完成后，运行:")
        print(f"      python comment_analyzer.py -mediacrawler xhs")
        print(f"   ──────────────────────────────────────")

        return []


# ==================== 评论分析器 ====================

class CommentAnalyzer:
    """评论分析器 - 支持 GLM 和 Gemini"""

    def __init__(self, ai_provider: str = 'glm', model: str = None):
        """
        初始化分析器

        Args:
            ai_provider: AI 提供商 ('glm' 或 'gemini')
            model: 模型名称（不指定则使用默认）
        """
        self.ai_provider = ai_provider

        if ai_provider == 'glm':
            self.model = model or 'flash'
            self.model_name = GLM_MODELS.get(self.model, GLM_MODELS['flash'])
            # 检查 API Key
            if not get_glm_api_key():
                raise ValueError("未找到 GLM API Key，请在 config_api.py 中配置或设置 ZHIPU_API_KEY 环境变量")
        else:
            self.model = model or 'flash-lite'
            self.model_name = GEMINI_MODELS.get(self.model, GEMINI_MODELS['flash-lite'])
            # 检查并配置 Gemini
            api_key = get_gemini_api_key()
            if not api_key:
                raise ValueError("未找到 Gemini API Key")
            import google.generativeai as genai
            genai.configure(api_key=api_key)

    def filter_comments(self, comments: List[Dict], min_likes: int = 0,
                        min_length: int = 10) -> List[Dict]:
        """过滤评论"""
        filtered = []
        for comment in comments:
            content = comment.get('content', '').strip()
            likes = comment.get('likes', 0)

            if len(content) < min_length:
                continue
            if likes < min_likes:
                continue

            filtered.append(comment)

        # 按点赞数排序
        filtered.sort(key=lambda x: x.get('likes', 0), reverse=True)
        return filtered

    def analyze_comments(self, comments: List[Dict]) -> Tuple[str, dict]:
        """使用 AI 分析评论"""
        if not comments:
            return "没有可分析的评论", {}

        comment_text = self._format_comments(comments)
        prompt = ANALYSIS_PROMPT.format(comments=comment_text)

        print(f"   └─ 使用模型: {self.ai_provider.upper()} {self.model_name}")
        print(f"   └─ 分析中...")

        if self.ai_provider == 'glm':
            return call_glm_api(prompt, self.model_name)
        else:
            return call_gemini_api(prompt, self.model_name)

    def _format_comments(self, comments: List[Dict]) -> str:
        """格式化评论为文本"""
        lines = []
        for i, comment in enumerate(comments, 1):
            content = comment.get('content', '')
            likes = comment.get('likes', 0)
            author = comment.get('author', '[未知]')

            # 清理内容
            content = re.sub(r'\s+', ' ', content).strip()

            lines.append(f"{i}. [{likes}赞] {author}: {content}")

        return '\n\n'.join(lines)


# ==================== 输出管理 ====================

def save_report(comments: List[Dict], analysis: str, output_path: str,
                source_url: str = "", token_info: dict = None, ai_provider: str = 'glm'):
    """保存分析报告"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        # 头部
        f.write(f"# 评论区观点分析报告\n\n")

        # 元信息
        f.write(f"## 📌 元信息\n\n")
        f.write(f"| 项目 | 内容 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| **分析时间** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write(f"| **AI 模型** | {ai_provider.upper()} |\n")
        f.write(f"| **评论总数** | {len(comments)} |\n")

        if source_url:
            f.write(f"| **来源** | {source_url} |\n")

        if token_info and token_info.get('total_tokens', 0) > 0:
            f.write(f"| **Token 使用** | 输入: {token_info.get('prompt_tokens', 0):,} | 输出: {token_info.get('candidates_tokens', 0):,} | **总计: {token_info.get('total_tokens', 0):,}** |\n")

        f.write(f"\n---\n\n")

        # 分析结果
        f.write(analysis)

    print(f"   └─ 💾 报告已保存: {output_path}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="社交媒体评论区观点分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 分析 CSV/JSON 文件:
   python comment_analyzer.py -csv comments.csv -o output.md

2. 使用 MediaCrawler 输出:
   python comment_analyzer.py -mediacrawler xhs -o output.md

3. 指定 AI 提供商:
   python comment_analyzer.py -csv comments.csv --ai gemini -o output.md

4. 设置最小点赞数:
   python comment_analyzer.py -csv comments.csv --min-likes 10 -o output.md
        """
    )

    # 数据源选项
    parser.add_argument('-csv', '--csv-file', help='CSV/JSON 评论文件路径')
    parser.add_argument('-mediacrawler', metavar='PLATFORM',
                        help='从 MediaCrawler 输出读取 (xhs/reddit/bili/zhihu)')
    parser.add_argument('-xhs', '--xiaohongshu', help='小红书笔记 URL (需要先爬取)')
    parser.add_argument('-reddit', help='Reddit 帖子 URL')

    # AI 选项
    parser.add_argument('--ai', choices=['glm', 'gemini'], default='glm',
                        help='AI 提供商（默认: glm，因为你有 GLM API Key）')
    parser.add_argument('--model', help='指定模型（glm: flash/air/plus, gemini: flash/flash-lite/pro）')

    # 过滤选项
    parser.add_argument('-n', '--max-comments', type=int, default=50,
                        help='最大分析评论数（默认: 50）')
    parser.add_argument('--min-likes', type=int, default=0,
                        help='最小点赞数（默认: 0）')
    parser.add_argument('--min-length', type=int, default=10,
                        help='最小评论长度（默认: 10）')

    # 输出选项
    parser.add_argument('-o', '--output', default='comment_analysis.md',
                        help='输出文件路径（默认: comment_analysis.md）')

    args = parser.parse_args()

    # 检查数据源
    if not any([args.csv_file, args.mediacrawler, args.xiaohongshu, args.reddit]):
        parser.print_help()
        print("\n❌ 请指定至少一个数据源 (-csv / -mediacrawler / -xhs / -reddit)")
        return

    # 确定数据源
    source_url = ""
    source: CommentSource = None

    if args.csv_file:
        source = CsvCommentSource()
        source_url = args.csv_file
        print(f"\n{'='*80}")
        print(f"📂 数据源: CSV/JSON 文件")
        print(f"{'='*80}")
    elif args.mediacrawler:
        source = MediaCrawlerSource()
        source_url = f"MediaCrawler/{args.mediacrawler}"
        print(f"\n{'='*80}")
        print(f"📂 数据源: MediaCrawler ({args.mediacrawler})")
        print(f"{'='*80}")
    elif args.xiaohongshu:
        source = XhsCommentSource()
        source_url = args.xiaohongshu
        print(f"\n{'='*80}")
        print(f"📱 数据源: 小红书")
        print(f"{'='*80}")
    elif args.reddit:
        source = RedditCommentSource()
        source_url = args.reddit
        print(f"\n{'='*80}")
        print(f"📱 数据源: Reddit")
        print(f"{'='*80}")

    # 获取评论
    comments = source.fetch_comments(source_url, args.max_comments)

    if not comments:
        print("❌ 未能获取到评论")
        return

    print(f"\n📊 原始评论数: {len(comments)}")

    # 初始化分析器
    try:
        analyzer = CommentAnalyzer(ai_provider=args.ai, model=args.model)
    except ValueError as e:
        print(f"❌ {e}")
        return

    # 过滤评论
    filtered = analyzer.filter_comments(
        comments,
        min_likes=args.min_likes,
        min_length=args.min_length
    )

    print(f"📊 过滤后评论数: {len(filtered)}")

    if not filtered:
        print("❌ 没有符合条件的评论")
        return

    # 显示前几条评论预览
    print(f"\n📝 评论预览:")
    for i, comment in enumerate(filtered[:3], 1):
        content = comment.get('content', '')
        if len(content) > 80:
            content = content[:80] + "..."
        print(f"   {i}. [{comment.get('likes', 0)}赞] {content}")

    if len(filtered) > 3:
        print(f"   ... 还有 {len(filtered) - 3} 条")

    # 分析评论
    print(f"\n🔍 开始分析...")

    analysis, token_info = analyzer.analyze_comments(filtered)

    # 保存报告
    save_report(filtered, analysis, args.output, source_url, token_info, args.ai)

    # 显示 token 信息
    if token_info and token_info.get('total_tokens', 0) > 0:
        print(f"   └─ 📊 Token 使用: 输入 {token_info.get('prompt_tokens', 0):,} | "
              f"输出 {token_info.get('candidates_tokens', 0):,} | "
              f"总计 {token_info.get('total_tokens', 0):,}")

    print(f"\n✅ 分析完成!")


if __name__ == "__main__":
    main()
