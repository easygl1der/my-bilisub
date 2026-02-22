#!/usr/bin/env python3
"""测试 AI 分析功能"""
import sys
sys.path.insert(0, '.')

def test_gemini():
    try:
        from analysis.gemini_subtitle_summary import GeminiClient

        print("测试 Gemini API...")
        client = GeminiClient(model='flash-lite')

        result = client.generate_content("你好，请简单回复：测试成功")

        print(f"成功: {result['success']}")
        print(f"回复: {result['text']}")
        return result['success']

    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    success = test_gemini()
    print(f"\n测试结果: {'通过' if success else '失败'}")
