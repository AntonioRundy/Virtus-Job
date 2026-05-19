"""
Register scraping sources in the database.
Run once after the initial migration:
  docker compose exec scraper python -m scrapers.seed_sources
"""
import asyncio
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from scrapers.config import settings
from scrapers.sources import REGISTRY

try:
    from app.models.scraping import ScrapingSource
except ImportError:
    logger.error("Cannot import API models. Set PYTHONPATH to include apps/api.")
    raise


async def seed_sources() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        from sqlalchemy import select

        for source_id, spider_cls in REGISTRY.items():
            cfg = spider_cls.config

            result = await db.execute(
                select(ScrapingSource).where(ScrapingSource.name == source_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info("Source '{}' already exists — skipping", source_id)
                continue

            source = ScrapingSource(
                name=source_id,
                url=cfg.base_url,
                parser_type="HTML",
                schedule_cron=cfg.schedule_cron,
                is_active=cfg.is_active,
                requires_js=cfg.requires_js,
                created_at=datetime.now(timezone.utc),
            )
            db.add(source)
            logger.success("Registered source: {} ({})", source_id, cfg.name)

        await db.commit()

    await engine.dispose()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(seed_sources())
