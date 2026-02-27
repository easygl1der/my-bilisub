# -*- coding: utf-8 -*-
"""
Gemini观点提取器测试脚本

使用方法:
    python test_gemini_extractor.py YOUR_GEMINI_API_KEY
"""
import json
import sys
from pathlib import Path

# 导入Gemini提取器
from platforms.comments.gemini_viewpoint_extractor import GeminiViewpointExtractor
from platforms.comments.comment_formatter import CommentFormatter


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_gemini_extractor.py YOUR_GEMINI_API_KEY")
        print("\nGet API Key from: https://makersuite.google.com/app/apikey")
        return

    api_key = sys.argv[1]

    # 读取B站评论数据
    json_file = Path('bili_comments_output/bili_comments_BV1UPZtBiEFS_20260227_001621.json')
    if not json_file.exists():
        print(f"[ERROR] File not found: {json_file}")
        return

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] Loaded {data.get('total_comments', 0)} comments from {data.get('video_id', 'unknown')}")

    # 创建Gemini提取器
    print("\n[INFO] Initializing Gemini extractor...")
    extractor = GeminiViewpointExtractor(api_key)

    if not extractor.client:
        print("[ERROR] Failed to initialize Gemini client")
        return

    # 提取观点
    print("[INFO] Extracting top 3 viewpoints...")
    result = extractor.extract_top_viewpoints(data, count=3)

    # 保存结果
    output_file = json_file.with_suffix('.viewpoints.json')
    extractor.save_result(result, output_file)

    # 生成Markdown总结
    summary_md = extractor.format_as_summary_markdown(result)
    summary_file = json_file.with_suffix('.viewpoints.md')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_md)
    print(f"[SAVED] Markdown summary: {summary_file}")

    # 显示结果摘要
    print("\n" + "=" * 60)
    print("EXTRACTION RESULT")
    print("=" * 60)
    print(f"Sentiment: {result.get('sentiment', 'unknown')}")
    print(f"Overall Summary: {result.get('overall_summary', 'N/A')}")
    print(f"\nViewpoints extracted: {len(result.get('viewpoints', []))}")

    for vp in result.get('viewpoints', []):
        print(f"\n  [{vp.get('rank', '?')}] {vp.get('title', 'N/A')}")
        print(f"      {vp.get('summary', 'N/A')}")


if __name__ == '__main__':
    main()
