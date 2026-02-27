# -*- coding: utf-8 -*-
"""
Gemini观点提取器 - 从评论中提取2-3个最有价值的观点

功能：
1. 使用Gemini API分析评论
2. 提取2-3个最有价值的观点
3. 生成视频总结材料
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class GeminiViewpointExtractor:
    """使用Gemini提取评论中的关键观点"""

    def __init__(self, api_key: str, model: str = 'gemini-2.0-flash-exp'):
        """
        初始化Gemini客户端

        Args:
            api_key: Google API Key
            model: 模型名称（默认gemini-2.0-flash-exp）
        """
        self.api_key = api_key
        self.model = model
        self._init_client()

    def _init_client(self):
        """初始化Gemini客户端"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
            print(f"[OK] Gemini client initialized (model: {self.model})")
        except ImportError:
            print("[ERROR] Please install google-generativeai: pip install google-generativeai")
            self.client = None
        except Exception as e:
            print(f"[ERROR] Gemini initialization failed: {e}")
            self.client = None

    def extract_top_viewpoints(self, comments_data: Dict, count: int = 3) -> Dict:
        """
        从评论中提取2-3个最有价值的观点

        Args:
            comments_data: 评论数据（包含对话链格式）
            count: 提取观点数量

        Returns:
            {
                "viewpoints": [...],
                "overall_summary": "...",
                "sentiment": "positive|neutral|negative"
            }
        """
        if not self.client:
            return {
                'error': 'Gemini客户端未初始化',
                'viewpoints': [],
                'overall_summary': '',
                'sentiment': 'neutral'
            }

        print(f"\n[INFO] Extracting {count} top viewpoints from comments...")

        # 1. 转换为对话链格式
        conversation_chain = self._format_as_conversation_chain(comments_data, count=count*10)

        # 2. 构建Gemini提示词
        prompt = self._build_prompt(conversation_chain, count)

        # 3. 调用Gemini API
        try:
            response = self.client.generate_content(prompt)
            result_text = response.text

            # 4. 解析结果
            result = self._parse_result(result_text, comments_data)
            result['extract_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result['model'] = self.model

            print("[OK] Viewpoint extraction completed")
            return result

        except Exception as e:
            print(f"[ERROR] Gemini API call failed: {e}")
            return {
                'error': str(e),
                'viewpoints': [],
                'overall_summary': '',
                'sentiment': 'neutral'
            }

    def _format_as_conversation_chain(self, comments_data: Dict, count: int = 30) -> str:
        """
        将评论数据格式化为对话链文本

        Args:
            comments_data: 评论数据
            count: 最多转换的评论数

        Returns:
            对话链文本
        """
        from platforms.comments.comment_formatter import CommentFormatter

        formatter = CommentFormatter()
        return formatter.format_conversation_chain(
            comments_data.get('comments', []),
            comments_data.get('platform', 'unknown'),
            max_comments=count
        )

    def _build_prompt(self, conversation_chain: str, count: int = 3) -> str:
        """
        构建Gemini提示词

        Args:
            conversation_chain: 对话链文本
            count: 提取观点数量

        Returns:
            提示词
        """
        return f"""你是一个专业的观点分析师，需要从评论区提取最有价值的内容。

## 待分析的评论和讨论

{conversation_chain}

## 任务要求
从上述评论中提取**{count}个最有价值的观点**，这些观点应该：
1. 有较高的点赞数支持
2. 内容有实质性和见解
3. 代表了社区的主要共识或争议点
4. 能够丰富视频/笔记总结的价值

## 输出格式
请严格按以下JSON格式输出：

```json
{{
  "viewpoints": [
    {{
      "rank": 1,
      "title": "观点标题（简短概括）",
      "summary": "观点摘要（100字以内）",
      "supporting_comment": {{
        "author": "作者名",
        "content": "完整评论内容",
        "likes": 赞数
      }},
      "reasoning": "为什么这个观点有价值（50字以内）"
    }},
    {{
      "rank": 2,
      ...
    }}
  ],
  "overall_summary": "评论区整体观点总结（100字以内）",
  "sentiment": "positive|neutral|negative"
}}
```

请开始分析。
"""

    def _parse_result(self, result_text: str, comments_data: Dict) -> Dict:
        """
        解析Gemini返回的JSON结果

        Args:
            result_text: Gemini返回的文本
            comments_data: 原始评论数据

        Returns:
            解析后的结果
        """
        # 提取JSON部分
        json_match = re.search(r'```json\n(.*?)\n```', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个文本
            json_str = result_text

        try:
            result = json.loads(json_str)

            # 添加元数据
            result['metadata'] = {
                'platform': comments_data.get('platform', 'unknown'),
                'total_comments': len(comments_data.get('comments', [])),
                'raw_response': result_text[:500]  # 保存原始响应片段
            }

            return result
        except json.JSONDecodeError as e:
            print(f"[WARN] JSON parsing failed: {e}")
            return {
                'error': 'JSON解析失败',
                'raw_text': result_text,
                'viewpoints': [],
                'overall_summary': '',
                'sentiment': 'neutral'
            }

    def save_result(self, result: Dict, output_path: Path):
        """
        保存提取结果到文件

        Args:
            result: 提取结果
            output_path: 输出文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        try:
            print(f"[SAVED] {output_path}")
        except UnicodeEncodeError:
            print(f"[SAVED] {output_path.as_posix()}")
        return output_path

    def format_as_summary_markdown(self, result: Dict) -> str:
        """
        将提取结果格式化为Markdown总结

        Args:
            result: 提取结果

        Returns:
            Markdown文本
        """
        output = []

        output.append("# 评论观点提取结果\n")
        output.append(f"**提取时间**: {result.get('extract_time', '未知')}")
        output.append(f"**模型**: {result.get('model', '未知')}")
        output.append(f"**整体情感**: {result.get('sentiment', '未知')}")

        overall = result.get('overall_summary', '')
        if overall:
            output.append(f"\n## 整体总结")
            output.append(overall)

        viewpoints = result.get('viewpoints', [])
        if viewpoints:
            output.append(f"\n## 核心观点 ({len(viewpoints)})\n")

            for vp in viewpoints:
                rank = vp.get('rank', 0)
                title = vp.get('title', '')
                summary = vp.get('summary', '')
                supporting = vp.get('supporting_comment', {})
                reasoning = vp.get('reasoning', '')

                output.append(f"### 观点 {rank}: {title}")
                output.append(f"**摘要**: {summary}")
                output.append(f"**理由**: {reasoning}")

                if supporting:
                    author = supporting.get('author', '未知')
                    likes = supporting.get('likes', 0)
                    content = supporting.get('content', '')
                    output.append(f"\n**支撑评论**:")
                    output.append(f"- 作者: {author}")
                    output.append(f"- 点赞: {likes}")
                    output.append(f"- 内容: {content}")

                output.append("")

        return "\n".join(output)


# 命令行使用
if __name__ == "__main__":
    import sys
    import os

    # 示例用法
    if len(sys.argv) < 3:
        print("用法: python gemini_viewpoint_extractor.py <评论JSON文件> <API_KEY> [观点数量]")
        sys.exit(1)

    json_file = Path(sys.argv[1])
    api_key = sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    # 读取评论数据
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 创建提取器
    extractor = GeminiViewpointExtractor(api_key)

    # 提取观点
    result = extractor.extract_top_viewpoints(data, count=count)

    # 保存结果
    output_file = json_file.with_suffix('.viewpoints.json')
    extractor.save_result(result, output_file)

    # 生成Markdown总结
    summary_md = extractor.format_as_summary_markdown(result)
    summary_file = json_file.with_suffix('.viewpoints.md')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_md)
    try:
        print(f"[SAVED] Markdown summary: {summary_file}")
    except UnicodeEncodeError:
        print(f"[SAVED] Markdown summary: {summary_file.as_posix()}")
