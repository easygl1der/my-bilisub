#!/usr/bin/env python3
"""
B站评论爬取工具
使用已有的 Cookie 爬取指定视频的评论

使用方法:
    python fetch_bili_comments.py
"""

import json
import os
import sys
import time
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)


# ============================================================================
# 配置区域
# ============================================================================

# B站 Cookie - 从 config/cookies.txt 统一读取
BILI_COOKIE = ""
try:
    import sys
    from pathlib import Path

    # 添加 platforms/bilibili 目录到路径以导入 cookie_manager
    sys.path.insert(0, str(Path(__file__).parent))
    # 添加 config 目录到路径
    sys.path.insert(0, str(Path(__file__).parent.parent / "config"))

    # 简化Cookie读取逻辑
    cookie_file = Path(__file__).parent.parent / "config" / "cookies.txt"
    if cookie_file.exists():
        with open(cookie_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 查找bili相关的Cookie
        for line in content.split('\n'):
            if line.startswith('[bilibili]') or 'bilibili' in line.lower():
                parts = line.split('=', 1)
                if len(parts) == 2:
                    BILI_COOKIE += parts[0].strip() + '=' + parts[1].strip() + '; '
                # 如果找到bili部分，开始提取
                if line.strip() == '[bilibili]':
                    continue
                break
        BILI_COOKIE = BILI_COOKIE.rstrip('; ')

    if not BILI_COOKIE:
        print("⚠️ B站 Cookie 未配置，请在 config/cookies.txt 中添加 [bilibili] 部分")
    else:
        print("✅ 已加载 B站 Cookie")

except Exception as e:
    print(f"⚠️ 无法读取 Cookie 文件: {e}")

# 输出目录
OUTPUT_DIR = "bili_comments_output"

# 每页评论数
PAGE_SIZE = 20

# 请求延迟
REQUEST_DELAY = 1


# ============================================================================
# WBI 签名
# ============================================================================

def get_mixin_key(orig: str) -> str:
    """对 imgKey 和 subKey 进行字符顺序打乱编码"""
    mixin_key_enc_tab = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    return ''.join([orig[i] for i in mixin_key_enc_tab])[:32]


def get_wbi_keys() -> tuple:
    """获取最新的 img_key 和 sub_key"""
    headers = get_headers()
    try:
        resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers, timeout=10)
        resp.raise_for_status()
        json_content = resp.json()
        img_url = json_content['data']['wbi_img']['img_url']
        sub_url = json_content['data']['wbi_img']['sub_url']
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key
    except Exception as e:
        print(f"⚠️  获取WBI密钥失败: {e}")
        return '', ''


def sign_wbi_params(params: dict) -> dict:
    """为请求参数进行 wbi 签名"""
    img_key, sub_key = get_wbi_keys()
    if not img_key or not sub_key:
        return params

    mixin_key = get_mixin_key(img_key + sub_key)
    curr_time = round(time.time())
    params['wts'] = curr_time
    params = dict(sorted(params.items()))

    # 过滤 value 中的 "!'()*" 字符
    params = {
        k: ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
        for k, v in params.items()
    }
    query = urlencode(params)
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params['w_rid'] = wbi_sign
    return params


# ============================================================================
# HTTP 客户端
# ============================================================================

