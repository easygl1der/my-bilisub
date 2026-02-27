# -*- coding: utf-8 -*-
import json
from pathlib import Path
from platforms.comments.comment_formatter import CommentFormatter

# 读取B站评论JSON
with open('bili_comments_output/bili_comments_BV1UPZtBiEFS_20260227_001621.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 创建格式化器
formatter = CommentFormatter()

# 生成对话链格式
conversation = formatter.format_conversation_chain(data['comments'], 'bilibili', max_comments=5)

# 保存对话链
output_file = Path('bili_comments_output/bili_comments_BV1UPZtBiEFS_20260227_001621.conversation.md')
formatter.save_to_file(conversation, output_file, 'md')

print("Conversation chain formatted successfully!")
# print(conversation)  # Skip console output to avoid encoding issues
