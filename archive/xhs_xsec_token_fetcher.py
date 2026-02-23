#!/usr/bin/env python3
"""
小红书 xsec_token 获取工具

通过小红书搜索接口，使用 note_id 获取带 xsec_token 的完整链接

原理：
1. 使用 Cookie 调用小红书搜索接口
2. 用 note_id 作为关键词搜索
3. 从搜索结果中提取 xsec_token
4. 生成完整访问链接

使用示例:
    # 处理单个 note_id
    python xhs_xsec_token_fetcher.py --note-id "690eaf15000000000700d395"

    # 处理完整 URL（自动提取 note_id）
    python xhs_xsec_token_fetcher.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

    # 批量处理 CSV
    python xhs_xsec_token_fetcher.py --csv notes.csv

    # 从 JSON 文件读取
    python xhs_xsec_token_fetcher.py --json videos.json

注意事项:
- 需要在 config/cookies.txt 中配置小红书 Cookie
- Cookie 必须包含 web_session（登录态令牌）
- 建议添加随机延迟避免频率限制
"""

import sys
import re
import json
import csv
import argparse
import random
import time
from pathlib import Path
from datetime import datetime

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests


# ==================== 配置 ====================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Origin': 'https://www.xiaohongshu.com',
    'Referer': 'https://www.xiaohongshu.com/',
    'Content-Type': 'application/json',
}

SEARCH_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
NOTE_DETAIL_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/feed"


# ==================== Cookie 读取 ====================

