"""
Playwright browser manager for JS-rendered pages.
Only used when plain HTTP fails or the source requires JS.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger

from scrapers.config import settings


class BrowserManager:
    """
    Lightweight wrapper around Playwright for selective use.

    Design: lazily instantiated — only pay the Playwright startup cost
    when we actually need a JS browser. Most Angolan government portals
    are server-rendered and don't need this.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.debug("Browser started (Chromium)")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.debug("Browser stopped")

    async def get_page_html(self, url: str) -> tuple[str, int]:
        """
        Navigate to URL and return (html_content, http_status).
        Uses a fresh context per page for isolation.
        """
        if not self._browser:
            raise RuntimeError("Browser not started.")

        context = await self._browser.new_context(
            user_agent=settings.HTTP_USER_AGENT,
            locale="pt-AO",
            extra_http_headers={
                "Accept-Language": "pt-AO,pt;q=0.9",
            },
        )
        try:
            page = await context.new_page()
            # Block heavy resources to speed up loading
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,mp4,woff,woff2,ttf,otf}",
                lambda route: route.abort(),
            )

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.BROWSER_TIMEOUT,
            )
            status = response.status if response else 0
            html = await page.content()
            logger.debug("Browser GET {} → {}", url, status)
            return html, status
        finally:
            await context.close()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator["BrowserManager", None]:
        await self.start()
        try:
            yield self
        finally:
            await self.stop()