def get_headers():
    """获取请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Origin': 'https://www.bilibili.com',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Cookie': BILI_COOKIE,
        'x-requested-with': 'fetch',
    }


class BiliCommentClient:
    """B站评论客户端"""

    def __init__(self):
        self.headers = get_headers()

    def get_comments(self, video_id: str, max_count: int = 100) -> List[Dict]:
        """获取视频评论"""
        all_comments = []

        print(f"\n📺 开始爬取B站视频评论")
        print(f"   视频 ID: {video_id}")
        print(f"   目标数量: {max_count}\n")

        # 判断是 BV 号还是 AV 号
        if video_id.startswith('BV'):
            oid = self.bv_to_aid(video_id)
            if not oid:
                print("❌ 无法获取视频 AV 号")
                return []
        else:
            oid = video_id

        page = 1

        while len(all_comments) < max_count:
            print(f"   正在获取第 {page} 页...")

            try:
                comments = self._fetch_page(oid, page)
                if not comments:
                    break

                all_comments.extend(comments)
                print(f"   ✅ 获取到 {len(comments)} 条评论，总计 {len(all_comments)} 条")

                if len(comments) < PAGE_SIZE:
                    break

                page += 1
                time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"   ⚠️  获取失败: {e}")
                break

        return all_comments[:max_count]

    def _fetch_page(self, oid: int, page: int) -> List[Dict]:
        """获取一页评论"""
        # 使用旧版 API（不需要 WBI 签名）
        url = "https://api.bilibili.com/x/v2/reply"

        params = {
            'type': 1,
            'oid': oid,
            'mode': 3,  # 按热门排序
            'ps': PAGE_SIZE,
            'pn': page,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)

            data = response.json()

            if data.get('code') == 0:
                replies = data.get('data', {}).get('replies', [])
                if replies is None:
                    replies = []
                return self._parse_comments(replies)
            else:
                print(f"   ⚠️  API 错误: {data.get('message', '未知错误')}")
                return []

        except Exception as e:
            print(f"   ⚠️  请求异常: {e}")
            return []

    def _parse_comments(self, replies: List[Dict]) -> List[Dict]:
        """解析评论数据"""
        parsed = []

        for reply in replies:
            try:
                member = reply.get("member", {})
                if member is None:
                    member = {}
                content = reply.get("content", {})
                if content is None:
                    content = {}
                like_count = reply.get("like", 0)

                parsed.append({
                    "comment_id": reply.get("rpid", ""),
                    "content": content.get("message", ""),
                    "likes": like_count,
                    "author": member.get("uname", ""),
                    "create_time": reply.get("ctime", 0),
                    "platform": "bilibili"
                })
            except Exception as e:
                continue

        return parsed

    def bv_to_aid(self, bvid: str) -> Optional[int]:
        """将 BV 号转换为 AV 号"""
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            data = response.json()

            if data.get('code') == 0:
                aid = data.get('data', {}).get('aid')
                print(f"   ✅ BV 号转 AV 号: {bvid} -> av{aid}")
                return aid
        except Exception as e:
            print(f"   ⚠️  转换失败: {e}")

        return None


# ============================================================================
# URL 解析
# ============================================================================

def extract_video_id(url: str) -> Optional[str]:
    """从 URL 中提取视频 ID"""
    # B站 URL 格式:
    # https://www.bilibili.com/video/BV1xx411c7mD/
    # https://www.bilibili.com/video/av123456/
    # https://www.bilibili.com/video/b-GCuaGxeZQr6wndCDzE_rcg (Base64格式)
    # https://b23.tv/xxxxx

    # BV 号
    bv_match = re.search(r'BV([a-zA-Z0-9]{10})', url)
    if bv_match:
        return 'BV' + bv_match.group(1)

    # b- 格式 (Base64编码的视频ID)
    b_match = re.search(r'/video/b-([a-zA-Z0-9_-]+)', url)
    if b_match:
        return b_match.group(1)

    # 直接输入的视频ID
    if re.match(r'^[a-zA-Z0-9_-]{10,}$', url.strip()):
        return url.strip()

    # AV 号
    av_match = re.search(r'av(\d+)', url)
    if av_match:
        return av_match.group(1)

    return None


# ============================================================================
# 保存结果
# ============================================================================

def save_comments(comments: List[Dict], video_id: str) -> str:
    """保存评论到 CSV"""
    if not comments:
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = os.path.join(OUTPUT_DIR, f"bili_comments_{video_id}_{timestamp}.csv")

    import csv
    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['comment_id', 'author', 'content', 'likes', 'create_time', 'platform'])
        writer.writeheader()
        writer.writerows(comments)

    return csv_file


# ============================================================================
# 主程序
# ============================================================================

def main(url: str = None, count: int = None):
    """主程序"""
    print("\n" + "="*70)
    print("B站评论爬取工具")
    print("="*70)

    # 获取视频链接
    if not url:
        print("\n请输入B站视频链接")
        print("示例: https://www.bilibili.com/video/BV1xx411c7mD/\n")
        url = input("视频链接: ").strip()

    if not url:
        print("❌ 链接不能为空")
        return

    # 提取视频 ID
    video_id = extract_video_id(url)
    if not video_id:
        print("❌ 无法从链接中提取视频 ID")
        return

    print(f"\n✅ 视频 ID: {video_id}")

    # 获取评论数量
    if count:
        max_count = count
    else:
        try:
            count_input = input("\n要爬取多少条评论? (默认50): ").strip()
            max_count = int(count_input) if count_input else 50
        except:
            max_count = 50

    # 创建客户端
    client = BiliCommentClient()

    # 获取评论
    comments = client.get_comments(video_id, max_count)

    if not comments:
        print("\n❌ 未获取到评论")
        return

    print(f"\n✅ 成功获取 {len(comments)} 条评论")

    # 保存结果
    csv_file = save_comments(comments, video_id.replace('/', '_'))
    print(f"💾 已保存到: {csv_file}")

    # 显示预览
    print("\n📝 评论预览:")
    for i, comment in enumerate(comments[:5], 1):
        content = comment.get('content', '')[:80]
        if len(content) == 80:
            content += "..."
        print(f"   {i}. [{comment['likes']}赞] {comment['author']}: {content}")

    if len(comments) > 5:
        print(f"   ... 还有 {len(comments) - 5} 条")

    print("\n" + "="*70)
    print("✅ 完成！可以使用以下命令分析评论:")
    print(f"   python comment_analyzer.py -csv {csv_file} -o analysis.md")
    print("="*70)


if __name__ == "__main__":
    import sys
    # 支持命令行参数
    url = sys.argv[1] if len(sys.argv) > 1 else None
    count = int(sys.argv[2]) if len(sys.argv) > 2 else None

    try:
        main(url, count)
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
