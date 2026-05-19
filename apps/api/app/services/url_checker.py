"""
Async source URL verifier.
Runs as a background task — never blocks the request/response cycle.

Status semantics:
  source_url_ok = True   → HTTP < 400 (confirmed reachable)
  source_url_ok = False  → HTTP 4xx/5xx (confirmed broken)
  source_url_ok = None   → unreachable from this environment (DNS/timeout —
                            may still work in a browser; do not flag as broken)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEADERS = {"User-Agent": "VirtusJob-URLChecker/1.0 (+https://virtus.ao)"}
MAX_REDIRECTS = 5


def is_absolute_url(url: str) -> bool:
    """Return True only for http:// or https:// URLs with a domain."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


async def check_url_reachable(url: str) -> tuple[bool | None, int | None]:
    """
    HEAD request to url. Falls back to GET if HEAD returns 405.

    Returns:
      (True, status)  — HTTP < 400
      (False, status) — HTTP 4xx/5xx
      (None, None)    — network/DNS error (can't verify from this environment)
    """
    if not is_absolute_url(url):
        return False, None
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers=HEADERS,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            resp = await client.head(url)
            if resp.status_code == 405:
                resp = await client.get(url)
            ok = resp.status_code < 400
            return ok, resp.status_code
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # DNS failure — mark as broken so frontend disables the link.
        # Better to show a warning than send users to a broken URL.
        logger.warning("URL DNS/connect failure: %s", url[:80])
        return False, None
    except httpx.TooManyRedirects:
        # Redirect loop — mark as broken
        logger.warning("URL too many redirects: %s", url[:80])
        return False, None
    except httpx.TimeoutException:
        logger.warning("URL check timeout: %s", url[:80])
        return None, None
    except Exception as exc:
        logger.warning("URL check unexpected error for %s: %s", url[:80], exc)
        return None, None


async def verify_opportunity_url(opportunity_id: uuid.UUID) -> None:
    """Background task: check one opportunity's source_url and update DB."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return

        ok, code = await check_url_reachable(opp.source_url)
        opp.source_url_ok = ok
        opp.source_url_checked_at = datetime.now(timezone.utc)
        await db.commit()

        if ok is True:
            status = f"OK (HTTP {code})"
        elif ok is False:
            status = f"BROKEN (HTTP {code})"
        else:
            status = "UNKNOWN (network unreachable from Docker)"
        logger.info("URL check [%s] %s → %s", opp.slug, opp.source_url[:60], status)


async def verify_all_urls() -> dict[str, bool | None]:
    """Check all opportunities without a recent URL verification. Returns slug→ok map."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Opportunity).where(Opportunity.source_url_checked_at.is_(None))
        )
        opps = result.scalars().all()

    results: dict[str, bool | None] = {}
    for opp in opps:
        ok, _ = await check_url_reachable(opp.source_url)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Opportunity).where(Opportunity.id == opp.id))
            record = result.scalar_one_or_none()
            if record:
                record.source_url_ok = ok
                record.source_url_checked_at = datetime.now(timezone.utc)
                await db.commit()
        results[opp.slug] = ok

    return results
