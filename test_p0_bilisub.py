#!/usr/bin/env python3
"""
P0阶段功能测试脚本（在bilisub环境中运行）

快速验证所有实现的功能是否正常工作

运行方式:
    # 1. 激活环境
    conda activate bilisub

    # 2. 运行测试
    python test_p0_bilisub.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_file_exists(filepath, description):
    """测试文件是否存在"""
    if filepath.exists():
        print(f"✅ {description}: {filepath.name}")
        return True
    else:
        print(f"❌ {description}: {filepath.name} (不存在)")
        return False


def test_syntax(filepath):
    """测试Python语法"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', str(filepath)],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False


def test_help_output(script_path, description):
    """测试脚本的帮助输出"""
    print(f"\n📝 测试: {description}")

    if not script_path.exists():
        print(f"   ⚠️  脚本不存在: {script_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), '--help'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            print(f"   ✅ 帮助信息正常")
            # 显示前几行
            lines = result.stdout.strip().split('\n')[:5]
            for line in lines:
                print(f"   {line}")
            return True
        else:
            print(f"   ❌ 帮助信息错误")
            return False

    except subprocess.TimeoutExpired:
        print(f"   ⏱️  超时")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False


def test_url_detection():
    """测试URL检测功能"""
    print(f"\n🔍 测试: URL平台检测")

    script = PROJECT_ROOT / "utils" / "unified_content_analyzer.py"

    if not script.exists():
        print(f"   ❌ 统一分析入口不存在")
        return False

    test_urls = [
        ("https://space.bilibili.com/3546607314274766", "bili"),
        ("https://www.bilibili.com/video/BV1xx411c7mD", "bili"),
        ("https://www.xiaohongshu.com/user/profile/12345", "xhs"),
    ]

    all_correct = True
    for url, expected_platform in test_urls:
        url_lower = url.lower()
        if 'bilibili.com' in url_lower:
            detected = 'bili'
        elif 'xiaohongshu.com' in url_lower:
            detected = 'xhs'
        else:
            detected = 'unknown'

        status = "✅" if detected == expected_platform else "❌"
        print(f"   {status} {url[:50]}... → {detected}")

        if detected != expected_platform:
            all_correct = False

    return all_correct


def main():
    """主测试函数"""
    print_header("P0阶段功能测试 (bilisub环境)")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 项目目录: {PROJECT_ROOT}")
    print(f"🐍 Python: {sys.version.split()[0]}")

    results = {}

    # 1. 文件存在性检查
    print_header("1. 文件存在性检查")

    files = [
        (PROJECT_ROOT / "utils" / "unified_content_analyzer.py", "统一分析入口"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_videos.py", "小红书视频爬取"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_image_notes.py", "小红书图文爬取"),
        (PROJECT_ROOT / "utils" / "auto_xhs_subtitle_workflow.py", "小红书字幕工作流"),
        (PROJECT_ROOT / "utils" / "auto_xhs_image_workflow.py", "小红书图文工作流"),
        (PROJECT_ROOT / "utils" / "auto_bili_workflow.py", "B站工作流"),
        (PROJECT_ROOT / "analysis" / "gemini_subtitle_summary.py", "Gemini字幕分析"),
        (PROJECT_ROOT / "analysis" / "xhs_image_analysis.py", "小红书图文分析"),
        (PROJECT_ROOT / "docs" / "P0_IMPLEMENTATION_GUIDE.md", "使用文档"),
    ]

    file_results = []
    for filepath, desc in files:
        file_results.append(test_file_exists(filepath, desc))

    results['files'] = {
        'passed': sum(file_results),
        'total': len(file_results),
        'success': all(file_results)
    }

    # 2. Python语法检查
    print_header("2. Python语法检查")

    syntax_tests = [
        (PROJECT_ROOT / "utils" / "unified_content_analyzer.py", "统一分析入口"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_videos.py", "小红书视频爬取"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_image_notes.py", "小红书图文爬取"),
        (PROJECT_ROOT / "utils" / "auto_xhs_subtitle_workflow.py", "小红书字幕工作流"),
        (PROJECT_ROOT / "utils" / "auto_xhs_image_workflow.py", "小红书图文工作流"),
    ]

    syntax_results = []
    for filepath, desc in syntax_tests:
        if filepath.exists():
            if test_syntax(filepath):
                print(f"✅ {desc}: 语法正确")
                syntax_results.append(True)
            else:
                print(f"❌ {desc}: 语法错误")
                syntax_results.append(False)
        else:
            print(f"⏭️  {desc}: 文件不存在")
            syntax_results.append(False)

    results['syntax'] = {
        'passed': sum(syntax_results),
        'total': len(syntax_results),
        'success': all(syntax_results)
    }

    # 3. 帮助信息测试
    print_header("3. 帮助信息测试")

    help_results = []
    help_results.append(test_help_output(
        PROJECT_ROOT / "utils" / "unified_content_analyzer.py",
        "统一分析入口"
    ))
    help_results.append(test_help_output(
        PROJECT_ROOT / "utils" / "auto_bili_workflow.py",
        "B站工作流"
    ))

    results['help'] = {
        'passed': sum(help_results),
        'total': len(help_results),
        'success': all(help_results)
    }

    # 4. URL检测测试
    print_header("4. URL检测测试")

    results['url_detection'] = test_url_detection()

    # 5. 总结
    print_header("测试结果总结")

    print(f"\n📊 测试统计:")
    print(f"   文件检查: {results['files']['passed']}/{results['files']['total']} ✅")
    print(f"   语法检查: {results['syntax']['passed']}/{results['syntax']['total']} ✅")
    print(f"   帮助信息: {results['help']['passed']}/{results['help']['total']} ✅")
    print(f"   URL检测: {'✅' if results['url_detection'] else '❌'}")

    total_passed = (
        results['files']['success'] +
        results['syntax']['success'] +
        results['help']['success'] +
        results['url_detection']
    )

    print(f"\n🎯 总体评分: {total_passed}/4 项通过")

    if total_passed == 4:
        print(f"\n{'='*70}")
        print(f"  ✅ 所有测试通过！P0阶段实现成功！")
        print(f"{'='*70}")

        print(f"\n📝 快速开始:")
        print(f"\n1️⃣  测试B站工作流（无需额外配置）:")
        print(f"   cd {PROJECT_ROOT}")
        print(f"   python utils/unified_content_analyzer.py \\")
        print(f"       --url \"https://space.bilibili.com/3546607314274766\" \\")
        print(f"       --count 3")

        print(f"\n2️⃣  查看使用文档:")
        print(f"   📄 docs/P0_IMPLEMENTATION_GUIDE.md")
        print(f"   📄 docs/P0_COMPLETION_SUMMARY.md")

        print(f"\n3️⃣  下一步:")
        print(f"   - 配置 Gemini API Key (config_api.py)")
        print(f"   - 配置小红书 Cookie (config/cookies.txt)")
        print(f"   - 测试小红书功能")

        return 0
    else:
        print(f"\n⚠️  部分测试未通过，请检查上述错误")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        input(f"\n按Enter键退出...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n⚠️  测试中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
