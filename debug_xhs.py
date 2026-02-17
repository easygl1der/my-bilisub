import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import re
import json

url = 'https://www.xiaohongshu.com/explore/698d8b4c000000000c0360e2?xsec_token=ABtk__zniCl2zWeX1W4x5VmMEL3tBj2b3hAFGXUFsoLkw=&xsec_source=pc_user'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.xiaohongshu.com/',
}

print(f'请求: {url[:80]}...')
r = requests.get(url, headers=headers, timeout=30)
print(f'状态: {r.status_code}')

html = r.text

# 检查是否成功
if '404' in r.url or '你访问的页面不见了' in html:
    print('被重定向到404页面!')
    print(f'最终URL: {r.url}')
else:
    print('成功获取页面')

# 提取 __INITIAL_STATE__
start_idx = html.find('window.__INITIAL_STATE__=')
if start_idx >= 0:
    start_idx += len('window.__INITIAL_STATE__=')
    end_idx = html.find('</script>', start_idx)
    json_str = html[start_idx:end_idx]

    print(f'\n=== JSON数据片段 ===')
    print(f'JSON长度: {len(json_str)}')

    # 搜索所有可能包含图片的字段
    print('\n=== 搜索图片相关字段 ===')
    fields = ['imageList', 'images', 'urlDefault', 'traceId', 'noteDetail']
    for field in fields:
        count = json_str.count(field)
        print(f'{field}: {count}')

    # 尝试直接提取 imageList 数组内容
    print('\n=== 尝试提取 imageList ===')
    # 使用更宽松的正则
    patterns = [
        r'"imageList"\s*:\s*(\[.+?\])',
        r'"imageList"\s*:\s*(\[[^\]]+\])',
    ]

    for pat in patterns:
        match = re.search(pat, json_str, re.DOTALL)
        if match:
            content = match.group(1)
            print(f'找到 imageList (长度: {len(content)})')
            print(f'前500字符: {content[:500]}')

            # 计算对象数量（通过 { 计数）
            obj_count = content.count('{')
            print(f'对象数量约: {obj_count}')
            break

    # 显示整个 JSON 的结构
    print('\n=== JSON 顶层结构 ===')
    try:
        # 尝试只解析顶层
        # 找到第一个 { 和匹配的 }
        data = json.loads(json_str)
        print(f'顶层键: {list(data.keys())[:10]}')

        if 'note' in data:
            print(f'note 键: {list(data["note"].keys())[:10]}')
    except:
        pass
