"""
Data normalisation — bridges AI extraction output to DB-ready records.

Responsibilities:
- Compute URL hash for deduplication
- Build NormalisedOpportunity from RawPage + AIExtractionResult
- Clean and validate all fields
- Generate slug-ready title
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from loguru import logger

from scrapers.models import AIExtractionResult, NormalisedOpportunity, RawPage


def ensure_absolute_url(url: str, base_url: str = "") -> str:
    """
    Guarantee url is absolute HTTP/HTTPS.
    Raises ValueError for relative URLs or non-HTTP schemes so the pipeline
    rejects the record rather than persisting a broken link.
    """
    url = url.strip()
    if not url:
        raise ValueError("source_url is empty")
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return url
    if url.startswith("/") and base_url:
        # Relative path — prepend base domain
        base = urlparse(base_url)
        absolute = f"{base.scheme}://{base.netloc}{url}"
        logger.warning("Converted relative URL '{}' → '{}'", url[:60], absolute[:60])
        return absolute
    raise ValueError(
        f"source_url is not an absolute HTTP/HTTPS URL: '{url[:80]}'"
    )

ANGOLA_PROVINCES = {
    "luanda", "benguela", "huambo", "bié", "malanje", "kuanza sul",
    "uíge", "zaire", "cabinda", "cunene", "huíla", "kuando kubango",
    "kuanza norte", "lunda norte", "lunda sul", "moxico", "namibe", "bengo",
}


def url_hash(url: str) -> str:
    """SHA-256 of the canonical URL — primary dedup key."""
    canonical = url.strip().rstrip("/").lower()
    return hashlib.sha256(canonical.encode()).hexdigest()


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text if text else None


def infer_province_from_text(text: str) -> str | None:
    """Try to find an Angolan province mentioned in text."""
    lower = text.lower()
    for prov in ANGOLA_PROVINCES:
        if prov in lower:
            # Capitalize properly
            return " ".join(w.capitalize() for w in prov.split())
    return None


class Normalizer:
    """
    Converts (RawPage, AIExtractionResult) → NormalisedOpportunity.
    """

    def normalise(
        self, raw: RawPage, extracted: AIExtractionResult
    ) -> NormalisedOpportunity:
        title = self._clean_title(extracted.title or raw.title or "Sem título")
        description = self._build_description(extracted, raw)
        province = extracted.province or infer_province_from_text(raw.text or "")
        confidence = extracted.confidence

        # If AI didn't find a province, mark for review
        requires_review = extracted.requires_review or confidence < 0.6

        salary_min: float | None = None
        salary_max: float | None = None
        salary_currency = "AOA"
        if extracted.salary_range:
            salary_min = extracted.salary_range.min
            salary_max = extracted.salary_range.max
            salary_currency = extracted.salary_range.currency or "AOA"

        source_url = ensure_absolute_url(raw.url)

        record = NormalisedOpportunity(
            source_url=source_url,
            source_name=raw.source_name,
            source_id=raw.source_id,
            url_hash=url_hash(raw.url),
            title=title,
            type=extracted.type,
            status="UNVERIFIED" if requires_review else "ACTIVE",
            description_structured=description,
            requirements=extracted.requirements or [],
            benefits=extracted.benefits or [],
            categories=self._build_categories(extracted),
            province=province,
            municipality=clean_text(extracted.municipality),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            organization_name=clean_text(extracted.organization),
            deadline=extracted.deadline,
            published_at=raw.fetched_at.replace(tzinfo=timezone.utc),
            extracted_at=datetime.now(timezone.utc),
            ai_confidence_score=confidence,
            requires_review=requires_review,
            ai_extracted=True,
        )

        logger.debug(
            "Normalised: '{}' | status={} | province={}",
            title[:60], record.status, province,
        )
        return record

    def _clean_title(self, raw_title: str) -> str:
        # Remove common noise
        title = re.sub(r"\s+", " ", raw_title).strip()
        # Remove trailing source name patterns like " - MAPTESS"
        title = re.sub(r"\s*[-|–]\s*[A-Z].{2,30}$", "", title).strip()
        # Truncate
        return title[:490]

    def _build_description(self, extracted: AIExtractionResult, raw: RawPage) -> str:
        parts = []
        if extracted.description:
            parts.append(extracted.description)
        if extracted.organization and extracted.organization not in (extracted.description or ""):
            parts.append(f"Instituição: {extracted.organization}.")
        if not parts:
            parts.append(
                f"Oportunidade publicada por {raw.source_name}. "
                "Consulte a fonte original para mais informações."
            )
        return " ".join(parts)[:5000]

    def _build_categories(self, extracted: AIExtractionResult) -> list[str]:
        cats = list(extracted.categories)
        # Always add the type as a category if not already there
        type_label = {
            "VAGA": "Emprego",
            "CONCURSO": "Concurso Público",
            "BOLSA": "Bolsa de Estudos",
            "ESTAGIO": "Estágio",
            "FORMACAO": "Formação",
        }.get(extracted.type.value, "")
        if type_label and type_label not in cats:
            cats.insert(0, type_label)
        return cats[:6]
