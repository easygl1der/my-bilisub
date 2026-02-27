# -*- coding: utf-8 -*-
"""
小红书笔记评论爬取工具 (HTML 版 - v5)

功能：
1. 使用 Cookie 直接访问笔记页面
2. 从 HTML 中提取所有评论（单层扁平）
3. 在 Python 端按"回复 XXX : …"规则构建评论-回复树
4. 输出 JSON：每条顶级评论 + replies（不重复自己）

使用方法:
    python fetch_xhs_comments_v5.py "笔记链接"

需要先安装：
    pip install playwright
    playwright install chromium
"""

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from playwright.async_api import async_playwright

OUTPUT_DIR = Path("xhs_comments_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== JS：诊断 DOM，找评论相关类 ====================

_JS_DIAGNOSE = r"""
(function () {
    var result = {
        all_comment_related: [],
        sample_html: ""
    };

    var all_els = document.querySelectorAll("*");
    var seen_cls = {};
    for (var i = 0; i < all_els.length; i++) {
        var el = all_els[i];
        var cls = el.className;
        if (typeof cls === "string" && cls.toLowerCase().indexOf("comment") !== -1) {
            var parts = cls.trim().split(/\s+/);
            for (var j = 0; j < parts.length; j++) {
                var p = parts[j];
                if (p && !seen_cls[p]) {
                    seen_cls[p] = true;
                    var count = document.querySelectorAll("." + CSS.escape(p)).length;
                    result.all_comment_related.push({ cls: p, count: count });
                }
            }
        }
    }

    result.all_comment_related.sort(function (a, b) {
        return b.count - a.count;
    });

    if (result.all_comment_related.length > 0) {
        var topCls = result.all_comment_related[0].cls;
        var topEl = document.querySelector("." + CSS.escape(topCls));
        if (topEl) {
            result.sample_html = topEl.outerHTML.substring(0, 3000);
        }
    }

    return result;
})();
"""

# ==================== JS：扁平提取所有评论 ====================


def build_extract_js(root_cls: str) -> str:
    """
    根据根评论类名生成 JS，返回扁平列表：
    {id, nickname, content, like_count, create_time}
    """
    return rf"""
(function(rootCls) {{
    var comments = [];
    var seen = {{}};

    function getText(el) {{
        return el ? el.textContent.trim() : "";
    }}

    function getUniqueId(item, index) {{
        var id = item.getAttribute("data-id")
                || item.getAttribute("data-comment-id")
                || item.getAttribute("id")
                || "";
        if (!id) id = "comment_" + index;
        return id;
    }}

    function findContent(item) {{
        var candidates = [
            ".content", "[class*='content']",
            "[class*='text']", "[class*='body']",
            "span", "p"
        ];
        for (var k = 0; k < candidates.length; k++) {{
            var el = item.querySelector(candidates[k]);
            if (el) {{
                var t = el.textContent.trim();
                if (t.length > 2) return t;
            }}
        }}
        return item.textContent.trim().substring(0, 200);
    }}

    function findAuthor(item) {{
        var candidates = [
            "[class*='nick']", "[class*='name']",
            "[class*='author']", "[class*='user']",
            ".nickname", ".username"
        ];
        for (var k = 0; k < candidates.length; k++) {{
            var el = item.querySelector(candidates[k]);
            if (el) {{
                var t = el.textContent.trim();
                if (t.length > 0 && t.length < 50) return t;
            }}
        }}
        return "未知用户";
    }}

    function findTime(item) {{
        var candidates = [
            "[class*='time']", "[class*='date']",
            ".date", ".time", "time"
        ];
        for (var k = 0; k < candidates.length; k++) {{
            var el = item.querySelector(candidates[k]);
            if (el) return el.textContent.trim();
        }}
        return "";
    }}

    function findLikes(item) {{
        var candidates = [
            "[class*='like']", "[class*='count']",
            "[class*='thumb']", "[class*='heart']"
        ];
        for (var k = 0; k < candidates.length; k++) {{
            var el = item.querySelector(candidates[k]);
            if (el) {{
                var num = parseInt(el.textContent.replace(/[^0-9]/g, ""), 10);
                if (!isNaN(num)) return num;
            }}
        }}
        return 0;
    }}

    function parseItem(item, index) {{
        var commentId = getUniqueId(item, index);
        if (seen[commentId]) return null;
        seen[commentId] = true;

        var content = findContent(item);
        if (!content || content.length < 1) return null;

        // 查找父评论ID（支持多种属性格式）
        var parentCommentId = item.getAttribute("data-parent-id")
                        || item.getAttribute("data-reply-to")
                        || item.getAttribute("data-root-id")
                        || "";

        // 查找被回复者昵称（支持多种格式）
        var replyToEl = item.querySelector("[class*='reply-to'], [class*='at'], [class*='mention']");
        var replyToName = replyToEl ? replyToEl.textContent.replace(/@/g, '').trim() : "";

        return {{
            id:          commentId,
            parent_id:   parentCommentId,
            reply_to_name: replyToName,
            nickname:    findAuthor(item),
            content:     content,
            like_count:  findLikes(item),
            create_time: findTime(item)
        }};
    }}

    var rootItems = document.querySelectorAll("." + rootCls);
    var idx = 0;

    for (var i = 0; i < rootItems.length; i++) {{
        var root = rootItems[i];
        var data = parseItem(root, idx++);
        if (!data) continue;
        comments.push(data);
    }}

    return comments;
}})({json.dumps(root_cls)});
"""


# ==================== Cookie 管理 ====================


def load_cookies():
    cookie_file = Path("config/cookies.txt")
    if not cookie_file.exists():
        print("❌ Cookie文件不存在: config/cookies.txt")
        return None
    with open(cookie_file, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"xiaohongshu_full=([^\n]+)", content)
    if m:
        return m.group(1)
    xhs_section = re.search(r"\[xiaohongshu\](.*?)(\[|$)", content, re.DOTALL)
    if xhs_section:
        section = xhs_section.group(1)
        cookies = []
        for line in section.split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                cookies.append(f"{key.strip()}={value.strip()}")
        return "; ".join(cookies)
    return None


def parse_cookies(cookie_str):
    cookies = []
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookies.append(
                {
                    "name": key.strip(),
                    "value": value.strip(),
                    "domain": ".xiaohongshu.com",
                    "path": "/",
                }
            )
    return cookies


def extract_note_id(url):
    if "/explore/" in url:
        m = re.search(r"/explore/([a-f0-9]{24})", url)
        if m:
            return m.group(1)
    m = re.search(r"([a-f0-9]{24})", url, re.IGNORECASE)
    if m:
        return m.group(0)
    return None


# ==================== 评论提取器 ====================


class XHSCommentExtractor:
    def __init__(self, note_id: str):
        self.note_id = note_id
        self.root_cls: str | None = None

    async def diagnose_dom(self, page) -> bool:
        print("\n  🔍 诊断评论区 DOM 结构...")
        result = await page.evaluate(_JS_DIAGNOSE)

        classes = result.get("all_comment_related", [])
        if not classes:
            print("  ⚠️ 未找到包含 'comment' 的类名，可能未登录或评论区未加载")
            return False

        print("  📋 含 'comment' 的类名 (Top 20):")
        for item in classes[:20]:
            print(f"     .{item['cls']}  ({item['count']} 个元素)")

        # 简单策略：数量最多的类作为根评论
        self.root_cls = classes[0]["cls"]
        print(f"\n  ✅ 选定根评论类: .{self.root_cls} ({classes[0]['count']} 个元素)")

        if result.get("sample_html"):
            print("\n  🔎 第一个评论元素 HTML 片段（前 500 字符）:")
            print("  " + result["sample_html"][:500].replace("\n", "\n  "))

        return True

    async def extract_flat_comments(self, page):
        print("\n  📝 提取扁平评论列表...")
        if not self.root_cls:
            print("  ❌ 未确定根评论类，无法提取")
            return []

        js = build_extract_js(self.root_cls)
        comments = await page.evaluate(js)
        if not comments:
            print("  ⚠️ 未找到任何评论")
            return []

        print(f"  ✅ 扁平评论数: {len(comments)}")
        return comments

    def build_comment_tree(self, comments):
        """
        构建多层嵌套评论树

        支持:
        - 基于 parent_id 的直接关系（优先）
        - 基于 reply_to_name 的间接关系（回退）
        - 基于文本规则识别"回复 XXX : …"（最后回退）

        comments: [{id, parent_id, reply_to_name, nickname, content, like_count, create_time}]
        """
        # 构建ID到评论的映射
        id2node: dict[str, dict] = {c['id']: c for c in comments}

        # 作者 -> 点赞最高的那条评论（作为被回复 anchor）
        by_author: dict[str, dict] = {}
        for c in comments:
            name = c["nickname"]
            if name not in by_author or c["like_count"] > by_author[name]["like_count"]:
                by_author[name] = c

        # 初始化所有评论的replies
        for c in comments:
            c['replies'] = []

        # 构建树结构
        roots = []
        for c in comments:
            parent_id = c.get('parent_id', '')

            # 优先：基于parent_id构建直接关系
            if parent_id and parent_id in id2node:
                id2node[parent_id]['replies'].append(c)
                continue

            # 回退：基于reply_to_name构建（当parent_id不可用时）
            reply_to_name = c.get('reply_to_name', '')
            if reply_to_name:
                # 找到该作者的评论中点赞最高的作为父评论
                candidates = [n for n in comments if n['nickname'] == reply_to_name]
                if candidates:
                    best_parent = max(candidates, key=lambda x: x['like_count'])
                    best_parent['replies'].append(c)
                    continue

            # 最后回退：基于文本规则识别"回复 XXX : …"
            reply_pattern = re.compile(r"^回复\s+(.+?)\s*[:：]")
            m = reply_pattern.match(c.get("content", ""))
            if m:
                target_name = m.group(1).strip()
                # 避免自己回复自己
                if target_name != c["nickname"]:
                    anchor = by_author.get(target_name)
                    if anchor:
                        anchor['replies'].append(c)
                        continue

            # 既没有parent_id也没有reply_to_name也没有匹配文本，作为顶级评论
            roots.append(c)

        # 递归排序所有回复
        for r in roots:
            self._sort_replies(r)

        return roots

    def _sort_replies(self, node):
        """递归排序所有回复"""
        node['replies'].sort(key=lambda x: x['like_count'], reverse=True)
        for reply in node['replies']:
            self._sort_replies(reply)

    def save_json(self, tree, total):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"xhs_comments_{self.note_id}_{timestamp}.json"
        result = {
            "note_id": self.note_id,
            "total_comments": total,
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "comments": tree,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON 已保存: {output_file}")
        return output_file


# ==================== 主流程 ====================


async def main_async(url: str | None = None, headless: bool = False):
    print("\n" + "=" * 80)
    print("小红书笔记评论爬取工具 (HTML 版 - v5)")
    print("=" * 80)

    print("\n[步骤 1] 加载 Cookie")
    cookie_str = load_cookies()
    if not cookie_str:
        print("❌ 未找到有效 Cookie")
        return
    print("✅ Cookie 已加载")

    print("\n[步骤 2] 解析笔记链接")
    if not url:
        print("请输入小红书笔记链接:")
        url = input("笔记链接: ").strip()

    note_id = extract_note_id(url)
    if not note_id:
        print(f"❌ 无法从链接提取笔记 ID: {url}")
        return
    print(f"✅ 笔记 ID: {note_id}")

    page_url = url if "?xsec_token=" in url else f"https://www.xiaohongshu.com/explore/{note_id}"
    print(f"📝 页面 URL: {page_url}")

    print("\n[步骤 3] 访问页面并提取评论")
    print("-" * 80)
    print(f"浏览器模式: {'无头模式' if headless else '有头模式'}")

    extractor = XHSCommentExtractor(note_id)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        cookies = parse_cookies(cookie_str)

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        if cookies:
            await context.add_cookies(cookies)
            print(f"✅ 已设置 {len(cookies)} 个 Cookie")

        page = await context.new_page()
        print("\n📡 正在访问笔记页面...")
        print(f"   {page_url}")

        try:
            await page.goto(page_url, wait_until="networkidle", timeout=60000)
            print("✅ 页面加载成功")
            await asyncio.sleep(3)

            # 诊断 DOM
            ok = await extractor.diagnose_dom(page)
            if not ok:
                html = await page.content()
                debug_file = OUTPUT_DIR / f"debug_{note_id}.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"   调试 HTML 已保存: {debug_file}")
                await browser.close()
                return

            # 深度滚动 + 展开
            print("\n  🔄 正在深度加载评论（滚动 + 展开所有回复）...")
            count_sel = f".{extractor.root_cls}"

            last_count = 0
            stable_rounds = 0
            MAX_STABLE = 5
            MAX_LOOPS = 60

            for loop_i in range(MAX_LOOPS):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

                # 安全点击"展开/更多回复"，避免误点 a 链接
                try:
                    clicked = await page.evaluate(
                        r"""
                    (function() {
                        var clicked = 0;
                        var keywords = ['展开', '查看更多回复', '更多回复', '展开回复'];
                        var els = document.querySelectorAll('span, div, button');
                        for (var i = 0; i < els.length; i++) {
                            var el = els[i];
                            var txt = el.textContent.trim();
                            if (txt.length < 15 && keywords.some(function(k){ return txt.indexOf(k) !== -1; })) {
                                if (el.tagName !== 'A' && !el.closest('a') && !el.closest('[href]')) {
                                    try { el.click(); clicked++; } catch(e) {}
                                }
                            }
                        }
                        return clicked;
                    })()
                    """
                    )
                    if clicked > 0:
                        await asyncio.sleep(0.8)
                except Exception:
                    pass

                # 防止跳转到用户主页
                current_url = page.url
                if note_id not in current_url:
                    print(f"  ⚠️ 检测到页面跳转 ({current_url[:60]}...)，正在返回...")
                    await page.goto(page_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)

                current_count = await page.evaluate(
                    f"document.querySelectorAll({json.dumps(count_sel)}).length"
                )

                if current_count > last_count:
                    print(f"     [{loop_i+1}] 已发现 {current_count} 条评论项...")
                    last_count = current_count
                    stable_rounds = 0
                else:
                    stable_rounds += 1
                    if stable_rounds >= MAX_STABLE:
                        print(f"     连续 {MAX_STABLE} 次无新增，判定加载完毕")
                        break

            print(f"  ✅ 滚动完成，共 {last_count} 条评论项")

            # 扁平提取
            flat_comments = await extractor.extract_flat_comments(page)
            if not flat_comments:
                html = await page.content()
                debug_file = OUTPUT_DIR / f"debug_{note_id}.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"⚠️ 未提取到评论，调试 HTML 已保存: {debug_file}")
                await browser.close()
                return

            # 构建树
            print("\n  🌳 构建评论树（按赞数排序 + 回复挂载）...")
            tree = extractor.build_comment_tree(flat_comments)
            print("  ✅ 评论树构建完成")

            # 保存 JSON
            print("\n[步骤 4] 保存结果")
            extractor.save_json(tree, len(flat_comments))

            # 简要统计
            print("\n[步骤 5] 统计摘要")
            top_level = len(tree)
            reply_count = sum(len(t["replies"]) for t in tree)
            print("-" * 80)
            print(f"  总评论数（含回复）: {len(flat_comments)}")
            print(f"  顶级评论数        : {top_level}")
            print(f"  回复评论数        : {reply_count}")
            print("-" * 80)

            await browser.close()

        except Exception as e:
            print(f"\n❌ 爬取失败: {e}")
            import traceback

            traceback.print_exc()
            try:
                await browser.close()
            except Exception:
                pass

    print("\n" + "=" * 80)
    print("✅ 完成！")
    print("=" * 80 + "\n")


def main(url: str | None = None, headless: bool = False):
    asyncio.run(main_async(url, headless))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="小红书笔记评论爬取工具 (HTML 版 - v5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", nargs="?", help="小红书笔记链接")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    try:
        main(args.url, args.headless)
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback

        traceback.print_exc()
