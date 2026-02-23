# -*- coding: utf-8 -*-
"""
平台检测器

从URL自动识别平台类型
"""

import re


class PlatformDetector:
    """平台检测器"""

    @staticmethod
    def detect(url: str) -> str:
        """
        从URL检测平台

        Args:
            url: URL字符串

        Returns:
            平台名称: 'bilibili' 或 'xiaohongshu'
        """
        url = url.lower().strip()

        # B站检测
        if any(domain in url for domain in ['bilibili.com', 'b23.tv']):
            return 'bilibili'

        # 小红书检测
        if any(domain in url for domain in ['xiaohongshu.com', 'xhslink.com']):
            return 'xiaohongshu'

        # 尝试通过内容特征检测
        # BV号格式 (BV + 10位字母数字)
        if re.search(r'BV[a-zA-Z0-9]{10}', url):
            return 'bilibili'

        # AV号格式 (av + 数字)
        if re.search(r'av\d+', url):
            return 'bilibili'

        # 笔记ID格式（24位十六进制）
        if re.search(r'[a-f0-9]{24}', url):
            return 'xiaohongshu'

        return 'unknown'
