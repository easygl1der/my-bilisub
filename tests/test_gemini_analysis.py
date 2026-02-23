#!/usr/bin/env python3
"""
创建测试图片并测试 Gemini 分析

由于小红书需要有效的 xsec_token，我们先创建一个测试图片来验证 Gemini 分析功能
"""

import sys
import subprocess
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def create_test_image():
    """创建一个简单的测试图片"""
    from PIL import Image, ImageDraw

    # 创建测试图片
    img_dir = Path("test_images_sample")
    img_dir.mkdir(exist_ok=True)

    # 创建3张测试图片
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1"]
    texts = ["测试图片1", "测试图片2", "测试图片3"]

    for i, (color, text) in enumerate(zip(colors, texts), 1):
        img = Image.new('RGB', (400, 300), color)
        draw = ImageDraw.Draw(img)

        # 添加文字
        draw.text((200, 150), text, fill="white", anchor="mm")

        # 保存
        filepath = img_dir / f"test_image_{i}.jpg"
        img.save(filepath)
        print(f"✅ 创建: {filepath}")

    return str(img_dir)


def test_gemini_analysis(image_dir: str):
    """测试 Gemini 分析"""
    print("\n" + "=" * 80)
    print("测试 Gemini 图文分析")
    print("=" * 80)
    print()

    script_path = Path(__file__).parent / "analysis" / "multimodal_gemini.py"

    # 测试文字
    test_text = "这是一组测试图片，用于验证 Gemini 多模态分析功能是否正常工作。"

    cmd = [
        sys.executable,
        str(script_path),
        "--dir", image_dir,
        "--text", test_text
    ]

    print(f"执行命令:")
    print(f"  python analysis/multimodal_gemini.py --dir {image_dir} --text \"{test_text}\"")
    print()

    result = subprocess.run(cmd, capture_output=False)

    return result.returncode == 0


def main():
    print("\n" + "=" * 80)
    print("小红书图文分析 - 测试脚本")
    print("=" * 80)
    print()

    # 检查依赖
    try:
        import PIL
    except ImportError:
        print("❌ 未安装 PIL，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=False)
        import PIL

    # 创建测试图片
    print("步骤1: 创建测试图片")
    print("-" * 80)
    img_dir = create_test_image()

    # 测试 Gemini 分析
    print("\n步骤2: 测试 Gemini 分析")
    print("-" * 80)
    success = test_gemini_analysis(img_dir)

    if success:
        print("\n✅ 测试完成!")
    else:
        print("\n❌ 测试失败")


if __name__ == "__main__":
    main()
