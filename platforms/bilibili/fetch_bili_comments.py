#!/usr/bin/env python3
"""
B站评论爬取工具
使用已有的 Cookie 爬取指定视频的评论（按热度排序，获取最热评论）

使用方法:
    python fetch_bili_comments.py "视频链接" [评论数量]

示例:
    # 爬取前50条最热评论（默认）
    python fetch_bili_comments.py "https://www.bilibili.com/video/BV1UPZtBiEFS"

    # 爬取前20条最热评论
    python fetch_bili_comments.py "https://www.bilibili.com/video/BV1UPZtBiEFS" 20

    # 爬取全部最热评论
    python fetch_bili_comments.py "https://www.bilibili.com/video/BV1UPZtBiEFS" 0

    # 输出为 Markdown 格式
    python fetch_bili_comments.py "视频链接" -f md

    # 只爬取有点赞数的主评论
    python fetch_bili_comments.py "视频链接" --only-liked
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

    # 读取Cookie文件 - 从脚本路径往上两级到根目录
    script_dir = Path(__file__).resolve().parent
    # script_dir 是 platforms/bilibili
    # 往上两级：platforms/bilibili -> platforms -> 根目录
    root_dir = script_dir.parent.parent
    cookie_file = root_dir / "config" / "cookies.txt"

    if cookie_file.exists():
        with open(cookie_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 查找 [bilibili] 部分
        in_bilibili_section = False
        for line in content.split('\n'):
            line = line.strip()

            # 进入bilibili部分
            if line == '[bilibili]':
                in_bilibili_section = True
                continue
            # 退出bilibili部分
            elif line.startswith('['):
                in_bilibili_section = False
                continue
            # 收集Cookie
            elif in_bilibili_section and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                BILI_COOKIE += f"{key.strip()}={value.strip()}; "

        # 移除最后的分号和空格
        BILI_COOKIE = BILI_COOKIE.rstrip('; ')

    if BILI_COOKIE:
        print(f"✅ 已加载 B站 Cookie (长度: {len(BILI_COOKIE)} 字符)")
    else:
        print("⚠️ B站 Cookie 未配置，请在 config/cookies.txt 中添加 [bilibili] 部分")

except Exception as e:
    print(f"⚠️ 无法读取 Cookie 文件: {e}")

# 输出目录
OUTPUT_DIR = "bili_comments_output"

# 每页评论数
PAGE_SIZE = 20  # B站 API 页码限制

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

    def get_comments(self, video_id: str, max_count: int = 50, only_liked: bool = False) -> List[Dict]:
        """获取视频最热评论

        Args:
            video_id: 视频 ID（BV 或 AV 号）
            max_count: 最大评论数，默认 50 条最热评论
            only_liked: 是否只爬取有点赞数的主评论（默认 False）

        Returns:
            评论列表
        """
        print(f"\n📺 开始爬取B站视频最热评论")
        print(f"   视频 ID: {video_id}")
        print(f"   🔥 模式：收集评论后按点赞数排序")
        if only_liked:
            print(f"   🔍 过滤模式：仅爬取有点赞数的主评论")

        # 判断是 BV 号还是 AV 号
        if video_id.startswith('BV'):
            oid = self.bv_to_aid(video_id)
            if not oid:
                print("❌ 无法获取视频 AV 号")
                return []
        else:
            oid = video_id

        # 第一阶段：收集多页评论（默认爬取前10页）
        all_collected = []
        page = 1
        max_pages_to_fetch = 10  # 最多爬取10页（约200条评论）
        total_available = None

        print(f"\n   📥 第一阶段：收集评论...")
        while page <= max_pages_to_fetch:
            print(f"   正在获取第 {page} 页...")

            try:
                result = self._fetch_page(oid, page)
                comments = result.get('comments', [])

                # 获取总评论数（首次获取时）
                if total_available is None:
                    total_available = result.get('total_count', 0)
                    if total_available > 0:
                        print(f"   📊 视频共有 {total_available} 条主评论")
                    # 确定要爬取的页数
                    if total_available < PAGE_SIZE * max_pages_to_fetch:
                        max_pages_to_fetch = (total_available + PAGE_SIZE - 1) // PAGE_SIZE
                        print(f"   📄 将爬取 {max_pages_to_fetch} 页")

                if not comments:
                    print(f"   ✅ 第 {page} 页无评论，结束收集")
                    break

                all_collected.extend(comments)
                print(f"   ✅ 本页获取 {len(comments)} 条，累计 {len(all_collected)} 条")

                page += 1

            except Exception as e:
                print(f"   ⚠️  获取失败: {e}")
                break

        if not all_collected:
            print("   ❌ 未获取到任何评论")
            return []

        print(f"\n   📊 第二阶段：按点赞数排序...")

        # 第二阶段：按点赞数降序排序
        all_collected.sort(key=lambda x: x.get('likes', 0), reverse=True)

        # 统计点赞数分布
        if all_collected:
            max_likes = max(c.get('likes', 0) for c in all_collected)
            min_likes = min(c.get('likes', 0) for c in all_collected)
            avg_likes = sum(c.get('likes', 0) for c in all_collected) / len(all_collected)
            print(f"   📈 点赞统计：最高 {max_likes} 赞，最低 {min_likes} 赞，平均 {avg_likes:.1f} 赞")

        # 确定最终数量
        target_count = min(max_count if max_count else len(all_collected), len(all_collected))
        hot_comments = all_collected[:target_count]

        print(f"   ✅ 筛选出 {len(hot_comments)} 条最热评论")

        # 显示前3条最热评论预览
        print(f"\n   🔥 热评预览：")
        for i, comment in enumerate(hot_comments[:3], 1):
            content = comment.get('content', '')[:40]
            likes = comment.get('likes', 0)
            author = comment.get('author', '未知')
            print(f"      {i}. [{likes}赞] {author}: {content}{'...' if len(comment.get('content', '')) > 40 else ''}")

        # 第三阶段：为每条热评获取回复
        print(f"\n   💬 第三阶段：获取热评回复...")

        final_comments = []
        for i, comment in enumerate(hot_comments, 1):
            if i % 10 == 0 or i == len(hot_comments):
                print(f"   进度: {i}/{len(hot_comments)}")

            # 检查是否有点赞数要求
            if only_liked and comment.get('likes', 0) <= 0:
                continue

            # 获取子评论
            rpid = comment.get('comment_id')
            rcount = comment.get('rcount', 0)

            if rcount > 0:
                # 需要获取子评论，先用API获取
                sub_replies = self._fetch_replies(oid, int(rpid))
                comment['replies'] = sub_replies
            else:
                comment['replies'] = []

            final_comments.append(comment)

        print(f"\n   📈 最终统计：")
        print(f"      📊 总共筛选 {len(final_comments)} 条热评")
        print(f"      💬 包含子评论 {sum(1 for c in final_comments for _ in c.get('replies', []))} 条")

        return final_comments

    def _fetch_page(self, oid: int, page: int) -> Dict:
        """获取一页评论

        Returns:
            dict: {
                'comments': 评论列表,
                'total_count': 总评论数
            }
        """
        # 使用旧版 API（不需要 WBI 签名）
        url = "https://api.bilibili.com/x/v2/reply"

        params = {
            'type': 1,
            'oid': oid,
            'mode': 0,  # 按热度排序（获取最热评论）
            'ps': PAGE_SIZE,
            'pn': page,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)

            data = response.json()

            if data.get('code') == 0:
                replies = data.get('data', {}).get('replies', [])
                page_info = data.get('data', {}).get('page', {})
                total_count = page_info.get('count', 0)

                if replies is None:
                    replies = []

                return {
                    'comments': self._parse_comments(replies, oid=oid),
                    'total_count': total_count
                }
            else:
                print(f"   ⚠️  API 错误: {data.get('message', '未知错误')}")
                return {'comments': [], 'total_count': 0}

        except Exception as e:
            print(f"   ⚠️  请求异常: {e}")
            return {'comments': [], 'total_count': 0}

    def _fetch_replies(self, oid: int, root_rpid: int) -> List[Dict]:
        """获取指定评论的全部子评论

        Args:
            oid: 视频 ID（AV 号）
            root_rpid: 根评论 ID

        Returns:
            子评论列表
        """
        all_replies = []
        page = 1

        while True:
            url = "https://api.bilibili.com/x/v2/reply/reply"
            params = {
                'oid': oid,
                'root': root_rpid,
                'pn': page,
                'ps': PAGE_SIZE,
            }

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                data = response.json()

                if data.get('code') == 0:
                    replies_data = data.get('data', {}).get('replies', {})
                    page_info = data.get('data', {}).get('page', {})

                    # replies 是一个字典，key 是回复类型
                    for reply_type in replies_data.values():
                        if reply_type:
                            for reply in reply_type:
                                all_replies.append(reply)

                    # 检查是否还有更多页
                    if page_info.get('num', 0) <= page:
                        break

                    page += 1
                else:
                    break

            except Exception as e:
                print(f"      ⚠️  获取子评论失败: {e}")
                break

        return self._parse_comments(all_replies)

    def _parse_comment(self, reply: Dict, level: int = 0, oid: int = None) -> Dict:
        """解析单条评论（递归处理回复）

        Args:
            reply: 评论数据
            level: 评论层级
            oid: 视频 ID（用于获取子评论）
        """
        try:
            member = reply.get("member", {})
            if member is None:
                member = {}
            content = reply.get("content", {})
            if content is None:
                content = {}
            like_count = reply.get("like", 0)

            # 处理回复关系
            parent_rpid = reply.get("parent", 0)
            reply_to = None
            if parent_rpid and parent_rpid != 0:
                # 获取被回复者的用户名（需要在上层维护一个映射）
                reply_to = parent_rpid

            # 基础评论数据
            comment_data = {
                "comment_id": str(reply.get("rpid", "")),
                "content": content.get("message", ""),
                "likes": like_count,
                "author": member.get("uname", ""),
                "author_mid": str(member.get("mid", "")),
                "author_avatar": member.get("face", ""),
                "create_time": reply.get("ctime", 0),
                "reply_to": reply_to,
                "level": level,
                "platform": "bilibili",
                "replies": []
            }

            # 获取完整的子评论
            rpid = reply.get("rpid", 0)
            rcount = reply.get("rcount", 0)  # 子评论数量

            # 只有主评论才需要获取子评论，且oid 不为 None 时
            if level == 0 and oid is not None and rcount > 0:
                # API 返回的 replies 只有前 3 条，需要单独请求获取全部
                sub_replies = self._fetch_replies(oid, rpid)
                comment_data["replies"] = sub_replies
            else:
                # 递归处理子评论（使用 API 返回的数据）
                sub_replies = reply.get("replies", [])
                if sub_replies:
                    for sub_reply in sub_replies:
                        sub_data = self._parse_comment(sub_reply, level + 1)
                        comment_data["replies"].append(sub_data)

            return comment_data
        except Exception as e:
            return None

    def _parse_comments(self, replies: List[Dict], oid: int = None) -> List[Dict]:
        """解析评论数据（支持嵌套结构）

        Args:
            replies: 评论列表
            oid: 视频 ID（用于获取子评论）
        """
        parsed = []

        for reply in replies:
            comment = self._parse_comment(reply, oid=oid)
            if comment:
                parsed.append(comment)

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

def save_comments(comments: List[Dict], video_id: str, output_format: str = "json") -> str:
    """保存评论到 JSON 或 Markdown（支持嵌套结构）"""
    if not comments:
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 统计总评论数（包括子评论）
    def count_all_comments(comment_list):
        """递归统计所有评论数"""
        count = 0
        for comment in comment_list:
            count += 1
            count += count_all_comments(comment.get("replies", []))
        return count

    total_count = count_all_comments(comments)

    if output_format == "json":
        # JSON 格式
        json_file = os.path.join(OUTPUT_DIR, f"bili_comments_{video_id}_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "video_id": video_id,
                "total_comments": total_count,
                "fetch_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "comments": comments
            }, f, ensure_ascii=False, indent=2)

        print(f"💾 JSON已保存: {json_file}")
        return json_file

    elif output_format == "md":
        # Markdown 格式
        md_file = os.path.join(OUTPUT_DIR, f"bili_comments_{video_id}_{timestamp}.md")

        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# B站视频评论\n\n")
            f.write(f"**视频ID**: {video_id}\n\n")
            f.write(f"**评论总数**: {total_count}\n")
            f.write(f"**爬取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            # 递归写入评论
            def write_comment(comment: Dict, level: int = 0):
                """递归写入单条评论"""
                indent = "  " * level
                prefix = "├─ " if level > 0 else ""

                # 时间格式化
                create_time = comment.get("create_time", 0)
                time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S') if create_time else "未知"

                f.write(f"{indent}{prefix}**{comment['author']}**\n")
                f.write(f"{indent}    ID: `{comment['comment_id']}`\n")
                f.write(f"{indent}    时间: {time_str}\n")
                f.write(f"{indent}    点赞: {comment['likes']}\n")
                f.write(f"{indent}    内容: {comment['content']}\n")

                # 递归写入子评论
                for reply in comment.get("replies", []):
                    write_comment(reply, level + 1)

            for comment in comments:
                write_comment(comment)
                f.write("\n")

        print(f"💾 Markdown已保存: {md_file}")
        return md_file

    else:
        # 默认 CSV（扁平化结构）
        csv_file = os.path.join(OUTPUT_DIR, f"bili_comments_{video_id}_{timestamp}.csv")
        import csv

        # 扁平化评论数据
        def flatten_comments(comment_list, flat_list=None):
            """递归扁平化评论列表"""
            if flat_list is None:
                flat_list = []

            for comment in comment_list:
                flat_list.append({
                    "comment_id": comment.get("comment_id", ""),
                    "author": comment.get("author", ""),
                    "content": comment.get("content", ""),
                    "likes": comment.get("likes", 0),
                    "create_time": comment.get("create_time", 0),
                    "platform": comment.get("platform", ""),
                    "level": comment.get("level", 0)
                })
                # 递归处理子评论
                if comment.get("replies"):
                    flatten_comments(comment["replies"], flat_list)

            return flat_list

        flat_comments = flatten_comments(comments)

        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['comment_id', 'author', 'content', 'likes', 'create_time', 'platform', 'level'])
            writer.writeheader()
            writer.writerows(flat_comments)

        print(f"💾 CSV已保存: {csv_file}")
        return csv_file


# ============================================================================
# 主程序
# ============================================================================

def main(url: str = None, count: int = None, output_format: str = "json", only_liked: bool = False):
    """主程序"""
    print("\n" + "="*70)
    print("B站评论爬取工具（最热评论模式）")
    print("="*70)

    # 判断是否为交互式模式
    is_interactive = (url is None)

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
    print("🔥 当前模式：收集多页评论，按点赞数排序获取最热评论")

    # 获取评论数量
    if count is not None:
        # 命令行指定了数量，0 表示爬取全部收集到的评论
        max_count = count if count != 0 else None
    elif is_interactive:
        # 交互式模式：询问用户
        try:
            count_input = input("\n要爬取多少条最热评论? (留空表示50条，0表示全部收集的评论): ").strip()
            if count_input == '':
                max_count = 50  # 默认50条
            else:
                max_count = int(count_input) if int(count_input) != 0 else None
        except:
            max_count = 50
    else:
        # 命令行模式，未指定数量：默认50条
        max_count = 50

    # 创建客户端
    client = BiliCommentClient()

    # 获取评论
    comments = client.get_comments(video_id, max_count, only_liked)

    if not comments:
        print("\n❌ 未获取到评论")
        return

    print(f"\n✅ 成功获取 {len(comments)} 条主评论（包含子评论）")

    # 保存结果
    output_file = save_comments(comments, video_id.replace('/', '_'), output_format)

    # 显示预览（简化版）
    print("\n📝 评论预览:")
    def count_all_comments(comment_list):
        count = 0
        for comment in comment_list:
            count += 1
            count += count_all_comments(comment.get("replies", []))
        return count

    total_count = count_all_comments(comments)
    print(f"   主评论数: {len(comments)} 条")
    print(f"   总评论数: {total_count} 条（含子评论）")

    for i, comment in enumerate(comments[:3], 1):
        content = comment.get('content', '')[:60]
        if len(content) == 60:
            content += "..."
        sub_count = count_all_comments(comment.get("replies", []))
        print(f"   {i}. [{comment['likes']}赞] {comment['author']}: {content}")
        if sub_count > 0:
            print(f"      └─ {sub_count} 条回复")

    if len(comments) > 3:
        print(f"   ... 还有 {len(comments) - 3} 条主评论")

    print("\n" + "="*70)
    print("✅ 完成！")
    print(f"💾 输出文件: {output_file}")
    print("="*70)


if __name__ == "__main__":
    import sys
    # 支持命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="B站评论爬取工具（支持嵌套回复）")
    parser.add_argument("url", help="视频链接")
    parser.add_argument("count", nargs="?", type=int, default=50, help="评论数量（默认 50 条最热评论，0 表示全部最热）")
    parser.add_argument("-f", "--format", choices=["json", "md", "csv"], default="json",
                       help="输出格式：json（嵌套结构）、md（可读格式）、csv（扁平化），默认json")
    parser.add_argument("--only-liked", action="store_true",
                       help="只爬取有点赞数的主评论（子评论全部保留）")

    args = parser.parse_args()

    try:
        main(args.url, args.count, args.format, args.only_liked)
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
