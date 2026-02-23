#!/usr/bin/env python3
"""
P0阶段功能测试脚本

快速验证所有实现的功能是否正常工作

运行方式:
    python test_p0_implementation.py
"""

import sys
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

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


def test_file_exists(filepath: Path, description: str) -> bool:
    """测试文件是否存在"""
    print(f"\n📁 {description}")
    print(f"   路径: {filepath}")

    if filepath.exists():
        print(f"   ✅ 存在")
        return True
    else:
        print(f"   ❌ 不存在")
        return False


def test_script_syntax(filepath: Path) -> bool:
    """测试Python脚本语法是否正确"""
    print(f"\n🔍 测试语法: {filepath.name}")

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', str(filepath)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"   ✅ 语法正确")
            return True
        else:
            print(f"   ❌ 语法错误:")
            print(f"   {result.stderr}")
            return False

    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        return False


def test_import_module(module_name: str, filepath: Path) -> bool:
    """测试模块是否可以导入"""
    print(f"\n📦 测试导入: {module_name}")

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None:
            print(f"   ❌ 无法创建模块规范")
            return False

        module = importlib.util.module_from_spec(spec)

        # 尝试执行模块
        spec.loader.exec_module(module)

        print(f"   ✅ 导入成功")
        return True

    except Exception as e:
        print(f"   ⚠️  导入失败（可能缺少依赖）: {str(e)[:100]}")
        return False


def test_unified_analyzer_help():
    """测试统一分析入口的帮助信息"""
    print(f"\n🎯 测试统一分析入口")

    script = PROJECT_ROOT / "utils" / "unified_content_analyzer.py"

    if not script.exists():
        print(f"   ❌ 脚本不存在")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script), '--help'],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            print(f"   ✅ 帮助信息正常")
            print(f"\n   帮助内容预览:")
            lines = result.stdout.split('\n')[:10]
            for line in lines:
                print(f"   {line}")
            return True
        else:
            print(f"   ❌ 帮助信息错误")
            return False

    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print_header("P0阶段功能测试")
    print(f"📅 测试时间: {__import__('datetime').datetime.now()}")
    print(f"📂 项目根目录: {PROJECT_ROOT}")

    # 测试结果
    results = {}

    # 1. 测试核心文件是否存在
    print_header("1. 文件存在性检查")

    files_to_check = [
        (PROJECT_ROOT / "utils" / "unified_content_analyzer.py", "统一分析入口"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_videos.py", "小红书视频爬取工具"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_image_notes.py", "小红书图文爬取工具"),
        (PROJECT_ROOT / "utils" / "auto_xhs_subtitle_workflow.py", "小红书视频字幕工作流"),
        (PROJECT_ROOT / "utils" / "auto_xhs_image_workflow.py", "小红书图文分析工作流"),
        (PROJECT_ROOT / "utils" / "auto_bili_workflow.py", "B站工作流（已存在）"),
        (PROJECT_ROOT / "analysis" / "gemini_subtitle_summary.py", "Gemini字幕分析（已存在）"),
        (PROJECT_ROOT / "analysis" / "xhs_image_analysis.py", "小红书图文分析（已存在）"),
        (PROJECT_ROOT / "docs" / "P0_IMPLEMENTATION_GUIDE.md", "P0使用文档"),
    ]

    file_check_results = []
    for filepath, description in files_to_check:
        file_check_results.append(test_file_exists(filepath, description))

    results['files_exist'] = all(file_check_results)
    results['files_count'] = sum(file_check_results)
    results['files_total'] = len(file_check_results)

    # 2. 测试Python脚本语法
    print_header("2. Python语法检查")

    syntax_tests = [
        (PROJECT_ROOT / "utils" / "unified_content_analyzer.py", "统一分析入口"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_videos.py", "小红书视频爬取"),
        (PROJECT_ROOT / "utils" / "fetch_xhs_image_notes.py", "小红书图文爬取"),
        (PROJECT_ROOT / "utils" / "auto_xhs_subtitle_workflow.py", "小红书视频工作流"),
        (PROJECT_ROOT / "utils" / "auto_xhs_image_workflow.py", "小红书图文工作流"),
    ]

    syntax_results = []
    for filepath, description in syntax_tests:
        if filepath.exists():
            syntax_results.append(test_script_syntax(filepath))
        else:
            print(f"\n⏭️  跳过: {description}（文件不存在）")
            syntax_results.append(False)

    results['syntax'] = all(syntax_results)
    results['syntax_count'] = sum(syntax_results)
    results['syntax_total'] = len(syntax_results)

    # 3. 测试模块导入
    print_header("3. 模块导入测试")

    import_tests = [
        ("utils.unified_content_analyzer", PROJECT_ROOT / "utils" / "unified_content_analyzer.py"),
        ("utils.fetch_xhs_videos", PROJECT_ROOT / "utils" / "fetch_xhs_videos.py"),
    ]

    import_results = []
    for module_name, filepath in import_tests:
        if filepath.exists():
            import_results.append(test_import_module(module_name, filepath))
        else:
            import_results.append(False)

    results['imports'] = all(import_results)

    # 4. 测试统一分析入口
    print_header("4. 统一分析入口功能测试")

    results['unified_analyzer'] = test_unified_analyzer_help()

    # 5. 总结
    print_header("测试结果总结")

    total_tests = 4
    passed_tests = sum([
        results['files_exist'],
        results['syntax'],
        results['imports'],
        results['unified_analyzer']
    ])

    print(f"\n📊 测试统计:")
    print(f"   文件检查: {results['files_count']}/{results['files_total']} 通过")
    print(f"   语法检查: {results['syntax_count']}/{results['syntax_total']} 通过")
    print(f"   总体通过: {passed_tests}/{total_tests}")

    if passed_tests == total_tests:
        print(f"\n✅ 所有测试通过！P0阶段实现成功！")

        print(f"\n📝 下一步:")
        print(f"   1. 查看使用文档: docs/P0_IMPLEMENTATION_GUIDE.md")
        print(f"   2. 测试B站工作流:")
        print(f"      python utils/unified_content_analyzer.py --url \"https://space.bilibili.com/3546607314274766\" --count 5")
        print(f"   3. 测试小红书功能（需要配置Cookie）")

        return 0
    else:
        print(f"\n⚠️  部分测试未通过，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
