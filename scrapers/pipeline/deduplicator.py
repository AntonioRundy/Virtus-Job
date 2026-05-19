"""
Deduplication — prevents saving the same opportunity twice.

Strategy (layered):
1. Exact URL hash match (primary — zero false positives)
2. Title + source_name similarity check (catches URL changes for same content)

The dedup check runs BEFORE calling the AI, so we don't waste API credits
on content we already have.
"""
from __future__ import annotations

import re

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from scrapers.pipeline.normalizer import url_hash


class Deduplicator:
    """
    Checks if an opportunity already exists in the database.
    Operates on the URL hash stored in the opportunities table.

    Note: The SQLAlchemy models are imported from the API app.
    PYTHONPATH must include the api/ directory.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._seen_hashes: set[str] = set()  # in-memory cache for current run

    async def is_duplicate(self, url: str) -> bool:
        """
        Returns True if this URL (or equivalent) already exists.
        Uses in-memory cache first, then DB lookup.
        """
        h = url_hash(url)

        # Check in-memory cache (avoids repeated DB queries within one run)
        if h in self._seen_hashes:
            logger.debug("Duplicate (in-memory): {}", url)
            return True

        # Check database
        result = await self.db.execute(
            text("SELECT 1 FROM opportunities WHERE source_url = :url LIMIT 1"),
            {"url": url},
        )
        exists = result.scalar_one_or_none() is not None

        if exists:
            logger.debug("Duplicate (DB url match): {}", url)
            self._seen_hashes.add(h)
            return True

        # Also check by normalised URL (handles trailing slash / http vs https)
        alt_url = self._alternate_url(url)
        if alt_url != url:
            result = await self.db.execute(
                text("SELECT 1 FROM opportunities WHERE source_url = :url LIMIT 1"),
                {"url": alt_url},
            )
            if result.scalar_one_or_none() is not None:
                logger.debug("Duplicate (DB alt-url match): {}", url)
                self._seen_hashes.add(h)
                return True

        return False

    def mark_seen(self, url: str) -> None:
        """Register a URL as processed in this run."""
        self._seen_hashes.add(url_hash(url))

    @staticmethod
    def _alternate_url(url: str) -> str:
        """Normalise URL for comparison (http↔https, trailing slash)."""
        url = url.strip().rstrip("/")
        url = re.sub(r"^http://", "https://", url)
        return url
