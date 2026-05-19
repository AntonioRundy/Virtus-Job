import json
import uuid
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


def _parse_json_list(v: str | list | None) -> list[str] | None:
    """DB stores JSON arrays as strings; parse them back to Python lists."""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _validate_absolute_url(url: str) -> str:
    """Reject relative URLs, placeholders and non-HTTP schemes."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"source_url must be an absolute HTTP/HTTPS URL, got: '{url[:80]}'"
        )
    if not parsed.netloc:
        raise ValueError(f"source_url has no domain: '{url[:80]}'")
    return url


class OpportunityBase(BaseModel):
    title: str
    type: str
    status: str = "UNVERIFIED"
    modality: str | None = None
    description_structured: str | None = None
    requirements: list[str] | None = None
    benefits: list[str] | None = None
    tags: list[str] | None = None
    province: str | None = None
    municipality: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "AOA"
    source_url: str
    source_name: str
    deadline: date | None = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        return _validate_absolute_url(v)


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    description_structured: str | None = None
    deadline: date | None = None


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    is_verified: bool

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    category: str

    model_config = {"from_attributes": True}


class OpportunityOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    type: str
    status: str
    modality: str | None
    description_structured: str | None
    requirements: list[str] | None = None
    benefits: list[str] | None = None
    tags: list[str] | None = None
    province: str | None
    municipality: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str
    source_url: str
    source_name: str
    source_logo_url: str | None
    source_url_ok: bool | None
    source_url_checked_at: datetime | None
    # Trust system
    trust_level: str
    trust_score: float
    # Application details
    contact_email: str | None
    application_url: str | None
    document_url: str | None
    application_type: str | None
    ai_confidence_score: float | None
    deadline: date | None
    published_at: datetime | None
    created_at: datetime
    view_count: int
    save_count: int
    organization: OrganizationSummary | None
    categories: list[CategoryOut]

    model_config = {"from_attributes": True}

    @field_validator("requirements", "benefits", "tags", mode="before")
    @classmethod
    def parse_json_array(cls, v: str | list | None) -> list[str] | None:
        return _parse_json_list(v)


class OpportunityListOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    type: str
    status: str
    modality: str | None
    province: str | None
    source_name: str
    source_logo_url: str | None
    source_url_ok: bool | None
    trust_level: str
    trust_score: float
    deadline: date | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str
    view_count: int
    save_count: int
    created_at: datetime
    organization: OrganizationSummary | None
    categories: list[CategoryOut]

    model_config = {"from_attributes": True}


class PaginatedOpportunities(BaseModel):
    items: list[OpportunityListOut]
    total: int
    page: int
    per_page: int
    pages: int


class SourceCheckResult(BaseModel):
    slug: str
    source_url: str
    source_url_ok: bool | None
    source_url_checked_at: datetime | None
    message: str
