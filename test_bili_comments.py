#!/usr/bin/env python3
"""测试获取B站视频评论"""
import requests
import json
import sys
import io

# Windows编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 视频信息
video_id = "GCuaGxeZQr6wndCDzE_rcg"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': f'https://www.bilibili.com/video/{video_id}',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def get_comments(oid, page=1):
    """获取评论"""
    url = 'https://api.bilibili.com/x/v2/reply/main'
    params = {
        'oid': oid,
        'type': 1,
        'mode': 3,
        'pagination_str': '{"offset":""}',
        'ps': 20,  # 每页数量
    }

    # 尝试使用不同的 SSL 配置
    session = requests.Session()
    session.verify = False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    resp = session.get(url, headers=headers, params=params, timeout=15)
    print(f"Status: {resp.status_code}")

    try:
        data = resp.json()
        if data.get('code') == 0:
            replies = data.get('data', {}).get('replies', [])
            print(f"✅ 获取到 {len(replies)} 条评论\n")

            comments = []
            for r in replies:
                member = r.get('member', {})
                content = r.get('content', {})
                comment = {
                    'content': content.get('message', ''),
                    'likes': r.get('like', 0),
                    'author': member.get('uname', ''),
                    'platform': 'bilibili'
                }
                comments.append(comment)

                # 预览
                msg = comment['content'][:60].replace('\n', ' ')
                print(f"[{comment['likes']}赞] {comment['author']}: {msg}...")

            return comments
        else:
            print(f"❌ 错误: {data.get('message')}")
            return []
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        print(f"Response: {resp.text[:500]}")
        return []

if __name__ == '__main__':
    print("="*60)
    print(f"获取B站视频评论: {video_id}")
    print("="*60 + "\n")

    comments = get_comments(video_id)

    if comments:
        print(f"\n✅ 成功获取 {len(comments)} 条评论")

        # 保存到 CSV
        import csv
        with open('bili_comments.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['author', 'content', 'likes', 'platform'])
            writer.writeheader()
            writer.writerows(comments)

        print(f"💾 已保存到 bili_comments.csv")
