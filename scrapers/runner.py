"""
Scraping Runner — orchestrates the full pipeline.

Pipeline stages per URL:
  1. Dedup check (skip if already in DB)
  2. Fetch page (HTTP or browser)
  3. Parse HTML → plain text
  4. AI extraction → structured data
  5. Normalise → NormalisedOpportunity
  6. Save to PostgreSQL
  7. Log result

Each stage is independently error-handled so one bad URL
doesn't abort the entire run.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from scrapers.base.browser import BrowserManager
from scrapers.base.http_client import ScraperHTTPClient
from scrapers.base.spider import BaseSpider
from scrapers.config import settings
from scrapers.models import NormalisedOpportunity, ScrapeResult
from scrapers.pipeline.ai_extractor import AIExtractor
from scrapers.pipeline.deduplicator import Deduplicator
from scrapers.pipeline.normalizer import Normalizer
from scrapers.pipeline.saver import OpportunitySaver, ScrapingLogger
from scrapers.sources import REGISTRY


# ─── Database Session Factory ─────────────────────────────────────────────────

def _create_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


@asynccontextmanager
async def _db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = _create_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await engine.dispose()


# ─── Runner ──────────────────────────────────────────────────────────────────

class ScrapingRunner:
    """
    Orchestrates one full scraping run for one or more sources.

    Usage:
        runner = ScrapingRunner(dry_run=False)
        results = await runner.run(source_ids=["maptess"])
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run or settings.DRY_RUN
        self._ai = AIExtractor()
        self._normalizer = Normalizer()

    async def run(self, source_ids: list[str] | None = None) -> list[ScrapeResult]:
        """
        Run scraping for the given sources (or all active sources if None).
        Returns a list of ScrapeResult summaries.
        """
        targets = self._resolve_targets(source_ids)
        if not targets:
            logger.error("No active sources found for: {}", source_ids)
            return []

        results: list[ScrapeResult] = []
        for spider_cls in targets:
            spider: BaseSpider = spider_cls()
            result = await self._run_spider(spider)
            results.append(result)

        self._log_summary(results)
        return results

    async def _run_spider(self, spider: BaseSpider) -> ScrapeResult:
        result = ScrapeResult(
            source_id=spider.source_id,
            source_name=spider.source_name,
            started_at=datetime.now(timezone.utc),
        )

        logger.info("=" * 60)
        logger.info("Starting spider: {} [{}]", spider.source_name, spider.source_id)
        logger.info("=" * 60)

        try:
            async with _db_session() as db:
                dedup = Deduplicator(db)
                saver = OpportunitySaver(db, dry_run=self.dry_run)
                scraping_logger = ScrapingLogger(db)

                # Optionally start browser if source requires JS
                browser_ctx = (
                    spider.config.requires_js and BrowserManager().session()
                ) or _null_context()

                async with ScraperHTTPClient() as http:
                    async with browser_ctx as browser:
                        # Stage 1: Discover URLs
                        urls = await spider.discover_urls(http, browser)
                        result.items_found = len(urls)
                        logger.info("Discovered {} URLs", len(urls))

                        # Stage 2-6: Process each URL
                        for url in urls:
                            await self._process_url(
                                url, spider, http, browser, db,
                                dedup, saver, result,
                            )

                # Stage 7: Log the run
                result.finished_at = datetime.now(timezone.utc)
                result.success = result.items_failed == 0 or result.items_new > 0
                await scraping_logger.log_run(result)

        except Exception as e:
            logger.exception("Fatal error in spider {}: {}", spider.source_id, e)
            result.errors.append(str(e))
            result.finished_at = datetime.now(timezone.utc)
            result.success = False

        logger.info(
            "Spider {} finished: {} new | {} skipped | {} failed | {:.1f}s",
            spider.source_id,
            result.items_new,
            result.items_skipped_dup,
            result.items_failed,
            result.duration_seconds or 0,
        )
        return result

    async def _process_url(
        self,
        url: str,
        spider: BaseSpider,
        http: ScraperHTTPClient,
        browser,
        db: AsyncSession,
        dedup: Deduplicator,
        saver: OpportunitySaver,
        result: ScrapeResult,
    ) -> None:
        try:
            # Dedup check before fetching (save bandwidth + AI costs)
            if await dedup.is_duplicate(url):
                result.items_skipped_dup += 1
                return

            # Fetch
            raw = await spider.fetch_page(url, http, browser)
            if not raw.html and not raw.text:
                logger.warning("Empty response for {}", url)
                result.items_failed += 1
                return

            # Parse
            raw = await spider.parse_page(raw)
            if not raw.text or len(raw.text.strip()) < settings.MIN_CONTENT_LENGTH:
                logger.warning("Content too short for {}: {} chars", url, len(raw.text or ""))
                result.items_failed += 1
                return

            # AI Extraction
            extracted = await self._ai.extract(raw)

            # Low confidence and not marked for review? Skip silently
            if extracted.confidence < 0.2:
                logger.info("Very low confidence ({:.2f}) for {} — skipping", extracted.confidence, url)
                result.items_failed += 1
                return

            # Normalise
            normalised = self._normalizer.normalise(raw, extracted)

            # Save
            saved = await saver.save(normalised)
            if saved:
                result.items_new += 1
                dedup.mark_seen(url)
            else:
                result.items_failed += 1

        except Exception as e:
            logger.error("Error processing {}: {}", url, e)
            result.errors.append(f"{url}: {e}")
            result.items_failed += 1

    @staticmethod
    def _resolve_targets(source_ids: list[str] | None) -> list[type]:
        if source_ids is None or "all" in source_ids:
            return [cls for cls in REGISTRY.values() if cls.config.is_active]
        return [
            REGISTRY[sid]
            for sid in source_ids
            if sid in REGISTRY
        ]

    @staticmethod
    def _log_summary(results: list[ScrapeResult]) -> None:
        total_new = sum(r.items_new for r in results)
        total_dup = sum(r.items_skipped_dup for r in results)
        total_fail = sum(r.items_failed for r in results)
        logger.info("")
        logger.info("─── Run Summary ────────────────────────────")
        for r in results:
            status = "✓" if r.success else "✗"
            logger.info(
                "  {} {} | new={} | dup={} | fail={} | {:.1f}s",
                status, r.source_name,
                r.items_new, r.items_skipped_dup, r.items_failed,
                r.duration_seconds or 0,
            )
        logger.info("  Total: {} new | {} dup | {} failed", total_new, total_dup, total_fail)
        logger.info("─────────────────────────────────────────────")


@asynccontextmanager
async def _null_context():
    """No-op context manager for when browser is not needed."""
    yield None
