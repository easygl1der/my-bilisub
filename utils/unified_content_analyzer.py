#!/usr/bin/env python3
"""
统一多平台内容分析入口

支持的平台：
- B站（Bilibili）：视频分析
- 小红书（XiaohongShu）：视频分析、图文分析

功能：
1. 自动检测平台和内容类型
2. 路由到相应的工作流
3. 统一的参数接口
4. 统一的输出格式

使用示例:
    # 自动检测平台
    python unified_content_analyzer.py --url "任意链接"

    # B站用户主页
    python unified_content_analyzer.py --url "https://space.bilibili.com/3546607314274766"

    # 小红书用户主页（视频）
    python unified_content_analyzer.py --url "小红书用户链接" --mode subtitle

    # 小红书用户主页（图文）
    python unified_content_analyzer.py --url "小红书用户链接" --type image

    # 指定平台
    python unified_content_analyzer.py --platform bili --url "用户主页"
    python unified_content_analyzer.py --platform xhs --url "用户主页" --type video
"""

import os
import sys
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Literal

# 添加项目根目录到Python路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Windows编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== 配置 ====================

# 支持的平台
PlatformType = Literal['bili', 'xhs']
ContentType = Literal['video', 'image', 'auto']
AnalysisMode = Literal['subtitle', 'video', 'auto']

# 工作流脚本路径
BILI_WORKFLOW = PROJECT_ROOT / "utils" / "auto_bili_workflow.py"
XHS_SUBTITLE_WORKFLOW = PROJECT_ROOT / "utils" / "auto_xhs_subtitle_workflow.py"
XHS_IMAGE_WORKFLOW = PROJECT_ROOT / "utils" / "auto_xhs_image_workflow.py"

# ==================== URL路由器 ====================

class URLRouter:
    """URL路由器 - 自动检测平台和内容类型"""

    @staticmethod
    def detect_platform(url: str) -> Optional[PlatformType]:
        """
        检测平台类型

        Args:
            url: 内容链接

        Returns:
            平台类型 ('bili', 'xhs') 或 None
        """
        url = url.lower()

        if 'bilibili.com' in url:
            return 'bili'
        elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
            return 'xhs'
        else:
            return None

    @staticmethod
    def detect_content_type(url: str, platform: PlatformType) -> ContentType:
        """
        检测内容类型

        Args:
            url: 内容链接
            platform: 平台类型

        Returns:
            内容类型 ('video', 'image', 'auto')
        """
        url = url.lower()

        if platform == 'bili':
            # B站主要是视频
            return 'video'
        elif platform == 'xhs':
            # 小红书需要进一步判断
            # 如果是用户主页，默认为auto（后续处理时会根据实际笔记类型过滤）
            if '/user/profile/' in url:
                return 'auto'
            # 如果是单个笔记，尝试判断类型
            # TODO: 需要实际访问笔记才能确定类型，这里先返回auto
            return 'auto'

        return 'auto'

    @staticmethod
    def parse_url(url: str) -> Tuple[Optional[PlatformType], ContentType]:
        """
        解析URL，返回平台和内容类型

        Args:
            url: 内容链接

        Returns:
            (平台类型, 内容类型)
        """
        platform = URLRouter.detect_platform(url)
        if not platform:
            return None, 'auto'

        content_type = URLRouter.detect_content_type(url, platform)
        return platform, content_type


# ==================== 工作流执行器 ====================

