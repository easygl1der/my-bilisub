#!/usr/bin/env python3
"""
小红书 Cookie 更新工具
"""

import json
import sys
from pathlib import Path
import shutil
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def update_cookies_with_values():
    """使用用户提供的 Cookie 值更新文件"""

    # 用户提供的 Cookie 数据
    cookie_data = [
        {"name": "a1", "value": "19c72083b1ezv6ml7y7pz5sn08byjrw1jluju89dr50000339161"},
        {"name": "abRequestId", "value": "f1824227-247f-5eaa-9bca-c0d66760e4ae"},
        {"name": "acw_tc", "value": "0a00d58e17714415591946149e77e78d7e22a0a55f88f100718dedf8265b1c"},
        {"name": "gid", "value": "yjSWJ8YjD0VyyjSWJ8YqD1YjyduhK61WvWUu7fF2MI8YDV28vVFEy7888qqjyKy8820jYjSS"},
        {"name": "id_token", "value": "VjEAADMFIChJjisvKOOAod+7Y1zK5sflJM5TReqNuimT4d0eMsrZVrbEbRtSMlmyyY2VEvmXtjlTDiprhaoId/LD2BHf/CNT1unqe9gVz7Uor1UTa5gvRh1q65rVIWGnkY/J/sOG"},
        {"name": "loadts", "value": "1771441107834"},
        {"name": "sec_poison_id", "value": "27b478b7-a475-4252-8f43-4d77f857dc64"},
        {"name": "unread", "value": '{"ub":"69936fa5000000001a021d43","ue":"699463fc000000000b013d88","uc":29}'},
        {"name": "webId", "value": "cfb8ca276d5ca49f6808300d449d57af"},  # 使用之前的值
        {"name": "webBuild", "value": "5.11.0"},  # 使用之前的值
        {"name": "xsecappid", "value": "xhs-pc-web"},  # 使用之前的值
        {"name": "x-user-id-creator.xiaohongshu.com", "value": "607bf72a0000000001005ba8"},  # 使用之前的值
        {"name": "customerClientId", "value": "639917068231549"},  # 使用之前的值
        {"name": "access-token-creator.xiaohongshu.com", "value": "customer.creator.AT-68c517602893610816929798h5lnmwtmcpwiildi"},  # 使用之前的值
        {"name": "galaxy_creator_session_id", "value": "YfXCCWHuTJQylKVwXiJLs48olKm55KHAnsU6"},  # 使用之前的值
        {"name": "galaxy.creator.beaker.session.id", "value": "1770186613376043185707"},  # 使用之前的值
        {"name": "websectiga", "value": "16f444b9ff5e3d7e258b5f7674489196303a0b160e16647c6c2b4dcb609f4134"},  # 使用之前的值
    ]

    # 添加 web_session（如果用户之前有）
    cookie_data.append({"name": "web_session", "value": "040069b10fb462560bfe7e76a63b4b24ccd424"})

    return cookie_data


def save_cookies_file(cookies: list):
    """保存 Cookie 到文件"""
    # 从 platforms/xiaohongshu/ 回到父目录的 MediaCrawler
    cookie_file = Path(__file__).parent.parent.parent / "MediaCrawler" / "xhs_cookies.json"

    # 备份原文件
    if cookie_file.exists():
        backup_file = cookie_file.with_suffix('.json.bak')
        shutil.copy(cookie_file, backup_file)
        print(f"   已备份原文件到: {backup_file}")

    # 创建数据
    data = {
        "_说明": "小红书 Cookie 配置文件 - 从浏览器复制完整的 Cookies",
        "_获取方法": "使用浏览器扩展 EditThisCookie 导出",
        "_更新时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "_关键Cookie": {
            "a1": "必需 - 签名算法必需",
            "web_session": "必需 - 登录会话验证",
            "webId": "推荐 - 设备标识"
        },
        "cookies": []
    }

    # 转换为 xhs_cookies.json 格式
    for cookie in cookies:
        data["cookies"].append({
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": ".xiaohongshu.com",
            "path": "/"
        })

    # 写入文件
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookie_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return cookie_file


def main():
    print("\n" + "="*70)
    print("小红书 Cookie 更新工具")
    print("="*70)

    print("\n正在更新 Cookie...")

    # 获取新的 Cookie 数据
    cookies = update_cookies_with_values()

    # 保存到文件
    cookie_file = save_cookies_file(cookies)

    print(f"\n✅ Cookie 已更新到: {cookie_file}")

    # 显示关键 Cookie
    print("\n   已更新的关键 Cookie:")
    key_cookies = ["a1", "web_session", "webId", "gid"]
    for c in cookies:
        if c["name"] in key_cookies:
            value = c["value"]
            display_value = value[:25] + "..." if len(value) > 25 else value
            print(f"      {c['name']}: {display_value}")

    print("\n现在可以运行以下命令测试:")
    print("   python fetch_xhs_comments.py")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()
