# -*- coding: utf-8 -*-
"""
CDP browser manager for launching and managing browsers via Chrome DevTools Protocol
Ported from MediaCrawler for BiliSub
"""

import os
import asyncio
import socket
import httpx
import signal
import atexit
import logging
from typing import Optional, Dict, Any
from playwright.async_api import Browser, BrowserContext, Playwright

from .browser_launcher import BrowserLauncher

logger = logging.getLogger(__name__)


class CDPBrowserManager:
    """
    CDP browser manager, responsible for launching and managing browsers connected via CDP
    """

    def __init__(self, cdp_debug_port: int = 9222, browser_path: Optional[str] = None,
                 auto_close_browser: bool = True):
        """
        Initialize CDP browser manager

        :param cdp_debug_port: CDP debug port (default: 9222)
        :param browser_path: Custom browser path (auto-detect if None)
        :param auto_close_browser: Whether to auto-close browser on cleanup
        """
        self.launcher = BrowserLauncher()
        self.browser: Optional[Browser] = None
        self.browser_context: Optional[BrowserContext] = None
        self.debug_port: Optional[int] = None
        self._cleanup_registered = False

        # Configuration
        self.cdp_debug_port = cdp_debug_port
        self.custom_browser_path = browser_path
        self.auto_close_browser = auto_close_browser

    def _register_cleanup_handlers(self):
        """
        Register cleanup handlers to ensure browser process cleanup on program exit
        """
        if self._cleanup_registered:
            return

        def sync_cleanup():
            """Synchronous cleanup function for atexit"""
            if self.launcher and self.launcher.browser_process:
                logger.info("[CDPBrowserManager] atexit: Cleaning up browser process")
                self.launcher.cleanup()

        # Register atexit cleanup
        atexit.register(sync_cleanup)

        # Register signal handlers
        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)

        def signal_handler(signum, frame):
            """Signal handler"""
            logger.info(f"[CDPBrowserManager] Received signal {signum}, cleaning up browser process")
            if self.launcher and self.launcher.browser_process:
                self.launcher.cleanup()

            if signum == signal.SIGINT:
                if prev_sigint == signal.default_int_handler:
                    return prev_sigint(signum, frame)
                raise KeyboardInterrupt

            raise SystemExit(0)

        install_sigint = prev_sigint in (signal.default_int_handler, signal.SIG_DFL)
        install_sigterm = prev_sigterm == signal.SIG_DFL

        # Register SIGINT (Ctrl+C) and SIGTERM
        if install_sigint:
            signal.signal(signal.SIGINT, signal_handler)
        else:
            logger.info("[CDPBrowserManager] SIGINT handler already exists, skipping registration")

        if install_sigterm:
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            logger.info("[CDPBrowserManager] SIGTERM handler already exists, skipping registration")

        self._cleanup_registered = True
        logger.info("[CDPBrowserManager] Cleanup handlers registered")

    async def launch_and_connect(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = False,
        user_data_dir: Optional[str] = None,
    ) -> BrowserContext:
        """
        Launch browser and connect via CDP
        """
        try:
            # 1. Detect browser path
            browser_path = await self._get_browser_path()

            # 2. Get available port
            self.debug_port = self.launcher.find_available_port(self.cdp_debug_port)

            # 3. Launch browser
            await self._launch_browser(browser_path, headless, user_data_dir)

            # 4. Register cleanup handlers (ensure cleanup on abnormal exit)
            self._register_cleanup_handlers()

            # 5. Connect via CDP
            await self._connect_via_cdp(playwright)

            # 6. Create browser context
            browser_context = await self._create_browser_context(
                playwright_proxy, user_agent
            )

            self.browser_context = browser_context
            return browser_context

        except Exception as e:
            logger.error(f"[CDPBrowserManager] CDP browser launch failed: {e}")
            await self.cleanup()
            raise

    async def _get_browser_path(self) -> str:
        """Get browser path"""
        # Prefer user-defined path
        if self.custom_browser_path and os.path.isfile(self.custom_browser_path):
            logger.info(
                f"[CDPBrowserManager] Using custom browser path: {self.custom_browser_path}"
            )
            return self.custom_browser_path

        # Auto-detect browser path
        browser_paths = self.launcher.detect_browser_paths()

        if not browser_paths:
            raise RuntimeError(
                "No available browser found. Please ensure Chrome or Edge browser is installed, "
                "or set custom_browser_path when initializing CDPBrowserManager."
            )

        browser_path = browser_paths[0]  # Use first browser found
        browser_name, browser_version = self.launcher.get_browser_info(browser_path)

        logger.info(
            f"[CDPBrowserManager] Detected browser: {browser_name} ({browser_version})"
        )
        logger.info(f"[CDPBrowserManager] Browser path: {browser_path}")

        return browser_path

    async def _test_cdp_connection(self, debug_port: int) -> bool:
        """Test if CDP connection is available"""
        try:
            # Simple socket connection test
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(("localhost", debug_port))
                if result == 0:
                    logger.info(
                        f"[CDPBrowserManager] CDP port {debug_port} is accessible"
                    )
                    return True
                else:
                    logger.warning(
                        f"[CDPBrowserManager] CDP port {debug_port} is not accessible"
                    )
                    return False
        except Exception as e:
            logger.warning(f"[CDPBrowserManager] CDP connection test failed: {e}")
            return False

    async def _launch_browser(self, browser_path: str, headless: bool, user_data_dir: Optional[str]):
        """Launch browser process"""
        # Launch browser
        self.launcher.browser_process = self.launcher.launch_browser(
            browser_path=browser_path,
            debug_port=self.debug_port,
            headless=headless,
            user_data_dir=user_data_dir,
        )

        # Wait for browser to be ready
        browser_launch_timeout = 30
        if not self.launcher.wait_for_browser_ready(self.debug_port, browser_launch_timeout):
            raise RuntimeError(f"Browser failed to start within {browser_launch_timeout} seconds")

        # Extra wait for CDP service to fully start
        await asyncio.sleep(1)

        # Test CDP connection
        if not await self._test_cdp_connection(self.debug_port):
            logger.warning(
                "[CDPBrowserManager] CDP connection test failed, but will continue to try connecting"
            )

    async def _get_browser_websocket_url(self, debug_port: int) -> str:
        """Get browser WebSocket connection URL"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{debug_port}/json/version", timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        logger.info(
                            f"[CDPBrowserManager] Got browser WebSocket URL: {ws_url}"
                        )
                        return ws_url
                    else:
                        raise RuntimeError("webSocketDebuggerUrl not found")
                else:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"[CDPBrowserManager] Failed to get WebSocket URL: {e}")
            raise

    async def _connect_via_cdp(self, playwright: Playwright):
        """Connect to browser via CDP"""
        try:
            # Get correct WebSocket URL
            ws_url = await self._get_browser_websocket_url(self.debug_port)
            logger.info(f"[CDPBrowserManager] Connecting to browser via CDP: {ws_url}")

            # Use Playwright's connectOverCDP method to connect
            self.browser = await playwright.chromium.connect_over_cdp(ws_url)

            if self.browser.is_connected():
                logger.info("[CDPBrowserManager] Successfully connected to browser")
                logger.info(
                    f"[CDPBrowserManager] Browser contexts count: {len(self.browser.contexts)}"
                )
            else:
                raise RuntimeError("CDP connection failed")

        except Exception as e:
            logger.error(f"[CDPBrowserManager] CDP connection failed: {e}")
            raise

    async def _create_browser_context(
        self, playwright_proxy: Optional[Dict] = None, user_agent: Optional[str] = None
    ) -> BrowserContext:
        """Create or get browser context"""
        if not self.browser:
            raise RuntimeError("Browser not connected")

        # Get existing context or create new context
        contexts = self.browser.contexts

        if contexts:
            # Use existing first context
            browser_context = contexts[0]
            logger.info("[CDPBrowserManager] Using existing browser context")
        else:
            # Create new context
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "accept_downloads": True,
            }

            # Set user agent
            if user_agent:
                context_options["user_agent"] = user_agent
                logger.info(f"[CDPBrowserManager] Setting user agent: {user_agent}")

            # Note: Proxy settings may not work in CDP mode since browser is already launched
            if playwright_proxy:
                logger.warning(
                    "[CDPBrowserManager] Warning: Proxy settings may not work in CDP mode, "
                    "recommend configuring system proxy or browser proxy extension before launching browser"
                )

            browser_context = await self.browser.new_context(**context_options)
            logger.info("[CDPBrowserManager] Created new browser context")

        return browser_context

    async def add_stealth_script(self, script_path: str):
        """Add anti-detection script"""
        if self.browser_context and os.path.exists(script_path):
            try:
                await self.browser_context.add_init_script(path=script_path)
                logger.info(
                    f"[CDPBrowserManager] Added anti-detection script: {script_path}"
                )
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] Failed to add anti-detection script: {e}")

    async def add_cookies(self, cookies: list):
        """Add cookies"""
        if self.browser_context:
            try:
                await self.browser_context.add_cookies(cookies)
                logger.info(f"[CDPBrowserManager] Added {len(cookies)} cookies")
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] Failed to add cookies: {e}")

    async def get_cookies(self) -> list:
        """Get current cookies"""
        if self.browser_context:
            try:
                cookies = await self.browser_context.cookies()
                return cookies
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] Failed to get cookies: {e}")
                return []
        return []

    async def cleanup(self, force: bool = False):
        """
        Cleanup resources

        :param force: Whether to force cleanup browser process (ignoring auto_close_browser config)
        """
        try:
            # Close browser context
            if self.browser_context:
                try:
                    # Check if context is already closed
                    try:
                        pages = self.browser_context.pages
                        if pages is not None:
                            await self.browser_context.close()
                            logger.info("[CDPBrowserManager] Browser context closed")
                    except:
                        logger.debug("[CDPBrowserManager] Browser context already closed")
                except Exception as context_error:
                    # Only log warning if error is not due to already being closed
                    error_msg = str(context_error).lower()
                    if "closed" not in error_msg and "disconnected" not in error_msg:
                        logger.warning(
                            f"[CDPBrowserManager] Failed to close browser context: {context_error}"
                        )
                    else:
                        logger.debug(f"[CDPBrowserManager] Browser context already closed: {context_error}")
                finally:
                    self.browser_context = None

            # Disconnect browser
            if self.browser:
                try:
                    # Check if browser is still connected
                    if self.browser.is_connected():
                        await self.browser.close()
                        logger.info("[CDPBrowserManager] Browser connection disconnected")
                    else:
                        logger.debug("[CDPBrowserManager] Browser connection already disconnected")
                except Exception as browser_error:
                    # Only log warning if error is not due to already being closed
                    error_msg = str(browser_error).lower()
                    if "closed" not in error_msg and "disconnected" not in error_msg:
                        logger.warning(
                            f"[CDPBrowserManager] Failed to close browser connection: {browser_error}"
                        )
                    else:
                        logger.debug(f"[CDPBrowserManager] Browser connection already disconnected: {browser_error}")
                finally:
                    self.browser = None

            # Close browser process
            if force or self.auto_close_browser:
                if self.launcher and self.launcher.browser_process:
                    self.launcher.cleanup()
                else:
                    logger.debug("[CDPBrowserManager] No browser process to cleanup")
            else:
                logger.info(
                    "[CDPBrowserManager] Browser process kept running (auto_close_browser=False)"
                )

        except Exception as e:
            logger.error(f"[CDPBrowserManager] Error during resource cleanup: {e}")

    def is_connected(self) -> bool:
        """Check if connected to browser"""
        return self.browser is not None and self.browser.is_connected()

    async def get_browser_info(self) -> Dict[str, Any]:
        """Get browser info"""
        if not self.browser:
            return {}

        try:
            version = self.browser.version
            contexts_count = len(self.browser.contexts)

            return {
                "version": version,
                "contexts_count": contexts_count,
                "debug_port": self.debug_port,
                "is_connected": self.is_connected(),
            }
        except Exception as e:
            logger.warning(f"[CDPBrowserManager] Failed to get browser info: {e}")
            return {}