class WorkflowExecutor:
    """工作流执行器 - 调用相应的工作流脚本"""

    @staticmethod
    def run_bili_workflow(url: str, count: int = None, mode: str = None,
                         incremental: bool = False, **kwargs) -> bool:
        """
        运行B站工作流

        Args:
            url: B站用户主页链接
            count: 处理数量
            mode: 分析模式
            incremental: 增量模式
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        print("\n" + "="*70)
        print("🎬 检测到B站内容，启动B站工作流")
        print("="*70)

        if not BILI_WORKFLOW.exists():
            print(f"❌ B站工作流脚本不存在: {BILI_WORKFLOW}")
            return False

        # 构建命令
        cmd = [sys.executable, str(BILI_WORKFLOW), '--url', url]

        if count:
            cmd.extend(['--count', str(count)])

        if incremental:
            cmd.append('--incremental')

        # 添加其他参数
        if kwargs.get('model'):
            cmd.extend(['--model', kwargs['model']])
        if kwargs.get('jobs'):
            cmd.extend(['--jobs', str(kwargs['jobs'])])

        print(f"📝 命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"❌ B站工作流执行失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 执行出错: {e}")
            return False

    @staticmethod
    def run_xhs_video_workflow(url: str, count: int = None, mode: str = 'subtitle',
                               **kwargs) -> bool:
        """
        运行小红书视频工作流

        Args:
            url: 小红书用户主页链接
            count: 处理数量
            mode: 分析模式 ('subtitle', 'video')
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        print("\n" + "="*70)
        print("📱 检测到小红书视频内容，启动小红书视频工作流")
        print("="*70)

        # 检查工作流脚本是否存在
        # 由于我们还没创建这个脚本，先提供简化版本
        if not XHS_SUBTITLE_WORKFLOW.exists():
            print(f"⚠️  小红书视频工作流脚本不存在: {XHS_SUBTITLE_WORKFLOW}")
            print(f"   提供基本功能:")
            print(f"   1. 爬取视频列表")
            print(f"   2. 下载字幕")
            print(f"   (AI分析功能待实现)")

            # 调用爬取脚本
            fetch_script = PROJECT_ROOT / "utils" / "fetch_xhs_videos.py"
            if fetch_script.exists():
                cmd = [sys.executable, str(fetch_script), '--url', url]
                if count:
                    cmd.extend(['--count', str(count)])

                try:
                    result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
                    return result.returncode == 0
                except Exception as e:
                    print(f"❌ 执行失败: {e}")
                    return False
            else:
                print(f"❌ 爬取脚本不存在: {fetch_script}")
                return False
        else:
            # 使用完整工作流（待实现）
            cmd = [sys.executable, str(XHS_SUBTITLE_WORKFLOW), '--url', url]
            if count:
                cmd.extend(['--count', str(count)])
            if mode:
                cmd.extend(['--mode', mode])

            try:
                result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
                return result.returncode == 0
            except Exception as e:
                print(f"❌ 执行失败: {e}")
                return False

    @staticmethod
    def run_xhs_image_workflow(url: str, count: int = None, **kwargs) -> bool:
        """
        运行小红书图文工作流

        Args:
            url: 小红书用户主页链接
            count: 处理数量
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        print("\n" + "="*70)
        print("📸 检测到小红书图文内容，启动小红书图文工作流")
        print("="*70)

        # 检查工作流脚本是否存在
        if not XHS_IMAGE_WORKFLOW.exists():
            print(f"⚠️  小红书图文工作流脚本不存在: {XHS_IMAGE_WORKFLOW}")
            print(f"   提供基本功能:")
            print(f"   1. 爬取图文列表")
            print(f"   2. 下载图片")
            print(f"   (AI分析功能待实现)")

            # 调用爬取脚本
            fetch_script = PROJECT_ROOT / "utils" / "fetch_xhs_image_notes.py"
            if fetch_script.exists():
                cmd = [sys.executable, str(fetch_script), '--url', url]
                if count:
                    cmd.extend(['--count', str(count)])

                try:
                    result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
                    return result.returncode == 0
                except Exception as e:
                    print(f"❌ 执行失败: {e}")
                    return False
            else:
                print(f"❌ 爬取脚本不存在: {fetch_script}")
                return False
        else:
            # 使用完整工作流（待实现）
            cmd = [sys.executable, str(XHS_IMAGE_WORKFLOW), '--url', url]
            if count:
                cmd.extend(['--count', str(count)])

            try:
                result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
                return result.returncode == 0
            except Exception as e:
                print(f"❌ 执行失败: {e}")
                return False


# ==================== 主程序 ====================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="统一多平台内容分析入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 自动检测平台
    python unified_content_analyzer.py --url "任意链接"

    # B站用户主页
    python unified_content_analyzer.py --url "https://space.bilibili.com/3546607314274766" --count 10

    # 小红书用户主页（视频，字幕分析）
    python unified_content_analyzer.py --url "小红书用户链接" --mode subtitle

    # 小红书用户主页（图文）
    python unified_content_analyzer.py --url "小红书用户链接" --type image

    # 指定平台
    python unified_content_analyzer.py --platform bili --url "用户主页"
    python unified_content_analyzer.py --platform xhs --url "用户主页" --type video
        """
    )

    parser.add_argument('-u', '--url', required=True,
                       help='内容链接（B站/小红书）')
    parser.add_argument('-p', '--platform',
                       choices=['bili', 'xhs', 'auto'],
                       default='auto',
                       help='平台类型（默认: auto自动检测）')
    parser.add_argument('-t', '--type',
                       choices=['video', 'image', 'auto'],
                       default='auto',
                       help='内容类型（默认: auto自动检测）')
    parser.add_argument('-m', '--mode',
                       choices=['subtitle', 'video', 'auto'],
                       default='auto',
                       help='分析模式（默认: auto）')
    parser.add_argument('-c', '--count', type=int,
                       help='处理数量限制')
    parser.add_argument('--incremental', action='store_true',
                       help='增量模式（跳过已处理的内容）')
    parser.add_argument('--model',
                       choices=['flash', 'flash-lite', 'pro'],
                       help='Gemini模型')
    parser.add_argument('-j', '--jobs', type=int,
                       help='并发处理数')

    args = parser.parse_args()

    # 打印欢迎信息
    print("\n" + "="*70)
    print("🎯 统一多平台内容分析系统")
    print("="*70)
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 链接: {args.url}")

    # URL路由
    router = URLRouter()

    # 检测平台
    if args.platform == 'auto':
        platform, content_type = router.parse_url(args.url)

        if not platform:
            print("\n❌ 无法识别的平台类型")
            print("   支持的平台: B站 (bilibili.com), 小红书 (xiaohongshu.com)")
            return 1

        print(f"\n✅ 自动检测结果:")
        print(f"   平台: {platform}")
        print(f"   内容类型: {content_type}")
    else:
        platform = args.platform
        content_type = args.type if args.type != 'auto' else 'video'
        print(f"\n✅ 手动指定:")
        print(f"   平台: {platform}")
        print(f"   内容类型: {content_type}")

    # 执行相应的工作流
    executor = WorkflowExecutor()
    success = False

    try:
        if platform == 'bili':
            # B站工作流
            success = executor.run_bili_workflow(
                url=args.url,
                count=args.count,
                mode=args.mode,
                incremental=args.incremental,
                model=args.model,
                jobs=args.jobs
            )

        elif platform == 'xhs':
            # 小红书工作流
            if content_type == 'image':
                # 图文工作流
                success = executor.run_xhs_image_workflow(
                    url=args.url,
                    count=args.count,
                    model=args.model
                )
            else:
                # 视频工作流
                mode = args.mode if args.mode != 'auto' else 'subtitle'
                success = executor.run_xhs_video_workflow(
                    url=args.url,
                    count=args.count,
                    mode=mode,
                    model=args.model,
                    jobs=args.jobs
                )

        else:
            print(f"\n❌ 暂不支持的平台: {platform}")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 结果
    print("\n" + "="*70)
    if success:
        print("✅ 分析完成!")
    else:
        print("❌ 分析失败")
    print("="*70)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
