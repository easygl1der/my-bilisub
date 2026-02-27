# -*- coding: utf-8 -*-
"""
评论格式化工具 - 为Jamelia分析准备数据

功能：
1. 格式化为对话链格式（适合AI分析）
2. 格式化为Markdown可读格式（适合人工阅读）
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CommentFormatter:
    """评论格式化器 - 为Jamelia分析准备数据"""

    def __init__(self):
        pass

    def format_conversation_chain(self, comments: List[Dict], platform: str,
                                  max_comments: int = 20) -> str:
        """
        格式化为对话链格式（适合AI分析）

        Args:
            comments: 评论列表（带嵌套结构）
            platform: 平台名称
            max_comments: 最多输出的评论数

        Returns:
            对话链文本
        """
        output = []

        # 元信息
        output.append(f"# 评论数据 - {platform.upper()}\n")
        output.append(f"**平台**: {platform}")
        output.append(f"**评论数**: {len(comments)}")
        output.append(f"**格式化时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"\n" + "=" * 50 + "\n")

        # 为每条评论生成对话链
        for i, comment in enumerate(comments[:max_comments], 1):
            output.append(f"\n## 评论 {i}")

            # 主评论
            author = comment.get('author', comment.get('nickname', '未知'))
            likes = comment.get('likes', comment.get('like_count', 0))
            content = comment.get('content', '')

            output.append(f"**作者**: {author}")
            output.append(f"**点赞**: {likes}")
            output.append(f"**内容**: {content}")

            # 提取对话链
            conversation = self._extract_conversation_chain(comment)
            if conversation:
                output.append(f"\n### 对话讨论:")
                for j, msg in enumerate(conversation, 1):
                    msg_author = msg['author']
                    msg_content = msg['content']
                    msg_likes = msg.get('likes', 0)
                    reply_to = msg.get('reply_to', '')

                    prefix = f"@{reply_to} " if reply_to else ""
                    output.append(f"  {j}. {prefix}{msg_author}: {msg_content} (赞: {msg_likes})")

            output.append(f"\n" + "-" * 30)

        return "\n".join(output)

    def format_markdown(self, comments: List[Dict], platform: str,
                       max_comments: int = 20) -> str:
        """
        格式化为Markdown可读格式

        Args:
            comments: 评论列表（带嵌套结构）
            platform: 平台名称
            max_comments: 最多输出的评论数

        Returns:
            Markdown文本
        """
        output = []

        # 元信息
        platform_display = platform if isinstance(platform, str) else str(platform)
        output.append(f"# {platform_display.upper()} 评论\n")
        output.append(f"**平台**: {platform_display}")
        output.append(f"**评论数**: {len(comments)}")
        output.append(f"**格式化时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"\n---\n")

        # 递归写入评论
        for i, comment in enumerate(comments[:max_comments], 1):
            self._write_comment_md(output, comment, i, level=0)
            output.append("")

        return "\n".join(output)

    def _write_comment_md(self, output: List[str], comment: Dict, index: int, level: int = 0):
        """递归写入单条评论为Markdown"""
        indent = "  " * level
        prefix = "├─ " if level > 0 else f"{index}. "

        # 评论信息
        author = comment.get('author', comment.get('nickname', '未知'))
        likes = comment.get('likes', comment.get('like_count', 0))
        content = comment.get('content', '')
        create_time = comment.get('create_time', 0)

        # 时间格式化
        if isinstance(create_time, (int, float)):
            time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
        else:
            time_str = create_time or "未知"

        output.append(f"{indent}{prefix}**{author}** (赞: {likes})")
        output.append(f"{indent}    时间: {time_str}")
        output.append(f"{indent}    内容: {content}")

        # 递归写入子评论
        replies = comment.get('replies', [])
        if replies:
            for j, reply in enumerate(replies, 1):
                self._write_comment_md(output, reply, j, level + 1)

    def _extract_conversation_chain(self, comment: Dict) -> List[Dict]:
        """
        提取对话链（包含主评论和所有回复）

        Args:
            comment: 根评论

        Returns:
            对话链列表（按点赞数排序）
        """
        chain = []

        # 主评论
        chain.append({
            'author': comment.get('author', comment.get('nickname', '未知')),
            'content': comment.get('content', ''),
            'likes': comment.get('likes', comment.get('like_count', 0))
        })

        # 所有回复
        replies = comment.get('replies', [])
        if replies:
            # 提取所有回复
            for reply in replies:
                chain.append({
                    'author': reply.get('author', reply.get('nickname', '未知')),
                    'content': reply.get('content', ''),
                    'likes': reply.get('likes', reply.get('like_count', 0)),
                    'reply_to': reply.get('reply_to_name', comment.get('author', comment.get('nickname', '')))
                })

        # 按点赞数排序（AI更容易理解热点）
        chain.sort(key=lambda x: x['likes'], reverse=True)
        return chain

    def save_to_file(self, data: str, output_path: Path, format: str = "md"):
        """
        保存格式化数据到文件

        Args:
            data: 格式化后的文本
            output_path: 输出文件路径
            format: 格式类型（md/txt）
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(data)

        try:
            print(f"[SAVED] {format.upper()}: {output_path}")
        except UnicodeEncodeError:
            print(f"[SAVED] {format.upper()}: {output_path.as_posix()}")
        return output_path

    def format_json_for_ai(self, comments: List[Dict], platform: str,
                        max_comments: int = 20) -> Dict:
        """
        格式化为AI友好的JSON结构

        Args:
            comments: 评论列表
            platform: 平台名称
            max_comments: 最多输出的评论数

        Returns:
            增强的JSON结构
        """
        enhanced_comments = []

        for comment in comments[:max_comments]:
            # 提取对话链
            conversation = self._extract_conversation_chain(comment)

            enhanced = {
                'author': comment.get('author', comment.get('nickname', '未知')),
                'content': comment.get('content', ''),
                'likes': comment.get('likes', comment.get('like_count', 0)),
                'conversation_chain': conversation,
                'reply_count': len(comment.get('replies', []))
            }
            enhanced_comments.append(enhanced)

        return {
            'platform': platform,
            'total_comments': len(comments),
            'formatted_comments': len(enhanced_comments),
            'comments': enhanced_comments,
            'format_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# 命令行使用
if __name__ == "__main__":
    import sys

    # 示例用法
    if len(sys.argv) > 1:
        json_file = Path(sys.argv[1])
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        platform = data.get('platform', data.get('video_id', 'unknown')[:3])
        comments = data.get('comments', [])

        formatter = CommentFormatter()

        # 生成对话链
        conversation = formatter.format_conversation_chain(comments, platform, max_comments=20)
        output_file = json_file.with_suffix('.conversation.md')
        formatter.save_to_file(conversation, output_file, 'md')

        # 生成Markdown
        markdown = formatter.format_markdown(comments, platform, max_comments=20)
        output_file_md = json_file.with_suffix('.readable.md')
        formatter.save_to_file(markdown, output_file_md, 'md')

        # 生成AI JSON
        ai_json = formatter.format_json_for_ai(comments, platform, max_comments=20)
        output_file_json = json_file.with_suffix('.ai.json')
        with open(output_file_json, 'w', encoding='utf-8') as f:
            json.dump(ai_json, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON已保存: {output_file_json}")
    else:
        print("用法: python comment_formatter.py <评论JSON文件>")