def read_xhs_cookie() -> dict:
    """
    从 config/cookies.txt 读取小红书 Cookie

    Returns:
        Cookie 字典
    """
    cookie_file = Path(__file__).parent / "config" / "cookies.txt"

    if not cookie_file.exists():
        print("❌ Cookie 文件不存在: config/cookies.txt")
        print("💡 请按照以下格式配置:")
        print("   [xiaohongshu]")
        print("   a1=xxx")
        print("   web_session=xxx  # 最重要，登录态令牌")
        print("   webId=xxx")
        return {}

    with open(cookie_file, 'r', encoding='utf-8') as f:
        content = f.read()

    cookies = {}

    # 查找 [xiaohongshu] 部分
    xhs_section = re.search(r'\[xiaohongshu\](.*?)(?:\[|$)', content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        for line in section.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#') and not line.startswith('['):
                key, value = line.split('=', 1)
                cookies[key.strip()] = value.strip()
    else:
        # 尝试查找 xiaohongshu_full= 格式
        match = re.search(r'xiaohongshu_full=([^\n]+)', content)
        if match:
            cookie_str = match.group(1)
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()

    if not cookies:
        print("❌ 未找到有效的小红书 Cookie")
        print("💡 请在 config/cookies.txt 中配置 [xiaohongshu] 部分")
        return {}

    # 检查是否包含 web_session
    if 'web_session' not in cookies:
        print("⚠️  Cookie 中缺少 web_session（登录态令牌）")
        print("💡 请确保已登录小红书网页版并获取正确的 Cookie")

    print(f"✅ 已读取 Cookie，包含 {len(cookies)} 个字段")
    return cookies


# ==================== URL 解析 ====================

def extract_note_id_from_url(url: str) -> str:
    """
    从小红书 URL 中提取 note_id

    支持的 URL 格式：
    - https://www.xiaohongshu.com/explore/69983ebb00000000150304d8
    - https://www.xiaohongshu.com/discovery/item/69983ebb00000000150304d8
    - http://xhslink.com/xxx (会自动重定向)
    - 纯 note_id: 69983ebb00000000150304d8

    Args:
        url: 小红书 URL 或 note_id

    Returns:
        提取的 note_id，如果失败返回空字符串
    """
    if not url:
        return ""

    url = url.strip()

    # 如果已经是纯 note_id（24位十六进制）
    if re.match(r'^[a-f0-9]{24}$', url, re.IGNORECASE):
        return url

    # 如果是短链接，尝试重定向获取真实 URL
    if 'xhslink.com' in url:
        try:
            response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            url = response.url
        except:
            pass

    # 从 URL 中提取 note_id
    patterns = [
        r'/explore/([a-f0-9]{24})',
        r'/discovery/item/([a-f0-9]{24})',
        r'/item/([a-f0-9]{24})',
        r'noteId=([a-f0-9]{24})',
        r'note_id=([a-f0-9]{24})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

    # 最后尝试提取任意24位十六进制
    match = re.search(r'([a-f0-9]{24})', url, re.IGNORECASE)
    if match:
        return match.group(1)

    return ""


# ==================== xsec_token 获取 ====================

def get_xsec_token_via_note_detail(note_id: str, cookies: dict) -> dict:
    """
    通过笔记详情接口获取 note_id 对应的 xsec_token

    Args:
        note_id: 笔记ID（24位十六进制字符串）
        cookies: 小红书 Cookie 字典

    Returns:
        {'success': bool, 'note_id': str, 'xsec_token': str, 'full_url': str, 'error': str}
    """
    result = {
        'success': False,
        'note_id': note_id,
        'xsec_token': '',
        'full_url': '',
        'error': ''
    }

    # 验证 note_id 格式
    if not note_id or len(note_id) < 10:
        result['error'] = f"无效的 note_id: {note_id}"
        return result

    # 尝试多个笔记详情接口
    urls_to_try = [
        f"https://edith.xiaohongshu.com/api/sns/web/v1/note/feed",
        f"https://edith.xiaohongshu.com/api/sns/web/v1/note",
        f"https://edith.xiaohongshu.com/api/sns/web/v1/feed",
    ]

    headers = {
        **HEADERS,
        'Cookie': '; '.join([f"{k}={v}" for k, v in cookies.items()]),
    }

    for url in urls_to_try:
        try:
            # 方式1: GET 请求，使用 note_id 查询参数
            params = {
                'note_id': note_id,
                'source_note_id': '',
                'image_formats': 'jpg,webp,avif',
            }
            response = requests.get(url, headers=headers, params=params, timeout=15)

            # 检查响应状态
            if response.status_code != 200:
                print(f"    调试: {url} 返回状态码 {response.status_code}")
                continue

            # 检查是否返回了 HTML（可能是重定向到验证页）
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type or '<!DOCTYPE' in response.text[:100] or '<html' in response.text[:100]:
                print(f"    调试: {url} 返回了 HTML (content-type: {content_type})，跳过")
                continue

            data = response.json()

            # 检查响应
            if data.get('code') == 0:
                # 尝试从响应中提取 xsec_token
                note_data = data.get('data', {}).get('items', [{}])[0] if data.get('data', {}).get('items') else data.get('data', {})
                if isinstance(note_data, dict) and 'xsec_token' in note_data:
                    xsec_token = note_data['xsec_token']
                    result['xsec_token'] = xsec_token
                    result['full_url'] = f"https://www.xiaohongshu.com/discovery/item/{note_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
                    result['success'] = True
                    result['error'] = ''
                    return result
        except Exception as e:
            print(f"    调试: {url} 失败: {e}")
            continue

    # 方式2: 尝试 POST 请求
    try:
        payload = {
            'note_id': note_id,
            'num': 1,
            'cursor': '',
        }
        response = requests.post("https://edith.xiaohongshu.com/api/sns/web/v1/feed", headers=headers, json=payload, timeout=15)
        data = response.json()

        if data.get('code') == 0:
            items = data.get('data', {}).get('items', [])
            for item in items:
                if item.get('id') == note_id or item.get('model', {}).get('note', {}).get('id') == note_id:
                    xsec_token = item.get('xsec_token', '')
                    if xsec_token:
                        result['xsec_token'] = xsec_token
                        result['full_url'] = f"https://www.xiaohongshu.com/discovery/item/{note_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
                        result['success'] = True
                        return result
    except Exception as e:
        result['error'] = f"笔记详情接口请求失败: {e}"

    return result


def get_xsec_token_via_search(note_id: str, cookies: dict) -> dict:
    """
    通过搜索接口获取 note_id 对应的 xsec_token

    Args:
        note_id: 笔记ID（24位十六进制字符串）
        cookies: 小红书 Cookie 字典

    Returns:
        {'success': bool, 'note_id': str, 'xsec_token': str, 'full_url': str, 'error': str}
    """
    result = {
        'success': False,
        'note_id': note_id,
        'xsec_token': '',
        'full_url': '',
        'error': ''
    }

    # 验证 note_id 格式
    if not note_id or len(note_id) < 10:
        result['error'] = f"无效的 note_id: {note_id}"
        return result

    # 调用搜索接口
    payload = {
        "keyword": note_id,
        "page": 1,
        "page_size": 20,
        "search_id": "",
        "sort": "general",
        "note_type": 0,
    }

    headers = {
        **HEADERS,
        'Cookie': '; '.join([f"{k}={v}" for k, v in cookies.items()])
    }

    try:
        response = requests.post(SEARCH_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()

        data = response.json()

        # 检查是否登录
        if data.get('code') == -101:
            result['error'] = "未登录或 Cookie 已失效（code: -101）"
            return result

        # 检查响应状态
        if data.get('success', False) is False and data.get('code') != 0:
            result['error'] = f"接口返回错误: {data.get('msg', 'Unknown error')} (code: {data.get('code')})"
            return result

        # 解析搜索结果
        items = data.get('data', {}).get('items', [])

        for item in items:
            # 方法1: 从 item.id 判断
            if item.get('id') == note_id:
                xsec_token = item.get('xsec_token', '')
                if xsec_token:
                    result['xsec_token'] = xsec_token
                    result['full_url'] = f"https://www.xiaohongshu.com/discovery/item/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"
                    result['success'] = True
                    return result

            # 方法2: 从 note_card.id 判断
            note_card = item.get('note_card', {})
            if note_card.get('id') == note_id:
                xsec_token = item.get('xsec_token', '')
                if xsec_token:
                    result['xsec_token'] = xsec_token
                    result['full_url'] = f"https://www.xiaohongshu.com/discovery/item/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"
                    result['success'] = True
                    return result

        # 方法3: 从 note_card.note_id 判断
        for item in items:
            note_card = item.get('note_card', {})
            if note_card.get('note_id') == note_id:
                xsec_token = item.get('xsec_token', '')
                if xsec_token:
                    result['xsec_token'] = xsec_token
                    result['full_url'] = f"https://www.xiaohongshu.com/discovery/item/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"
                    result['success'] = True
                    return result

        # 搜索结果中未找到匹配的 note_id
        result['error'] = f"搜索结果中未找到 note_id: {note_id}（可能笔记已被删除或不可见）"

    except requests.exceptions.Timeout:
        result['error'] = "请求超时，请检查网络连接"
    except requests.exceptions.RequestException as e:
        result['error'] = f"网络请求失败: {e}"
    except json.JSONDecodeError:
        result['error'] = "接口返回的不是有效的 JSON 格式"
    except Exception as e:
        result['error'] = f"未知错误: {e}"

    return result


def get_xsec_token(note_id: str, cookies: dict) -> dict:
    """
    获取 note_id 对应的 xsec_token
    先尝试笔记详情接口，失败后尝试搜索接口

    Args:
        note_id: 笔记ID（24位十六进制字符串）
        cookies: 小红书 Cookie 字典

    Returns:
        {'success': bool, 'note_id': str, 'xsec_token': str, 'full_url': str, 'error': str}
    """
    result = {
        'success': False,
        'note_id': note_id,
        'xsec_token': '',
        'full_url': '',
        'error': ''
    }

    # 验证 note_id 格式
    if not note_id or len(note_id) < 10:
        result['error'] = f"无效的 note_id: {note_id}"
        return result

    # 方法1: 尝试笔记详情接口（不容易被风控）
    print("  📝 尝试笔记详情接口...")
    result = get_xsec_token_via_note_detail(note_id, cookies)
    if result['success']:
        return result
    print(f"  ⚠️  笔记详情接口失败: {result['error']}")

    # 方法2: 尝试搜索接口
    print("  🔍 尝试搜索接口...")
    result = get_xsec_token_via_search(note_id, cookies)

    return result


def process_single_note(note_id: str, cookies: dict, delay: bool = True) -> dict:
    """
    处理单个 note_id

    Args:
        note_id: 笔记ID
        cookies: Cookie 字典
        delay: 是否添加随机延迟

    Returns:
        处理结果字典
    """
    result = get_xsec_token(note_id, cookies)

    print(f"  Note ID: {note_id}")
    if result['success']:
        print(f"  ✅ xsec_token: {result['xsec_token'][:20]}...")
        print(f"  🔗 完整链接: {result['full_url']}")
    else:
        print(f"  ❌ {result['error']}")

    # 随机延迟，避免频率限制
    if delay and result['success']:
        sleep_time = random.uniform(1, 3)
        time.sleep(sleep_time)

    return result


# ==================== 批量处理 ====================

def process_csv(csv_path: str, cookies: dict, output_path: str = None, delay: bool = True):
    """
    批量处理 CSV 文件中的 note_id

    Args:
        csv_path: CSV 文件路径
        cookies: Cookie 字典
        output_path: 输出文件路径（可选）
        delay: 是否添加随机延迟
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        return

    # 设置输出路径
    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_xsec.csv"

    # 读取 CSV
    results = []
    note_ids = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        # 查找包含笔记ID的列
        note_id_col = None
        url_col = None
        for col in ['笔记ID', 'note_id', 'noteid', 'id', '笔记id']:
            if col in fieldnames:
                note_id_col = col
                break
        for col in ['链接', 'url', 'link', 'video_url', 'note_url']:
            if col in fieldnames:
                url_col = col
                break

        if not note_id_col and not url_col:
            print(f"❌ 未找到笔记ID或链接列，可用的列: {fieldnames}")
            return

        print(f"\n📋 从列 '{note_id_col or url_col}' 读取...")
        print("=" * 70)

        for row in reader:
            note_id = ''
            if note_id_col:
                note_id = row.get(note_id_col, '').strip()

            # 如果没有笔记ID，尝试从链接中提取
            if not note_id and url_col:
                url = row.get(url_col, '').strip()
                # 从链接中提取 note_id
                patterns = [
                    r'/explore/([a-f0-9]{24})',
                    r'/discovery/item/([a-f0-9]{24})',
                    r'([a-f0-9]{24})',
                ]
                for pattern in patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        note_id = match.group(1)
                        break

            if note_id:
                note_ids.append({
                    'note_id': note_id,
                    'row_data': row
                })

    print(f"\n找到 {len(note_ids)} 个笔记ID")
    print("=" * 70)

    # 处理每个 note_id
    for i, note_info in enumerate(note_ids, 1):
        print(f"\n[{i}/{len(note_ids)}]", end='')
        result = process_single_note(note_info['note_id'], cookies, delay)
        result['original_row'] = note_info['row_data']
        results.append(result)

    # 保存结果
    print(f"\n\n{'=' * 70}")
    print("📊 处理完成")
    print("=" * 70)

    success = sum(1 for r in results if r['success'])
    failed = len(results) - success
    print(f"总计: {len(results)} | 成功: {success} | 失败: {failed}")

    # 写入 CSV
    if results:
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            original_fields = list(results[0].get('original_row', {}).keys())

            writer = csv.DictWriter(f, fieldnames=original_fields + ['xsec_token', '完整链接', '状态', '错误信息'])
            writer.writeheader()

            for r in results:
                row_data = r.get('original_row', {})
                row_data.update({
                    'xsec_token': r['xsec_token'],
                    '完整链接': r['full_url'],
                    '状态': '成功' if r['success'] else '失败',
                    '错误信息': r['error']
                })
                writer.writerow(row_data)

        print(f"📄 结果已保存: {output_path}")


def process_json(json_path: str, cookies: dict, output_path: str = None, delay: bool = True):
    """
    处理 JSON 文件中的 note_id

    Args:
        json_path: JSON 文件路径
        cookies: Cookie 字典
        output_path: 输出文件路径（可选）
        delay: 是否添加随机延迟
    """
    json_path = Path(json_path)
    if not json_path.exists():
        print(f"❌ JSON 文件不存在: {json_path}")
        return

    # 设置输出路径
    if output_path is None:
        output_path = json_path.parent / f"{json_path.stem}_xsec.json"

    # 读取 JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ JSON 格式必须是数组")
        return

    print(f"\n📋 找到 {len(data)} 条记录")
    print("=" * 70)

    results = []
    for i, item in enumerate(data, 1):
        note_id = ''

        # 查找 note_id 字段
        for field in ['note_id', 'noteId', 'id', '笔记id', '笔记ID']:
            if field in item and item[field]:
                note_id = item[field]
                break

        # 如果没有 note_id，尝试从链接中提取
        if not note_id:
            for field in ['url', 'video_url', 'note_url', 'link', '链接']:
                if field in item and item[field]:
                    url = item[field]
                    patterns = [
                        r'/explore/([a-f0-9]{24})',
                        r'/discovery/item/([a-f0-9]{24})',
                        r'([a-f0-9]{24})',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, url, re.IGNORECASE)
                        if match:
                            note_id = match.group(1)
                            break
                    break

        if not note_id:
            print(f"\n[{i}/{len(data)}] ⚠️  未找到笔记ID")
            results.append({
                'original_item': item,
                'note_id': '',
                'xsec_token': '',
                'full_url': '',
                'success': False,
                'error': '未找到笔记ID'
            })
            continue

        print(f"\n[{i}/{len(data)}]", end='')
        result = process_single_note(note_id, cookies, delay)
        result['original_item'] = item
        results.append(result)

    # 保存结果
    print(f"\n\n{'=' * 70}")
    print("📊 处理完成")
    print("=" * 70)

    success = sum(1 for r in results if r['success'])
    failed = len(results) - success
    print(f"总计: {len(results)} | 成功: {success} | 失败: {failed}")

    # 写入 JSON
    output_data = []
    for r in results:
        item = r.get('original_item', {})
        item.update({
            'xsec_token': r['xsec_token'],
            'full_url': r['full_url'],
            'xsec_success': r['success'],
            'xsec_error': r['error']
        })
        output_data.append(item)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"📄 结果已保存: {output_path}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书 xsec_token 获取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 处理单个 note_id:
   python xhs_xsec_token_fetcher.py --note-id "690eaf15000000000700d395"

2. 处理完整 URL:
   python xhs_xsec_token_fetcher.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

3. 批量处理 CSV:
   python xhs_xsec_token_fetcher.py --csv notes.csv

4. 从 JSON 文件读取:
   python xhs_xsec_token_fetcher.py --json videos.json

5. 指定输出文件:
   python xhs_xsec_token_fetcher.py --csv notes.csv --output result.csv

6. 禁用延迟（快速模式，可能有风险）:
   python xhs_xsec_token_fetcher.py --csv notes.csv --no-delay

注意事项:
- 需要在 config/cookies.txt 中配置小红书 Cookie
- Cookie 必须包含 web_session（登录态令牌）
- 建议启用延迟避免频率限制（默认启用）
        """
    )

    parser.add_argument('--note-id', help='单个笔记ID')
    parser.add_argument('--url', help='小红书完整URL（会自动提取note_id）')
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('--json', help='JSON 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--no-delay', action='store_true', help='禁用随机延迟（快速模式，可能有风险）')

    args = parser.parse_args()

    if not any([args.note_id, args.url, args.csv, args.json]):
        parser.print_help()
        print("\n❌ 请提供 --note-id、--url、--csv 或 --json 参数")
        return

    print("=" * 70)
    print("小红书 xsec_token 获取工具")
    print("=" * 70)

    # 读取 Cookie
    cookies = read_xhs_cookie()
    if not cookies:
        print("\n❌ 未读取到有效 Cookie，无法继续")
        return

    if 'web_session' not in cookies:
        print("\n⚠️  Cookie 中缺少 web_session，可能导致失败")

    delay = not args.no_delay
    if delay:
        print(f"\n⏱️  延迟模式: 启用（随机 1-3 秒）")
    else:
        print(f"\n⏱️  延迟模式: 禁用（快速模式，可能有风险）")

    # 处理 URL 或 note_id
    note_id = None
    if args.url:
        note_id = extract_note_id_from_url(args.url)
        if not note_id:
            print(f"\n❌ 无法从 URL 提取 note_id: {args.url}")
            return
        print(f"\n从 URL 提取 note_id: {note_id}")
    elif args.note_id:
        note_id = args.note_id

    if note_id:
        print(f"\n处理笔记: {note_id}")
        print("-" * 70)
        result = process_single_note(note_id, cookies, delay)

        # 保存结果
        output_dir = Path(__file__).parent / "output" / "xsec_tokens"
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f"xsec_tokens_{date_str}.json"

        # 读取现有结果
        existing_data = []
        if output_path.exists():
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

        # 添加新结果
        existing_data.append({
            'input': args.url or args.note_id,
            'note_id': result['note_id'],
            'xsec_token': result['xsec_token'],
            'full_url': result['full_url'],
            'success': result['success'],
            'error': result['error'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        print(f"\n📄 结果已保存: {output_path}")

    elif args.csv:
        process_csv(args.csv, cookies, args.output, delay)

    elif args.json:
        process_json(args.json, cookies, args.output, delay)


if __name__ == "__main__":
    main()
