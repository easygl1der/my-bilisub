#!/usr/bin/env python3
import json
from pathlib import Path
import shutil
from datetime import datetime

# 最新 Cookie
cookie_str = 'abRequestId=f1824227-247f-5eaa-9bca-c0d66760e4ae; webBuild=5.11.0; xsecappid=xhs-pc-web; a1=19c72083b1ezv6ml7y7pz5sn08byjrw1jluju89dr50000339161; webId=50b111ff33792d12d971f3ca8cd47cbf; gid=yjSWJ8YjD0VyyjSWJ8YqD1YjyduhK61WvWUu7fF2MI8YDV28vVFEy7888qqjyKy8820jYjSS; loadts=1771441107834; websectiga=f3d8eaee8a8c63016320d94a1bd00562d516a5417bc43a032a80cbf70f07d5c0; sec_poison_id=27b478b7-a475-4252-8f43-4d77f857dc64; unread={%22ub%22:%2269936fa5000000001a021d43%22%2C%22ue%22:%22699463fc000000000b013d88%22%2C%22uc%22:29}'

# 解析 Cookie
cookies = {}
for item in cookie_str.split('; '):
    if '=' in item:
        key, value = item.split('=', 1)
        cookies[key] = value

# Cookie 数据
cookie_data = []
key_names = ['abRequestId', 'webBuild', 'xsecappid', 'a1', 'webId', 'gid', 'loadts', 'websectiga', 'sec_poison_id', 'unread']
for name in key_names:
    if name in cookies:
        cookie_data.append({'name': name, 'value': cookies[name]})

# 添加之前保留的 Cookie
preserved = [
    {'name': 'id_token', 'value': 'VjEAADMFIChJjisvKOOAod+7Y1zK5sflJM5TReqNuimT4d0eMsrZVrbEbRtSMlmyyY2VEvmXtjlTDiprhaoId/LD2BHf/CNT1unqe9gVz7Uor1UTa5gvRh1q65rVIWGnkY/J/sOG'},
    {'name': 'acw_tc', 'value': '0a00d58e17714415591946149e77e78d7e22a0a55f88f100718dedf8265b1c'},
    {'name': 'x-user-id-creator.xiaohongshu.com', 'value': '607bf72a0000000001005ba8'},
    {'name': 'customerClientId', 'value': '639917068231549'},
    {'name': 'access-token-creator.xiaohongshu.com', 'value': 'customer.creator.AT-68c517602893610816929798h5lnmwtmcpwiildi'},
    {'name': 'galaxy_creator_session_id', 'value': 'YfXCCWHuTJQylKVwXiJLs48olKm55KHAnsU6'},
    {'name': 'galaxy.creator.beaker.session.id', 'value': '1770186613376043185707'},
    {'name': 'web_session', 'value': '040069b10fb462560bfe7e76a63b4b24ccd424'},
]
cookie_data.extend(preserved)

# 保存文件
cookie_file = Path('MediaCrawler/xhs_cookies.json')
if cookie_file.exists():
    shutil.copy(cookie_file, cookie_file.with_suffix('.json.bak'))

data = {
    '_说明': '小红书 Cookie 配置文件',
    '_更新时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'cookies': []
}

for c in cookie_data:
    data['cookies'].append({
        'name': c['name'],
        'value': c['value'],
        'domain': '.xiaohongshu.com',
        'path': '/'
    })

with open(cookie_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Cookie updated successfully!')
print('Key cookies:')
for c in cookie_data[:5]:
    v = c['value']
    if len(v) > 25:
        v = v[:25] + '...'
    print(f'  {c["name"]}: {v}')
