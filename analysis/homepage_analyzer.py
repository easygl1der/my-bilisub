#!/usr/bin/env python3
"""
B站首页推荐数据分析工具

功能：
- 读取采集的视频数据
- 使用 Gemini API 进行分类统计
- 生成推荐偏好分析报告

使用方法:
    # 分析 CSV 文件
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv

    # 分析 JSON 文件
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.json

    # 指定模型
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv --model flash

    # 指定输出文件
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv --output report.md
"""

import sys
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Windows编码修复
if sys.platform == 'win32' and sys.stdout.isatty():
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        # 如果 stdout 已经关闭或不可用，跳过修复
        pass

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入 Gemini 客户端
try:
    from analysis.gemini_subtitle_summary import GeminiClient, GEMINI_MODELS
except ImportError:
    print("❌ 无法导入 Gemini 客户端")
    print("请确保 analysis/gemini_subtitle_summary.py 存在")
    sys.exit(1)


# ==================== 数据读取 ====================

def load_videos_from_csv(csv_path: str) -> List[Dict]:
    """从 CSV 文件读取视频数据"""
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
                'timestamp': row.get('timestamp', ''),
            })

    return videos


def load_videos_from_json(json_path: str) -> List[Dict]:
    """从 JSON 文件读取视频数据"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('视频列表', [])


def load_videos(input_path: str) -> List[Dict]:
    """根据文件扩展名读取视频数据"""
    path = Path(input_path)

    if not path.exists():
        print(f"❌ 文件不存在: {input_path}")
        return []

    if path.suffix == '.csv':
        return load_videos_from_csv(input_path)
    elif path.suffix == '.json':
        return load_videos_from_json(input_path)
    else:
        print(f"❌ 不支持的文件格式: {path.suffix}")
        return []


# ==================== 统计分析 ====================

def calculate_statistics(videos: List[Dict]) -> Dict:
    """计算基础统计数据"""
    if not videos:
        return {}

    # 统计 UP 主出现次数
    uploader_count = {}
    for video in videos:
        uploader = video.get('uploader', '未知UP主')
        uploader_count[uploader] = uploader_count.get(uploader, 0) + 1

    # 排序
    top_uploaders = sorted(uploader_count.items(), key=lambda x: x[1], reverse=True)

    return {
        '总视频数': len(videos),
        '唯一UP主数': len(uploader_count),
        '高频UP主': top_uploaders[:10],
    }


def format_videos_list(videos: List[Dict], max_videos: int = 100) -> str:
    """格式化视频列表用于 AI 分析"""
    if not videos:
        return "无视频数据"

    # 限制数量避免 token 超限
    videos_to_analyze = videos[:max_videos]

    text = ""
    for i, video in enumerate(videos_to_analyze, 1):
        text += f"{i}. 标题: {video.get('title', '未知')}\n"
        text += f"   UP主: {video.get('uploader', '未知')}\n"
        text += f"   链接: {video.get('video_url', '')}\n\n"

    if len(videos) > max_videos:
        text += f"\n(还有 {len(videos) - max_videos} 个视频未显示)\n"

    return text


# ==================== AI 分析 ====================

def analyze_with_gemini(videos: List[Dict], model: str = 'flash-lite',
                        custom_prompt: str = None) -> Dict:
    """使用 Gemini API 分析视频类型

    Args:
        videos: 视频列表
        model: Gemini 模型
        custom_prompt: 自定义提示词

    Returns:
        {'report': '分析报告', 'success': bool, 'error': str}
    """
    if not videos:
        return {
            'report': '没有视频可供分析',
            'success': False,
            'error': '视频列表为空'
        }

    # 构建视频列表文本
    videos_text = format_videos_list(videos)

    # 默认提示词
    default_prompt = f"""你是一个视频内容分析师。请分析以下B站首页推荐视频列表，将它们分类统计。

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

    prompt = custom_prompt or default_prompt

    try:
        client = GeminiClient(model=model)
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


# ==================== 报告生成 ====================

def generate_report(videos: List[Dict], ai_report: str,
                    stats: Dict, model: str) -> str:
    """生成完整分析报告"""
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
        report_lines.append(f"   - 链接: {video.get('video_url', '')}")
        report_lines.append("")

    return "\n".join(report_lines)


def save_report(report: str, output_path: str):
    """保存报告到文件"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 报告已保存到: {output_file}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="B站首页推荐数据分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 分析 CSV 文件
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv

    # 指定模型
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv --model flash

    # 指定输出文件
    python homepage_analyzer.py --input output/homepage/homepage_videos_20250222.csv --output report.md
        """
    )

    parser.add_argument('-i', '--input', required=True,
                        help='输入文件路径（CSV 或 JSON）')
    parser.add_argument('-o', '--output', type=str,
                        help='输出报告路径（默认: output/homepage/homepage_analysis_时间戳.md）')
    parser.add_argument('-m', '--model', choices=['flash', 'flash-lite', 'pro'],
                        default='flash-lite', help='Gemini 模型（默认: flash-lite）')
    parser.add_argument('-p', '--prompt', type=str,
                        help='自定义分析提示词')
    parser.add_argument('--max-videos', type=int, default=100,
                        help='AI 分析的最大视频数（默认: 100）')

    args = parser.parse_args()

    # 读取数据
    print("=" * 60)
    print("📂 读取数据...")
    print("=" * 60)

    videos = load_videos(args.input)

    if not videos:
        print("❌ 没有读取到视频数据")
        return

    print(f"✅ 成功读取 {len(videos)} 个视频")

    # 计算基础统计
    stats = calculate_statistics(videos)

    print(f"\n📊 基础统计:")
    print(f"  总视频数: {stats['总视频数']}")
    print(f"  唯一UP主数: {stats['唯一UP主数']}")
    print(f"\n  高频 UP 主 (前5):")
    for uploader, count in stats['高频UP主'][:5]:
        print(f"    {uploader}: {count} 次")

    # AI 分析
    print("\n" + "=" * 60)
    print("🤖 正在进行 AI 分析...")
    print("=" * 60)

    # 限制分析的视频数量
    videos_to_analyze = videos[:args.max_videos]
    if len(videos) > args.max_videos:
        print(f"⚠️  视频数量过多，仅分析前 {args.max_videos} 个")

    result = analyze_with_gemini(videos_to_analyze, args.model, args.prompt)

    if not result['success']:
        print(f"❌ AI 分析失败: {result.get('error', '未知错误')}")
        return

    print(f"✅ 分析完成 (使用 tokens: {result.get('tokens', 0)})")

    # 生成报告
    report = generate_report(videos, result['report'], stats, args.model)

    # 保存报告
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/homepage/homepage_analysis_{timestamp}.md"

    save_report(report, output_path)

    # 打印报告摘要
    print("\n" + "=" * 60)
    print("📋 分析报告摘要:")
    print("=" * 60)

    # 打印前 2000 字符
    preview = result['report'][:2000]
    print(preview)
    if len(result['report']) > 2000:
        print("...")
        print(f"\n(完整报告请查看: {output_path})")

    print("\n" + "=" * 60)
    print("✅ 分析完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
