#!/usr/bin/env python3
import requests
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

video_id = 'GCuaGxeZQr6wndCDzE_rcg'

# 使用你提供的Cookie
cookie = "buvid3=ED836AB2-1A1F-83B3-C368-EC717E8514CC52442infoc; b_nut=1768880952; DedeUserID=352314171; SESSDATA=340e7534%2C1786643702%2C8ff5f%2A22CjBmNdSHwh1cJexOwoyFWM5LODSzCLixmDSo8umHTW2VrYyVmwwZMAH0xptDSCSuoaoSVnJ1UF9Lc0pockFlLTlKMEYteUdfNFhSbUxYTDlZak1sMHd1MHlpRTJKUzg3WGpYbVpNbEFNNlZyczJuMUZObW5mOVgtWjJQZnJ0TFhHY1NnbnA1c1lRIIEC; bili_jct=00bda0ae20a58226c7ab7c0198f889e8"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Cookie': cookie,
}

# 尝试直接获取评论，把这个ID当作oid
url = 'https://api.bilibili.com/x/v2/reply/main'
params = {
    'oid': video_id,
    'type': 1,
    'mode': 3,
    'pagination_str': '{"offset":""}',
    'ps': 10,
}

print(f'Trying comment API with oid={video_id}')
try:
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f'Status: {r.status_code}')
    data = r.json()
    code = data.get('code')
    msg = data.get('message')
    print(f'Code: {code}')
    print(f'Message: {msg}')
    if code == 0:
        replies = data.get('data', {}).get('replies', [])
        print(f'Comments count: {len(replies)}')
        for rep in replies[:3]:
            member = rep.get('member', {})
            content = rep.get('content', {})
            likes = rep.get('like', 0)
            uname = member.get('uname', '')
            msg_text = content.get('message', '')
            print(f'  [{likes}] {uname}: {msg_text[:50]}...')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
