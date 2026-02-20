#!/usr/bin/env python3
import requests
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

video_id = 'GCuaGxeZQr6wndCDzE_rcg'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
}

urls = [
    f'https://api.bilibili.com/x/web-interface/view?bvid={video_id}',
    f'https://api.bilibili.com/x/web-interface/view?aid={video_id}',
]

for url in urls:
    print(f'Trying: {url}')
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f'Status: {r.status_code}')
        print(f'Response: {r.text[:200]}')
        print()
    except Exception as e:
        print(f'Error: {e}')
        print()
