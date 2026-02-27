# -*- coding: utf-8 -*-
"""
小红书评论格式化测试
"""
import json
from pathlib import Path
from platforms.comments.comment_formatter import CommentFormatter


def main():
    # 读取小红书评论
    json_file = Path('xhs_comments_output/xhs_comments_69a04393000000001600b991_20260227_013535.json')
    if not json_file.exists():
        print(f"[ERROR] File not found: {json_file}")
        return

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] Loaded {data.get('total_comments', 0)} comments from {data.get('note_id', 'unknown')}")

    # 创建格式化器
    formatter = CommentFormatter()

    # 生成对话链格式
    conversation = formatter.format_conversation_chain(data['comments'], platform='xiaohongshu')
    output_file = json_file.with_suffix('.conversation.md')
    formatter.save_to_file(conversation, output_file, 'md')

    # 生成可读Markdown格式
    readable = formatter.format_markdown(data['comments'], platform='xiaohongshu')
    output_file2 = json_file.with_suffix('.readable.md')
    formatter.save_to_file(readable, output_file2, 'md')

    print("\n[INFO] Formatting completed!")
    print(f"  - Conversation chain: {output_file.name}")
    print(f"  - Readable markdown: {output_file2.name}")


if __name__ == '__main__':
    main()
