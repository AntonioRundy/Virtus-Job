"""
Abstract base class for all Virtus Job spiders.

Every source spider must implement this interface. This enforces
consistent behaviour across sources and makes the runner source-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from scrapers.base.browser import BrowserManager
from scrapers.base.http_client import ScraperHTTPClient
from scrapers.models import RawPage, ScrapeResult


@dataclass
class SourceConfig:
    """
    Declarative configuration for a scraping source.
    Defined once per spider — used by the runner and registry.
    """
    id: str                          # machine-readable slug  e.g. "maptess"
    name: str                        # human-readable name
    base_url: str                    # homepage / entry URL
    requires_js: bool = False        # needs Playwright?
    is_active: bool = True
    schedule_cron: str = "0 */6 * * *"   # every 6 hours
    rate_limit_delay: float = 3.0    # seconds between requests
    tags: list[str] = field(default_factory=list)


class BaseSpider(ABC):
    """
    Abstract spider base class.

    Subclasses implement:
    - config: SourceConfig
    - discover_urls(client, browser) → list[str]  — find opportunity URLs
    - fetch_page(url, client, browser) → RawPage  — fetch one page
    - parse_page(raw) → RawPage                   — clean/prepare for AI

    The pipeline (AI extraction, normalisation, saving) is handled
    by the runner — spiders only deal with HTTP and HTML.
    """

    config: SourceConfig

    def __init__(self) -> None:
        self._result: ScrapeResult | None = None

    @property
    def source_id(self) -> str:
        return self.config.id

    @property
    def source_name(self) -> str:
        return self.config.name

    # ─── Abstract interface ──────────────────────────────────────────────────

    @abstractmethod
    async def discover_urls(
        self,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> list[str]:
        """
        Return a list of detail-page URLs to scrape.
        Must not exceed settings.MAX_ITEMS_PER_SOURCE items.
        """

    @abstractmethod
    async def fetch_page(
        self,
        url: str,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> RawPage:
        """Fetch a single detail page and return a RawPage."""

    @abstractmethod
    async def parse_page(self, raw: RawPage) -> RawPage:
        """
        Extract plain text from the raw HTML.
        Should populate raw.text with content relevant for AI extraction.
        Should NOT call the AI — that happens in the pipeline.
        """

    # ─── Concrete helpers ───────────────────────────────────────────────────

    def log(self, level: str, msg: str, *args: object) -> None:
        getattr(logger.bind(spider=self.source_id), level)(msg, *args)

    def _build_result(self) -> ScrapeResult:
        return ScrapeResult(
            source_id=self.source_id,
            source_name=self.source_name,
            started_at=datetime.utcnow(),
        )
