"""
AuthenticatedBrowserManager — extends BrowserManager with session injection.

Used by spiders that require a logged-in browser session (e.g. Jornal de Angola).
The base BrowserManager is unchanged and continues to work for public sources.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from scrapers.base.browser import BrowserManager
from scrapers.config import settings


class AuthenticatedBrowserManager(BrowserManager):
    """
    BrowserManager that injects a stored Playwright storage_state into every
    new browser context, ensuring all requests carry session cookies.

    Usage:
        auth_browser = AuthenticatedBrowserManager(storage_state)
        async with auth_browser.session():
            html, status = await auth_browser.get_page_html_authenticated(url)
    """

    def __init__(self, storage_state: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._storage_state = storage_state

    def set_storage_state(self, storage_state: dict[str, Any]) -> None:
        self._storage_state = storage_state

    async def get_page_html_authenticated(
        self,
        url: str,
        wait_for_selector: str | None = None,
    ) -> tuple[str, int]:
        """
        Fetch URL inside an authenticated browser context.

        - Injects saved session cookies / localStorage.
        - Optionally waits for a specific element to confirm page loaded.
        - Returns (html, http_status).
        """
        if not self._browser:
            raise RuntimeError("Browser not started — call start() first.")

        context_opts: dict[str, Any] = {
            "user_agent": settings.HTTP_USER_AGENT,
            "locale": "pt-AO",
            "extra_http_headers": {"Accept-Language": "pt-AO,pt;q=0.9"},
        }
        if self._storage_state:
            context_opts["storage_state"] = self._storage_state

        context = await self._browser.new_context(**context_opts)
        try:
            page = await context.new_page()

            # Block heavy assets (speeds up loading)
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,mp4,woff,woff2,ttf,otf,ico}",
                lambda route: route.abort(),
            )

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.BROWSER_TIMEOUT,
            )
            status = response.status if response else 0

            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=5000)
                except Exception:
                    pass  # selector not found — page still usable

            html = await page.content()
            logger.debug("Authenticated GET {} → {}", url, status)
            return html, status
        finally:
            await context.close()

    async def extract_storage_state(self) -> dict[str, Any]:
        """
        Create a fresh context and return its storage state.
        Useful for capturing updated cookies after a login redirect.
        """
        if not self._browser:
            raise RuntimeError("Browser not started.")
        context = await self._browser.new_context()
        state = await context.storage_state()
        await context.close()
        return state
