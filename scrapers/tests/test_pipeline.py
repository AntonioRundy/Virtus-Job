"""
Unit tests for the scraping pipeline.
Tests are isolated — no network calls, no AI API, no database.
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.models import (
    AIExtractionResult,
    NormalisedOpportunity,
    OpportunityType,
    RawPage,
    SalaryRange,
)
from scrapers.pipeline.normalizer import Normalizer, url_hash
from scrapers.pipeline.ai_extractor import AIExtractor


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_HTML = """
<html>
<head><title>Concurso Público — MAPTESS</title></head>
<body>
<nav>Menu de navegação</nav>
<main>
  <article>
    <h1>Concurso Público para Recrutamento de Técnicos Superiores</h1>
    <div class="entry-content">
      <p>O Ministério da Administração Pública, Trabalho e Segurança Social (MAPTESS)
      abre concurso público para recrutamento de 50 técnicos superiores nas áreas de
      Recursos Humanos, Gestão e Direito.</p>
      <p><strong>Prazo de candidatura:</strong> 30 de Junho de 2025</p>
      <p><strong>Requisitos:</strong></p>
      <ul>
        <li>Licenciatura em área relevante</li>
        <li>Experiência mínima de 3 anos</li>
        <li>Nacionalidade angolana</li>
      </ul>
      <p><strong>Local:</strong> Luanda</p>
    </div>
  </article>
