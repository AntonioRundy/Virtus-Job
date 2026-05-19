"""
Vision Extraction Pipeline — Claude Vision + OCR fallback.

Used for PressReader newspaper pages and other image-based content.
Sends screenshots to Claude Vision and extracts structured opportunity data.

Design:
  1. Fast-scan pass:  small screenshot → detect if page has opportunity content
  2. Extract pass:    full-quality screenshot → extract structured JSON
  3. OCR fallback:   if Vision API unavailable, try pytesseract
"""
from __future__ import annotations

import base64
import json
import re
from datetime import date
from typing import Any

import anthropic
from loguru import logger

from scrapers.config import settings

# ─── Prompts ─────────────────────────────────────────────────────────────────

SCAN_PROMPT = """Esta é uma página do Jornal de Angola (jornal oficial de Angola).

Analise a imagem e responda APENAS com JSON:
{
  "has_opportunities": true ou false,
  "confidence": 0.0-1.0,
  "keywords_found": ["RECRUTAMENTO", "CONCURSO", ...],
  "page_description": "breve descrição do conteúdo (1 frase)"
}

Palavras-chave a detectar (em qualquer capitalização):
RECRUTAMENTO, CONCURSO, CONCURSO PÚBLICO, VAGAS, VAGA, BOLSA, BOLSAS,
CANDIDATURA, ESTÁGIO, ESTAGIO, EDITAL, LICITAÇÃO, ADMISSÃO, EMPREGO.

Se a página não tiver qualquer oportunidade profissional, retorne has_opportunities: false."""

EXTRACT_PROMPT = """Esta é uma página do Jornal de Angola contendo anúncios de oportunidades profissionais.

Extraia TODAS as oportunidades visíveis na imagem. Para cada uma, retorne JSON estruturado.

REGRAS:
1. Extraia apenas o que está VISÍVEL na imagem — não invente dados
2. Preserve o português angolano conforme publicado
3. Datas em formato YYYY-MM-DD
4. confidence: 0.9 se todos os campos principais estão legíveis, menos se parcial

Retorne APENAS JSON válido com esta estrutura:
{
  "page_number": <número da página>,
  "opportunities": [
    {
      "title": "título exacto do anúncio",
      "type": "VAGA | CONCURSO | BOLSA | ESTAGIO | FORMACAO",
      "organization": "nome da entidade/empresa ou null",
      "description": "resumo em 2-4 frases do que foi publicado",
      "requirements": ["requisito 1", "requisito 2"],
      "contact_email": "email@example.ao ou null",
      "contact_phone": "número ou null",
      "deadline": "YYYY-MM-DD ou null",
      "deadline_raw": "texto original do prazo ou null",
      "location": "cidade/província ou null",
      "salary_info": "informação salarial ou null",
      "reference_number": "número de referência ou null",
      "application_method": "descrição de como candidatar ou null",
      "confidence": 0.0-1.0,
      "requires_review": true ou false
    }
  ],
  "extraction_notes": "observações sobre a extracção (legibilidade, cortes, etc.)"
}

Se não encontrar oportunidades claras, retorne: {"page_number": <n>, "opportunities": [], "extraction_notes": "..."}"""


# ─── Vision Extractor ─────────────────────────────────────────────────────────

class VisionExtractor:
    """
    Extracts structured opportunity data from newspaper page screenshots.

    Primary: Claude Vision (claude-sonnet-4-6)
    Fallback: pytesseract OCR → text → existing AI text extractor
    """

    VISION_MODEL = "claude-sonnet-4-6"

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not set — Vision extraction disabled")
            self._client = None
        else:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def scan_page(self, screenshot: bytes, page_num: int) -> dict[str, Any]:
        """
        Fast scan: detect if page contains opportunity content.
        Returns dict with has_opportunities, confidence, keywords_found.
        """
        if not self._client:
            return {"has_opportunities": False, "confidence": 0, "keywords_found": [], "error": "No API key"}

        try:
            img_b64 = base64.standard_b64encode(screenshot).decode("utf-8")
            response = await self._client.messages.create(
                model=self.VISION_MODEL,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64},
                        },
                        {"type": "text", "text": SCAN_PROMPT},
                    ]
                }]
            )
            raw = response.content[0].text.strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            result = json.loads(cleaned)
            result["page_number"] = page_num
            logger.info(
                "Vision scan p{}: has_opp={} confidence={:.2f} keywords={}",
                page_num,
                result.get("has_opportunities"),
                result.get("confidence", 0),
                result.get("keywords_found", []),
            )
            return result
        except Exception as exc:
            logger.warning("Vision scan failed for page {}: {}", page_num, exc)
            return {"has_opportunities": False, "confidence": 0, "keywords_found": [], "error": str(exc)}

    async def extract_opportunities(
        self,
        screenshot: bytes,
        page_num: int,
        edition_date: str,
        source_url: str,
    ) -> dict[str, Any]:
        """
        Full extraction: parse all opportunities from a page screenshot.
        Returns structured JSON with all opportunities found.
        """
        if not self._client:
            return {"page_number": page_num, "opportunities": [], "error": "No API key"}

        try:
            img_b64 = base64.standard_b64encode(screenshot).decode("utf-8")
            prompt = EXTRACT_PROMPT.replace("<número da página>", str(page_num))

            response = await self._client.messages.create(
                model=self.VISION_MODEL,
                max_tokens=2000,
                system=(
                    f"Estás a analisar a edição do Jornal de Angola de {edition_date}. "
                    "Extrai oportunidades profissionais com precisão máxima. "
                    "Responde APENAS com JSON válido."
                ),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64},
                        },
                        {"type": "text", "text": prompt},
                    ]
                }]
            )
            raw = response.content[0].text.strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            result = json.loads(cleaned)
            result["page_number"] = page_num
            result["source_url"] = source_url
            result["edition_date"] = edition_date

            n = len(result.get("opportunities", []))
            logger.success("Vision extraction p{}: {} opportunities found", page_num, n)
            for opp in result.get("opportunities", []):
                logger.info(
                    "  - [{}] {} | confidence={:.2f}",
                    opp.get("type", "?"),
                    opp.get("title", "?")[:60],
                    opp.get("confidence", 0),
                )
            return result

        except Exception as exc:
            logger.error("Vision extraction failed for page {}: {}", page_num, exc)
            return {
                "page_number": page_num,
                "opportunities": [],
                "error": str(exc),
                "source_url": source_url,
            }

    async def ocr_fallback(self, screenshot: bytes, page_num: int) -> str | None:
        """
        OCR fallback using pytesseract.
        Returns extracted text or None if pytesseract is not available.
        """
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(screenshot))
            text = pytesseract.image_to_string(img, lang="por")
            logger.info("OCR fallback p{}: {} chars", page_num, len(text))
            return text
        except ImportError:
            logger.debug("pytesseract not available — OCR fallback skipped")
            return None
        except Exception as exc:
            logger.warning("OCR fallback failed p{}: {}", page_num, exc)
            return None
