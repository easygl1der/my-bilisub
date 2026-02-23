#!/usr/bin/env python3
"""
小红书链接处理工具

功能：
- 从小红书链接提取笔记ID
- 生成简化链接格式
- 支持批量处理 CSV/JSON

使用示例:
    # 处理单个链接
    python xhs_share_link_generator.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

    # 批量处理 CSV
    python xhs_share_link_generator.py --csv notes.csv

    # 从 JSON 文件读取
    python xhs_share_link_generator.py --json videos.json
"""

import sys
import re
import json
import csv
import argparse
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests


# ==================== 配置 ====================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# ==================== 链接处理 ====================

def extract_note_id(url: str) -> str:
    """
    从小红书链接中提取笔记ID

    Args:
        url: 小红书链接（可以是 xhslink.com 或 xiaohongshu.com）

    Returns:
        笔记ID（24位十六进制字符串）
    """
    # 处理短链接，需要先重定向获取原始链接
    if 'xhslink.com' in url:
        try:
            response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            url = response.url
        except:
            pass

    # 从原始链接提取笔记ID
    patterns = [
        r'/explore/([a-f0-9]{24})',
        r'/discovery/item/([a-f0-9]{24})',
        r'noteId=([a-f0-9]{24})',
        r'/item/([a-f0-9]{24})',
        r'([a-f0-9]{24})',  # 最后尝试直接匹配24位十六进制
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

    return ''


def generate_short_url(note_id: str) -> dict:
    """
    生成小红书简化链接

    Args:
        note_id: 笔记ID（24位十六进制字符串）

    Returns:
        {'success': bool, 'short_url': str, 'original_url': str, 'error': str}
    """
    result = {'success': False, 'short_url': '', 'original_url': '', 'error': ''}

    if not note_id or len(note_id) != 24:
        result['error'] = f"无效的笔记ID: {note_id}"
        return result

    # 生成原始链接
    original_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    result['original_url'] = original_url

    # 小红书的 xhslink.com 分享链接需要通过 App 或登录后的网页生成
    # 这里提供几种替代方案：

    # 方案1: 尝试从 API 获取（需要 Cookie）
    try:
        api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/note/share/short_url"

        # 读取 Cookie
        cookies = {}
        cookie_file = Path(__file__).parent / "config" / "cookies.txt"
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    start = content.find('[xiaohongshu]')
                    if start >= 0:
                        end = content.find('\n[', start + 1)
                        if end == -1:
                            end = len(content)
                        xhs_section = content[start:end]
                        for line in xhs_section.split('\n'):
                            line = line.strip()
                            if '=' in line and not line.startswith('#') and not line.startswith('['):
                                key, value = line.split('=', 1)
                                cookies[key.strip()] = value.strip()
            except:
                pass

        if cookies:
            headers = {
                **HEADERS,
                'Referer': original_url,
                'Accept': 'application/json',
            }
            params = {'note_id': note_id}

            response = requests.get(api_url, headers=headers, params=params, cookies=cookies, timeout=10)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'data' in data and data['data']:
                        share_url = data['data'].get('short_url') or data['data'].get('share_url')
                        if share_url:
                            result['success'] = True
                            result['short_url'] = share_url
                            return result
                except:
                    pass

        # 方案2: 尝试从页面获取分享链接
        response = requests.get(original_url, headers=HEADERS, cookies=cookies, timeout=15, allow_redirects=True)

        if response.status_code == 200:
            html = response.text

            # 查找分享链接模式
            share_patterns = [
                r'"shareUrl":"([^"]+)"',
                r'"share_url":"([^"]+)"',
                r'"shortUrl":"([^"]+)"',
                r'"short_url":"([^"]+)"',
            ]

            for pattern in share_patterns:
                match = re.search(pattern, html)
                if match:
                    share_candidate = match.group(1).replace(r'\/', '/')
                    if 'xhslink.com' in share_candidate:
                        result['success'] = True
                        result['short_url'] = share_candidate
                        return result

    except Exception as e:
        result['error'] = str(e)

    # 如果没有获取到 xhslink.com，返回原始链接作为"短链接"
    result['error'] = "无法获取 xhslink.com 分享链接（需要登录或使用 App）"
    result['short_url'] = original_url

    return result


def process_url(url: str) -> dict:
    """
    处理单个链接

    Args:
        url: 小红书链接

    Returns:
        处理结果字典
    """
    result = {
        'original_url': url,
        'note_id': '',
        'short_url': '',
        'original_explore_url': '',
        'success': False,
        'error': ''
    }

    print(f"\n处理: {url[:70]}...")
    print("-" * 70)

    # 提取笔记ID
    note_id = extract_note_id(url)
    if not note_id:
        result['error'] = "无法提取笔记ID"
        print(f"❌ {result['error']}")
        return result

    result['note_id'] = note_id
    print(f"笔记ID: {note_id}")

    # 生成链接
    link_result = generate_short_url(note_id)
    result.update(link_result)

    # 输出结果
    if result['success'] and 'xhslink.com' in result['short_url']:
        print(f"✅ 分享链接: {result['short_url']}")
    elif result['short_url']:
        print(f"📝 简化链接: {result['short_url']}")
        print(f"   (如需 xhslink.com 分享链接，请在小红书 App 或登录后网页中点击分享)")
    else:
        print(f"❌ {result['error']}")

    return result


def process_csv(csv_path: str, output_path: str = None):
    """
    批量处理 CSV 文件

    Args:
        csv_path: CSV 文件路径
        output_path: 输出 CSV 文件路径（可选）
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"❌ CSV 文件不存在: {csv_path}")
        return

    # 设置输出路径
    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_processed.csv"

    # 读取 CSV
    results = []
    links = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        # 查找包含链接的列
        link_col = None
        for col in ['链接', 'url', 'link', 'video_url', 'note_url']:
            if col in fieldnames:
                link_col = col
                break

        if not link_col:
            print(f"❌ 未找到链接列，可用的列: {fieldnames}")
            return

        print(f"\n📋 从列 '{link_col}' 读取链接...")
        print("=" * 70)

        for row in reader:
            url = row.get(link_col, '').strip()
            if url:
                links.append({
                    'url': url,
                    'title': row.get('标题', '') or row.get('title', '') or '',
                    'row_data': row
                })

    print(f"\n找到 {len(links)} 个链接")
    print("=" * 70)

    # 处理每个链接
    for i, link_info in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}]", end='')
        result = process_url(link_info['url'])
        result['title'] = link_info['title']
        result['original_row'] = link_info['row_data']
        results.append(result)

    # 保存结果
    print(f"\n\n{'=' * 70}")
    print("📊 处理完成")
    print("=" * 70)

    success = sum(1 for r in results if r['success'] and 'xhslink.com' in r['short_url'])
    simplified = sum(1 for r in results if r['short_url'] and 'xiaohongshu.com/explore/' in r['short_url'])
    failed = len(results) - success - simplified
    print(f"总计: {len(results)} | xhslink分享链接: {success} | 简化链接: {simplified} | 失败: {failed}")

    # 写入 CSV
    if results:
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            original_fields = list(results[0].get('original_row', {}).keys())

            writer = csv.DictWriter(f, fieldnames=original_fields + ['笔记ID', '分享链接', '简化链接', '状态', '错误信息'])
            writer.writeheader()

            for r in results:
                row_data = r.get('original_row', {})
                row_data.update({
                    '笔记ID': r['note_id'],
                    '分享链接': r['short_url'] if 'xhslink.com' in r['short_url'] else '',
                    '简化链接': r['short_url'] if 'xiaohongshu.com/explore/' in r['short_url'] else '',
                    '状态': '成功' if r['success'] or r['short_url'] else '失败',
                    '错误信息': r['error']
                })
                writer.writerow(row_data)

        print(f"📄 结果已保存: {output_path}")


def process_json(json_path: str, output_path: str = None):
    """
    处理 JSON 文件

    Args:
        json_path: JSON 文件路径
        output_path: 输出文件路径（可选）
    """
    json_path = Path(json_path)
    if not json_path.exists():
        print(f"❌ JSON 文件不存在: {json_path}")
        return

    # 设置输出路径
    if output_path is None:
        output_path = json_path.parent / f"{json_path.stem}_processed.json"

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
        url = ''
        for field in ['url', 'video_url', 'note_url', 'link', '链接']:
            if field in item and item[field]:
                url = item[field]
                break

        if not url:
            print(f"\n[{i}/{len(data)}] ⚠️  未找到链接")
            results.append({
                'original_item': item,
                'note_id': '',
                'short_url': '',
                'success': False,
                'error': '未找到链接'
            })
            continue

        print(f"\n[{i}/{len(data)}]", end='')
        result = process_url(url)
        result['original_item'] = item
        results.append(result)

    # 保存结果
    print(f"\n\n{'=' * 70}")
    print("📊 处理完成")
    print("=" * 70)

    success = sum(1 for r in results if r['success'] and 'xhslink.com' in r['short_url'])
    simplified = sum(1 for r in results if r['short_url'] and 'xiaohongshu.com/explore/' in r['short_url'])
    failed = len(results) - success - simplified
    print(f"总计: {len(results)} | xhslink分享链接: {success} | 简化链接: {simplified} | 失败: {failed}")

    # 写入 JSON
    output_data = []
    for r in results:
        item = r.get('original_item', {})
        item.update({
            'note_id': r['note_id'],
            'share_link': r['short_url'] if 'xhslink.com' in r['short_url'] else '',
            'short_link': r['short_url'] if 'xiaohongshu.com/explore/' in r['short_url'] else '',
            'share_success': r['success'] if 'xhslink.com' in r['short_url'] else False,
            'share_error': r['error']
        })
        output_data.append(item)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"📄 结果已保存: {output_path}")


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(
        description="小红书链接处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 处理单个链接:
   python xhs_share_link_generator.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"

2. 批量处理 CSV:
   python xhs_share_link_generator.py --csv notes.csv

3. 从 JSON 文件读取:
   python xhs_share_link_generator.py --json videos.json

4. 指定输出文件:
   python xhs_share_link_generator.py --csv notes.csv --output result.csv

注意事项:
- xhslink.com 分享链接需要在小红书 App 或登录后的网页中点击分享按钮生成
- 如果配置了 config/cookies.txt 中的小红书 Cookie，可以尝试获取分享链接
- 如果无法获取 xhslink.com，工具会返回简化的 xiaohongshu.com/explore/ 链接
        """
    )

    parser.add_argument('--url', help='单个小红书链接')
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('--json', help='JSON 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    if not any([args.url, args.csv, args.json]):
        parser.print_help()
        print("\n❌ 请提供 --url、--csv 或 --json 参数")
        return

    print("=" * 70)
    print("小红书链接处理工具")
    print("=" * 70)

    if args.url:
        result = process_url(args.url)
        if result['short_url']:
            print(f"\n{'=' * 70}")
            print("处理结果:")
            print("=" * 70)
            print(f"笔记ID: {result['note_id']}")
            print(f"原始链接: {result['original_url']}")
            print(f"处理结果: {result['short_url']}")
            if result['error']:
                print(f"提示: {result['error']}")

    elif args.csv:
        process_csv(args.csv, args.output)

    elif args.json:
        process_json(args.json, args.output)


if __name__ == "__main__":
    main()
