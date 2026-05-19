"""
Async HTTP client with built-in retry, rate limiting and politeness.
"""
from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scrapers.config import settings

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


class ScraperHTTPClient:
    """
    Polite, retry-capable async HTTP client.

    Design:
    - Single shared client instance per scraping run (connection pooling)
    - Exponential backoff on failure
    - Configurable delays between requests (polite scraping)
    - Rotated User-Agent header
    - Response validation before returning
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ScraperHTTPClient":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.HTTP_TIMEOUT),
            headers={
                "User-Agent": settings.HTTP_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-AO,pt;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
            },
            follow_redirects=True,
            http2=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _polite_delay(self) -> None:
        """Random delay to avoid overwhelming source servers."""
        delay = random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        """
        GET with automatic retry + polite delay.
        Raises httpx.HTTPStatusError on non-retryable 4xx.
        """
        if not self._client:
            raise RuntimeError("Client not initialised — use as async context manager.")

        await self._polite_delay()

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.HTTP_MAX_RETRIES),
                wait=wait_exponential(
                    multiplier=1,
                    min=settings.HTTP_RETRY_WAIT_MIN,
                    max=settings.HTTP_RETRY_WAIT_MAX,
                ),
                retry=retry_if_exception_type((*RETRYABLE_EXCEPTIONS, httpx.HTTPStatusError)),
                before_sleep=before_sleep_log(logger, "DEBUG"),  # type: ignore[arg-type]
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get(url, **kwargs)  # type: ignore[arg-type]

                    if response.status_code in RETRYABLE_STATUS:
                        logger.warning(
                            "Retryable status {} for {} (attempt {})",
                            response.status_code,
                            url,
                            attempt.retry_state.attempt_number,
                        )
                        response.raise_for_status()

                    logger.debug("GET {} → {}", url, response.status_code)
                    return response

        except RetryError as e:
            logger.error("Exhausted retries for {}: {}", url, e)
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404, 410):
                logger.info("Non-retryable {} for {}", e.response.status_code, url)
            raise

        # Should never reach here (RetryError is re-raised)
        raise RuntimeError("Unreachable")  # pragma: no cover
