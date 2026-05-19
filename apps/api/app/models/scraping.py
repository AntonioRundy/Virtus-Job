import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParserType(str, Enum):
    HTML = "HTML"
    PDF = "PDF"
    API = "API"
    RSS = "RSS"


class ScrapingSource(Base):
    __tablename__ = "scraping_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    parser_type: Mapped[ParserType] = mapped_column(String(20), default=ParserType.HTML)
    schedule_cron: Mapped[str] = mapped_column(String(100), default="0 */6 * * *")  # every 6h
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Trust classification — set when source is registered and updated by curators
    trust_level: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", nullable=False)

    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
