"""
Hybrid extraction strategy classifier.

Decides automatically between:
  HTML   — standard web pages, parseable HTML
  VISION — PressReader, PDF viewers, image-based newspapers
  OCR    — low-quality scans, non-machine-readable images

The strategy is declared per source via SourceConfig.strategy.
"""
from __future__ import annotations

from enum import Enum


class ExtractionStrategy(str, Enum):
    HTML             = "HTML"              # standard HTML scraping
    VISION           = "VISION"            # Claude Vision API
    PRESSREADER_VISION = "PRESSREADER_VISION"  # PressReader newspaper viewer
    OCR              = "OCR"               # Tesseract local OCR


# Keywords that indicate a page is opportunity-related
OPPORTUNITY_TRIGGER_KEYWORDS: frozenset[str] = frozenset({
    "recrutamento", "recrut", "vaga", "vagas", "concurso", "concursos",
    "bolsa", "bolsas", "estágio", "estagio", "candidatura", "candidaturas",
    "emprego", "empregos", "licitação", "licitacao", "edital", "editais",
    "admissão", "admissao", "selecção", "selecao", "processo seletivo",
    "abertura de concurso", "contratação", "inscricão", "inscricao",
    "oportunidade", "oportunidades",
})

OPPORTUNITY_SECTION_PATTERNS: frozenset[str] = frozenset({
    "concursos-publicos", "emprego", "bolsas", "licitacoes",
    "recrutamento", "editais", "oportunidades",
})
