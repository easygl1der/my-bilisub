#!/usr/bin/env python3
"""
测试从小红书页面提取 xsec_token

使用方法:
    python tools/test_xsec_token.py --note-id "690eaf15000000000700d395"
    python tools/test_xsec_token.py --url "https://www.xiaohongshu.com/explore/69983ebb00000000150304d8"
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


async def test_extract_xsec_token(url: str):
    """测试从页面提取 xsec_token"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        print(f"\n📡 访问: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)

        print("\n🔍 开始搜索 xsec_token...")

        # 从页面中提取 xsec_token
        result = await page.evaluate('''
            () => {
                let xsecToken = '';
                let xsecSource = 'pc_explore';
                let foundLocation = '';

                // 方法1: 检查 URL 参数
                const urlParams = new URLSearchParams(window.location.href.split('?')[1]);
                xsecToken = urlParams.get('xsec_token') || '';
                if (urlParams.get('xsec_source')) {
                    xsecSource = urlParams.get('xsec_source');
                }
                if (xsecToken) foundLocation = 'URL参数';

                // 方法2: 检查 window 对象中的 xsec 相关属性
                if (!xsecToken) {
                    const windowKeys = Object.keys(window);
                    for (const key of windowKeys) {
                        if (key.toLowerCase().includes('xsec') || key.includes('note')) {
                            try {
                                const value = window[key];
                                if (typeof value === 'object' && value !== null) {
                                    const jsonStr = JSON.stringify(value);
                                    if (jsonStr.includes('xsec_token')) {
                                        const match = jsonStr.match(/"xsec_token"\\s*:\\s*"([^"]+)"/);
                                        if (match && match[1]) {
                                            xsecToken = match[1];
                                            foundLocation = `window.${key}`;
                                            break;
                                        }
                                    }
                                } else if (typeof value === 'string' && value.length > 10) {
                                    if (value.includes('xsec_token') || value.match(/^[A-Za-z0-9_-]{20,}$/)) {
                                        xsecToken = value;
                                        foundLocation = `window.${key}`;
                                        break;
                                    }
                                }
                            } catch (e) {}
                        }
                        if (xsecToken) break;
                    }
                }

                // 方法3: 检查页面中的 script 标签
                if (!xsecToken) {
                    const scripts = document.querySelectorAll('script');
                    for (let i = 0; i < scripts.length; i++) {
                        const text = scripts[i].textContent;
                        if (text && text.includes('xsec_token')) {
                            // 尝试多种提取方式
                            const patterns = [
                                /"xsec_token"\\s*:\\s*"([^"]+)"/g,
                                /xsec_token['"]?\\s*:\\s*"([^"]+)"/g,
                                /xsec_token\\s*=\\s*['"]?([^']+?)['"]?/g,
                            ];
                            for (const pattern of patterns) {
                                const matches = text.matchAll(pattern);
                                for (const m of matches) {
                                    if (m[1] && m[1].length > 10) {
                                        xsecToken = m[1];
                                        foundLocation = `script[${i}]`;
                                        break;
                                    }
                                }
                                if (xsecToken) break;
                            }
                        }
                        if (xsecToken) break;
                    }
                }

                // 方法4: 检查所有元素的 data 属性
                if (!xsecToken) {
                    const allElements = document.querySelectorAll('*');
                    for (const elem of allElements) {
                        for (const attr of elem.attributes) {
                            const attrName = attr.name.toLowerCase();
                            const attrValue = attr.value;
                            if (attrName.includes('xsec') && attrValue && attrValue.length > 10) {
                                xsecToken = attrValue;
                                foundLocation = `元素属性 ${attrName}`;
                                break;
                            }
                        }
                        if (xsecToken) break;
                    }
                }

                // 方法5: 检查页面中的隐藏 input 或 hidden 字段
                if (!xsecToken) {
                    const inputs = document.querySelectorAll('input[type="hidden"]');
                    for (const input of inputs) {
                        const name = input.name || input.getAttribute('name') || '';
                        const value = input.value || input.getAttribute('value') || '';
                        if (name.includes('xsec') && value && value.length > 10) {
                            xsecToken = value;
                            foundLocation = `hidden input ${name}`;
                            break;
                        }
                    }
                }

                // 方法6: 打印页面中的关键信息用于调试
                if (!xsecToken) {
                    // 输出一些调试信息
                    console.log('正在搜索 xsec_token...');
                }

                return {
                    success: xsecToken !== '',
                    xsecToken: xsecToken,
                    xsecSource: xsecSource,
                    foundLocation: foundLocation,
                    currentUrl: window.location.href
                };
            }
        ''')

        print(f"\n📊 提取结果:")
        print(f"   成功: {'✅ 是' if result['success'] else '❌ 否'}")
        print(f"   xsec_token: {result['xsecToken'] if result['xsecToken'] else '(未找到)'}")
        print(f"   来源: {result['foundLocation'] if result['foundLocation'] else '(未知)'}")
        print(f"   当前URL: {result['currentUrl']}")

        # 如果找到了，构建完整链接
        if result['success']:
            full_url = f"{result['currentUrl']}?xsec_token={result['xsecToken']}&xsec_source={result['xsecSource']}"
            print(f"\n🔗 完整链接:")
            print(f"   {full_url}")
        else:
            print(f"\n⚠️  未能在页面中找到 xsec_token")
            print(f"💡 可能原因:")
            print(f"   1. 笔记页面本身不包含 xsec_token（仅限推荐页）")
            print(f"   2. xsec_token 需要通过特定操作生成（如点击、滚动）")
            print(f"   3. 小红书更新了页面结构")

        print(f"\n⏳ 等待 10 秒后关闭浏览器...")
        await asyncio.sleep(10)

        await browser.close()
        return result


async def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python tools/test_xsec_token.py --url \"小红书链接\"")
        print("  python tools/test_xsec_token.py --note-id \"笔记ID\"")
        print("\n示例:")
        print("  python tools/test_xsec_token.py --url \"https://www.xiaohongshu.com/explore/69983ebb00000000150304d8\"")
        return

    url = None
    if sys.argv[1] == '--url' and len(sys.argv) >= 3:
        url = sys.argv[2]
    elif sys.argv[1] == '--note-id' and len(sys.argv) >= 3:
        note_id = sys.argv[2]
        url = f"https://www.xiaohongshu.com/explore/{note_id}"

    if not url:
        print("❌ 请提供 --url 或 --note-id 参数")
        return

    print("=" * 70)
    print("小红书 xsec_token 提取测试")
    print("=" * 70)

    await test_extract_xsec_token(url)


if __name__ == "__main__":
    asyncio.run(main())
