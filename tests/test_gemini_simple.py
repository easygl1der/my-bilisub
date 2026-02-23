#!/usr/bin/env python3
"""
一键测试 Gemini 图文分析功能

用法：
    python test_gemini_simple.py
"""

import os
import sys
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    print("\n" + "=" * 80)
    print("🧪 Gemini 图文分析 - 一键测试")
    print("=" * 80)
    print()

    # 检查依赖
    print("📦 检查依赖...")
    try:
        import google.generativeai as genai
        print("   ✅ google-generativeai")
    except ImportError:
        print("   ❌ google-generativeai - 请运行: pip install google-generativeai")
        return

    try:
        from PIL import Image, ImageDraw, ImageFont
        print("   ✅ Pillow")
    except ImportError:
        print("   ❌ Pillow - 请运行: pip install Pillow")
        return

    # 检查 API Key
    print("\n🔑 检查 API Key...")
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        print("   ✅ 环境变量 GEMINI_API_KEY")
    else:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from config_api import API_CONFIG
            api_key = API_CONFIG.get('gemini', {}).get('api_key')
            if api_key:
                print("   ✅ config_api.py")
            else:
                print("   ❌ 未找到 GEMINI_API_KEY")
                print("\n   请设置环境变量或在 config_api.py 中配置")
                return
        except:
            print("   ❌ 未找到 GEMINI_API_KEY")
            return

    # 创建测试图片
    print("\n📸 创建测试图片...")
    test_dir = Path("test_gemini_images")
    test_dir.mkdir(exist_ok=True)

    # 清空旧图片
    for f in test_dir.glob("*"):
        f.unlink()

    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
    texts = ["美食", "旅行", "数码", "时尚", "生活"]

    for i, (color, text) in enumerate(zip(colors, texts), 1):
        img = Image.new('RGB', (600, 400), color)
        draw = ImageDraw.Draw(img)

        # 大字
        font_size = 60 if i == 0 else 40
        try:
            font = ImageFont.truetype("msyh.ttc", font_size)
        except:
            font = ImageFont.load_default()

        # 绘制文字
        draw.text((300, 180), text, fill="white", font=font, anchor="mm")
        draw.text((300, 240), f"测试图片 {i}", fill="white", font=font, anchor="mm")

        filepath = test_dir / f"image_{i}.jpg"
        img.save(filepath, quality=95)
        print(f"   ✅ {filepath.name}")

    # 调用分析脚本
    print("\n🤖 调用 Gemini 分析...")
    print("-" * 80)

    script_path = Path(__file__).parent / "analysis" / "multimodal_gemini.py"

    import subprocess
    test_text = "这是一组测试图片，包含美食、旅行、数码、时尚、生活等主题的标签图片。"

    cmd = [
        sys.executable,
        str(script_path),
        "--dir", str(test_dir),
        "--text", test_text,
        "--model", "flash-lite"
    ]

    print(f"命令: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "=" * 80)
        print("✅ 测试成功!")
        print("=" * 80)
        print(f"\n📁 测试图片: {test_dir.absolute()}")
        print(f"📁 分析结果: output/multimodal_analysis/")
    else:
        print("\n" + "=" * 80)
        print("❌ 测试失败，请检查错误信息")
        print("=" * 80)


if __name__ == "__main__":
    main()
