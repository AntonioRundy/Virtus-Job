"""
Internal Pydantic models for the scraping pipeline.
These are NOT the SQLAlchemy ORM models — they represent data in transit.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class OpportunityType(str, Enum):
    VAGA = "VAGA"
    CONCURSO = "CONCURSO"
    BOLSA = "BOLSA"
    ESTAGIO = "ESTAGIO"
    FORMACAO = "FORMACAO"


# ─── Raw Scraped Page ────────────────────────────────────────────────────────

class RawPage(BaseModel):
    """Raw data fetched from source before any processing."""

    url: str
    source_name: str
    source_id: str               # slug identifier of the source
    html: str | None = None      # full HTML (not stored, only used in pipeline)
    text: str | None = None      # extracted plain text
    title: str | None = None     # <title> tag content
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    requires_js: bool = False
    http_status: int = 200

    @field_validator("text", mode="before")
    @classmethod
    def truncate_text(cls, v: str | None) -> str | None:
        """Prevent sending massive texts to AI."""
        if v and len(v) > 12000:
            return v[:12000]
        return v


# ─── AI Extraction Result ────────────────────────────────────────────────────

class SalaryRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "AOA"


class AIExtractionResult(BaseModel):
    """Validated output from the AI extraction step."""

    title: str
    type: OpportunityType
    description: str = ""                    # 2-5 sentence summary
    organization: str | None = None
    province: str | None = None
    municipality: str | None = None
    deadline: date | None = None
    requirements: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    salary_range: SalaryRange | None = None
    categories: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    requires_review: bool = False
    raw_deadline_text: str | None = None     # original deadline string for debugging

    @field_validator("province", mode="before")
    @classmethod
    def validate_province(cls, v: str | None) -> str | None:
        if not v:
            return None
        valid = {
            "Luanda", "Benguela", "Huambo", "Bié", "Malanje", "Kuanza Sul",
            "Uíge", "Zaire", "Cabinda", "Cunene", "Huíla", "Kuando Kubango",
            "Kuanza Norte", "Lunda Norte", "Lunda Sul", "Moxico", "Namibe", "Bengo",
        }
        # Case-insensitive match
        for prov in valid:
            if prov.lower() == v.strip().lower():
                return prov
        return v.strip() if v.strip() else None

    @field_validator("categories", mode="before")
    @classmethod
    def limit_categories(cls, v: list) -> list:
        return v[:6] if v else []

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# ─── Normalised Opportunity ──────────────────────────────────────────────────

class NormalisedOpportunity(BaseModel):
    """Final normalised record ready to be persisted."""

    # Identity
    source_url: str
    source_name: str
    source_id: str
    url_hash: str                # SHA-256 of source_url for dedup

    # Core fields
    title: str
    type: OpportunityType
    status: str = "ACTIVE"

    # Content
    description_structured: str
    requirements: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)

    # Location
    province: str | None = None
    municipality: str | None = None

    # Compensation
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "AOA"

    # Organisation
    organization_name: str | None = None

    # Dates
    deadline: date | None = None
    published_at: datetime | None = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    # AI metadata
    ai_confidence_score: float
    requires_review: bool
    ai_extracted: bool = True


# ─── Scrape Run Result ───────────────────────────────────────────────────────

class ScrapeResult(BaseModel):
    """Summary of a scraping run for one source."""

    source_id: str
    source_name: str
    started_at: datetime
    finished_at: datetime | None = None
    success: bool = False
    pages_visited: int = 0
    items_found: int = 0
    items_new: int = 0
    items_skipped_dup: int = 0
    items_failed: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
