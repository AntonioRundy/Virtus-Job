"""
Database persistence layer for scraped opportunities.

Responsibilities:
- Map NormalisedOpportunity → SQLAlchemy Opportunity model
- Handle Organisation lookup / creation
- Save OpportunityCategory records
- Log the scraping run to scraping_logs
- Transaction management
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from scrapers.models import NormalisedOpportunity, ScrapeResult

# Import SQLAlchemy models from the API app
# PYTHONPATH must include the api/ directory (set in Dockerfile & runner)
try:
    from app.models.opportunity import Opportunity, OpportunityCategory
    from app.models.organization import Organization
    from app.models.scraping import ScrapingLog, ScrapingSource
except ImportError:
    logger.error(
        "Cannot import API models. Ensure PYTHONPATH includes 'apps/api'. "
        "If running locally: export PYTHONPATH=$PWD/apps/api"
    )
    raise


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[àáâãä]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")[:480] + "-" + uuid.uuid4().hex[:6]


class OpportunitySaver:
    """
    Persists a NormalisedOpportunity to PostgreSQL.

    Design: each save is a separate transaction so one failure
    doesn't block the rest of the batch.
    """

    def __init__(self, db: AsyncSession, dry_run: bool = False) -> None:
        self.db = db
        self.dry_run = dry_run

    async def save(self, record: NormalisedOpportunity) -> bool:
        """
        Persist one opportunity. Returns True if saved, False if skipped/failed.
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would save: {}", record.title[:70])
            return True

        try:
            org_id = await self._get_or_create_org(record.organization_name)
            source_db_id = await self._get_source_id(record.source_id)
            slug = _slugify(record.title)

            opp = Opportunity(
                slug=slug,
                title=record.title,
                type=record.type.value,
                status=record.status,
                description_structured=record.description_structured,
                requirements=json.dumps(record.requirements) if record.requirements else None,
                benefits=json.dumps(record.benefits) if record.benefits else None,
                tags=json.dumps(record.categories) if record.categories else None,
                province=record.province,
                municipality=record.municipality,
                salary_min=record.salary_min,
                salary_max=record.salary_max,
                salary_currency=record.salary_currency,
                source_url=record.source_url,
                source_name=record.source_name,
                deadline=record.deadline,
                published_at=record.published_at,
                extracted_at=record.extracted_at,
                ai_confidence_score=record.ai_confidence_score,
                requires_review=record.requires_review,
                ai_extracted=record.ai_extracted,
                organization_id=org_id,
                source_id=source_db_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(opp)
            await self.db.flush()

            for cat in record.categories:
                self.db.add(OpportunityCategory(opportunity_id=opp.id, category=cat))

            await self.db.commit()
            logger.success("Saved: '{}'", record.title[:70])
            return True

        except IntegrityError as e:
            await self.db.rollback()
            logger.warning("IntegrityError saving '{}': {}", record.title[:50], str(e)[:100])
            return False
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed saving '{}': {}", record.title[:50], e)
            return False

    async def _get_or_create_org(self, name: str | None) -> uuid.UUID | None:
        if not name:
            return None

        slug = _slugify(name)[:200]
        result = await self.db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        org = result.scalar_one_or_none()
        if org:
            return org.id

        org = Organization(
            name=name[:255],
            slug=slug,
            type="PUBLIC",
            is_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(org)
        await self.db.flush()
        logger.debug("Created organisation: {}", name)
        return org.id

    async def _get_source_id(self, source_id: str) -> uuid.UUID | None:
        result = await self.db.execute(
            select(ScrapingSource).where(ScrapingSource.name == source_id)
        )
        source = result.scalar_one_or_none()
        return source.id if source else None


class ScrapingLogger:
    """Persists scraping run results to the scraping_logs table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_run(self, result: ScrapeResult) -> None:
        source_id = await self._get_source_id(result.source_id)
        if not source_id:
            logger.warning("No DB source found for '{}' — skipping log", result.source_id)
            return

        log = ScrapingLog(
            source_id=source_id,
            started_at=result.started_at,
            finished_at=result.finished_at or datetime.now(timezone.utc),
            success=result.success,
            items_found=result.items_found,
            items_new=result.items_new,
            error_message="; ".join(result.errors[:5]) if result.errors else None,
        )
        self.db.add(log)

        # Update source stats
        source_result = await self.db.execute(
            select(ScrapingSource).where(ScrapingSource.name == result.source_id)
        )
        source = source_result.scalar_one_or_none()
        if source:
            source.last_scraped_at = datetime.now(timezone.utc)
            source.total_runs += 1
            source.total_found += result.items_found
            if result.success:
                source.last_success_at = datetime.now(timezone.utc)
            # Rolling success rate (last 10 runs approx)
            prev = source.success_rate
            source.success_rate = round((prev * 9 + (1.0 if result.success else 0.0)) / 10, 3)

        await self.db.commit()
        logger.info("Scraping log saved for '{}'", result.source_id)

    async def _get_source_id(self, source_name: str) -> uuid.UUID | None:
        result = await self.db.execute(
            select(ScrapingSource).where(ScrapingSource.name == source_name)
        )
        source = result.scalar_one_or_none()
        return source.id if source else None
