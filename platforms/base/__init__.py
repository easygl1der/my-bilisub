# -*- coding: utf-8 -*-
"""
Platform base module for BiliSub
Contains abstract base classes and browser utilities
"""

from .platform_base import AbstractCrawler, AbstractLogin, AbstractStore, AbstractApiClient
from .browser_launcher import BrowserLauncher
from .cdp_browser import CDPBrowserManager

__all__ = [
    'AbstractCrawler',
    'AbstractLogin',
    'AbstractStore',
    'AbstractApiClient',
    'BrowserLauncher',
    'CDPBrowserManager',
]
