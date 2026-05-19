import uuid
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OpportunityType(str, Enum):
    VAGA = "VAGA"
    CONCURSO = "CONCURSO"
    BOLSA = "BOLSA"
    ESTAGIO = "ESTAGIO"
    FORMACAO = "FORMACAO"


class OpportunityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    UNVERIFIED = "UNVERIFIED"
    DRAFT = "DRAFT"


class Modality(str, Enum):
    PRESENCIAL = "PRESENCIAL"
    REMOTO = "REMOTO"
    HIBRIDO = "HIBRIDO"


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    type: Mapped[OpportunityType] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[OpportunityStatus] = mapped_column(
        String(50), default=OpportunityStatus.UNVERIFIED, nullable=False, index=True
    )
    modality: Mapped[Modality | None] = mapped_column(String(50), nullable=True)

    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_structured: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)            # JSON array
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)                # JSON array
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)                    # JSON array

    # Location
    province: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    municipality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Compensation
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="AOA", nullable=False)

    # Source — always required for attribution
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # AI extraction metadata
    ai_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Dates
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Source verification
    source_url_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_url_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Trust system
    trust_level: Mapped[str] = mapped_column(
        String(30), default="UNVERIFIED", nullable=False, index=True
    )
    trust_score: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)

    # Application details — how to actually apply
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    application_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Stats
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    apply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    save_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relations
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    organization: Mapped["Organization | None"] = relationship(back_populates="opportunities")
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_sources.id", ondelete="SET NULL"), nullable=True
    )

    categories: Mapped[list["OpportunityCategory"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    saved_by: Mapped[list["SavedOpportunity"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Opportunity {self.title[:50]}>"


class OpportunityCategory(Base):
    __tablename__ = "opportunity_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="categories")


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_saved_opportunity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="saved_opportunities")
    opportunity: Mapped["Opportunity"] = relationship(back_populates="saved_by")
