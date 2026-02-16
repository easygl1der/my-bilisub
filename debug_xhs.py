import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import re

url = 'https://www.xiaohongshu.com/explore/698d8b4c000000000c0360e2'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.xiaohongshu.com/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

print(f'Requesting: {url}')
r = requests.get(url, headers=headers, timeout=30)
print(f'Status: {r.status_code}')
print(f'URL after redirect: {r.url}')
print(f'Content length: {len(r.text)}')

html = r.text

# 检查标题
title_match = re.search(r'<title>(.+?)</title>', html)
if title_match:
    print(f'Title: {title_match.group(1)}')

# 检查是否需要登录
if '登录' in html:
    print('WARNING: Page may require login')

# 查找所有图片相关的script标签
print('\n=== Searching for images in scripts ===')
scripts = re.findall(r'<script[^>]*>(.+?)</script>', html, re.DOTALL)
print(f'Found {len(scripts)} script tags')

# 查找包含图片数据的script
for i, script in enumerate(scripts):
    if 'imageList' in script or 'urlDefault' in script or 'xhscdn' in script:
        print(f'\nScript #{i} contains image data (length: {len(script)})')
        # 显示前500字符
        print(script[:500])

# 检查整个页面中的 xhscdn URL
all_urls = re.findall(r'(https?://[a-z0-9\.\-]*xhscdn\.com/[^\s"\'<>]+)', html)
print(f'\n=== All xhscdn URLs ===')
for i, u in enumerate(set(all_urls), 1):
    print(f'{i}. {u[:100]}')