</main>
<footer>Rodapé</footer>
</body>
</html>
"""

SAMPLE_AI_RESPONSE = json.dumps({
    "title": "Concurso Público para Recrutamento de Técnicos Superiores",
    "type": "CONCURSO",
    "description": "O MAPTESS abre concurso público para 50 técnicos superiores em RH, Gestão e Direito.",
    "organization": "MAPTESS",
    "province": "Luanda",
    "municipality": None,
    "deadline": "2025-06-30",
    "raw_deadline_text": "30 de Junho de 2025",
    "requirements": [
        "Licenciatura em área relevante",
        "Experiência mínima de 3 anos",
        "Nacionalidade angolana",
    ],
    "benefits": [],
    "salary_range": None,
    "categories": ["Concurso Público", "Recursos Humanos", "Gestão", "Direito"],
    "confidence": 0.92,
    "requires_review": False,
})


# ─── Tests: URL Hash ─────────────────────────────────────────────────────────

def test_url_hash_is_deterministic():
    url = "https://maptess.gov.ao/concurso-123"
    assert url_hash(url) == url_hash(url)


def test_url_hash_normalises_trailing_slash():
    url1 = "https://maptess.gov.ao/concurso-123/"
    url2 = "https://maptess.gov.ao/concurso-123"
    assert url_hash(url1) == url_hash(url2)


def test_url_hash_different_urls_differ():
    assert url_hash("https://a.ao/1") != url_hash("https://a.ao/2")


# ─── Tests: Normalizer ───────────────────────────────────────────────────────

def _make_raw(url: str = "https://maptess.gov.ao/concurso-1") -> RawPage:
    return RawPage(
        url=url,
        source_name="MAPTESS",
        source_id="maptess",
        text="Concurso público para recrutamento de técnicos. Prazo: 30/06/2025.",
        title="Concurso Público",
    )


def _make_extracted(**kwargs) -> AIExtractionResult:
    defaults = dict(
        title="Concurso Público MAPTESS",
        type=OpportunityType.CONCURSO,
        description="O MAPTESS abre concurso público.",
        organization="MAPTESS",
        province="Luanda",
        categories=["Concurso Público"],
        confidence=0.9,
        requires_review=False,
        deadline=date(2025, 6, 30),
    )
    defaults.update(kwargs)
    return AIExtractionResult(**defaults)


def test_normalizer_basic():
    n = Normalizer()
    raw = _make_raw()
    extracted = _make_extracted()
    result = n.normalise(raw, extracted)

    assert isinstance(result, NormalisedOpportunity)
    assert result.title == "Concurso Público MAPTESS"
    assert result.type == OpportunityType.CONCURSO
    assert result.province == "Luanda"
    assert result.status == "ACTIVE"
    assert result.ai_extracted is True
    assert result.source_url == raw.url


def test_normalizer_low_confidence_marks_unverified():
    n = Normalizer()
    raw = _make_raw()
    extracted = _make_extracted(confidence=0.4, requires_review=False)
    result = n.normalise(raw, extracted)
    assert result.status == "UNVERIFIED"
    assert result.requires_review is True


def test_normalizer_salary_range():
    n = Normalizer()
    raw = _make_raw()
    extracted = _make_extracted(
        salary_range=SalaryRange(min=500000, max=1000000, currency="AOA")
    )
    result = n.normalise(raw, extracted)
    assert result.salary_min == 500000
    assert result.salary_max == 1000000
    assert result.salary_currency == "AOA"


def test_normalizer_type_added_to_categories():
    n = Normalizer()
    raw = _make_raw()
    extracted = _make_extracted(
        type=OpportunityType.BOLSA,
        categories=["Internacional", "Portugal"],
    )
    result = n.normalise(raw, extracted)
    # "Bolsa de Estudos" should be prepended
    assert "Bolsa de Estudos" in result.categories
    assert result.categories[0] == "Bolsa de Estudos"


def test_normalizer_categories_capped_at_6():
    n = Normalizer()
    raw = _make_raw()
    extracted = _make_extracted(categories=["a", "b", "c", "d", "e", "f", "g"])
    result = n.normalise(raw, extracted)
    assert len(result.categories) <= 6


# ─── Tests: Province Validation ──────────────────────────────────────────────

def test_province_valid():
    ex = AIExtractionResult(
        title="Test",
        type=OpportunityType.VAGA,
        description="Test",
        province="luanda",
        confidence=0.8,
    )
    assert ex.province == "Luanda"


def test_province_invalid_kept_as_is():
    ex = AIExtractionResult(
        title="Test",
        type=OpportunityType.VAGA,
        description="Test",
        province="Lisboa",
        confidence=0.8,
    )
    assert ex.province == "Lisboa"  # Kept but not normalised


def test_province_empty_becomes_none():
    ex = AIExtractionResult(
        title="Test",
        type=OpportunityType.VAGA,
        description="Test",
        province="",
        confidence=0.8,
    )
    assert ex.province is None


# ─── Tests: AI Extractor (mocked) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_extractor_no_api_key(monkeypatch):
    """Without API key, returns fallback result."""
    monkeypatch.setattr("scrapers.pipeline.ai_extractor.settings.ANTHROPIC_API_KEY", "")

    ai = AIExtractor()
    raw = _make_raw()
    raw.text = "Some content"
    result = await ai.extract(raw)

    assert result.confidence == 0.1
    assert result.requires_review is True


@pytest.mark.asyncio
async def test_ai_extractor_content_too_short():
    monkeypatch_settings = MagicMock()
    monkeypatch_settings.ANTHROPIC_API_KEY = "test-key"
    monkeypatch_settings.MIN_CONTENT_LENGTH = 100

    ai = AIExtractor()
    ai._client = MagicMock()  # Prevent real API call

    raw = _make_raw()
    raw.text = "Short"  # Too short

    with patch.object(ai, "_client", None):
        result = await ai.extract(raw)

    assert result.requires_review is True


@pytest.mark.asyncio
async def test_ai_extractor_parse_valid_json():
    ai = AIExtractor()
    raw = _make_raw()
    result = ai._parse_response(SAMPLE_AI_RESPONSE, raw.url)

    assert result is not None
    assert result.title == "Concurso Público para Recrutamento de Técnicos Superiores"
    assert result.type == OpportunityType.CONCURSO
    assert result.province == "Luanda"
    assert result.confidence == 0.92
    assert result.deadline == date(2025, 6, 30)
    assert len(result.requirements) == 3


@pytest.mark.asyncio
async def test_ai_extractor_handles_markdown_wrapped_json():
    ai = AIExtractor()
    raw = _make_raw()
    wrapped = f"```json\n{SAMPLE_AI_RESPONSE}\n```"
    result = ai._parse_response(wrapped, raw.url)
    assert result is not None
    assert result.title is not None


@pytest.mark.asyncio
async def test_ai_extractor_handles_invalid_json():
    ai = AIExtractor()
    raw = _make_raw()
    result = ai._parse_response("not valid json {{{", raw.url)
    assert result is None


# ─── Tests: MAPTESS Spider ───────────────────────────────────────────────────

def test_maptess_spider_config():
    from scrapers.sources.maptess import MaptessSpider
    spider = MaptessSpider()
    assert spider.source_id == "maptess"
    assert spider.source_name == "MAPTESS"
    assert spider.config.is_active is True
    assert spider.config.requires_js is False


def test_maptess_extract_links_from_html():
    from scrapers.sources.maptess import MaptessSpider
    spider = MaptessSpider()
    html = """
    <html><body>
    <a href="/concurso-publico-2025">Concurso Público 2025</a>
    <a href="/vaga-engenheiro">Vaga de Engenheiro</a>
    <a href="/sobre-nos">Sobre Nós</a>
    <a href="https://google.com/external">External</a>
    </body></html>
    """
    links = spider._extract_links(html, "https://maptess.gov.ao")
    urls = [l for l in links]
    # Should find opportunity links but not "sobre-nos" or external
    assert any("concurso" in u for u in urls)
    assert any("vaga" in u or "engenheiro" in u for u in urls)
    assert not any("google.com" in u for u in urls)


def test_maptess_clean_text():
    from scrapers.sources.maptess import MaptessSpider
    raw = "\n\n\n  Hello   \n\n   World  \n\n\n\n\n"
    cleaned = MaptessSpider._clean_text(raw)
    assert "Hello" in cleaned
    assert "World" in cleaned
    # No more than 2 consecutive newlines
    assert "\n\n\n" not in cleaned


@pytest.mark.asyncio
async def test_maptess_parse_page():
    from scrapers.sources.maptess import MaptessSpider
    spider = MaptessSpider()
    raw = RawPage(
        url="https://maptess.gov.ao/test",
        source_name="MAPTESS",
        source_id="maptess",
        html=SAMPLE_HTML,
        title="Concurso Público — MAPTESS",
    )
    parsed = await spider.parse_page(raw)
    assert parsed.text is not None
    assert "Técnicos Superiores" in parsed.text
    assert "Luanda" in parsed.text
    # Navigation and footer should be removed
    assert "Menu de navegação" not in parsed.text
    assert "Rodapé" not in parsed.text
