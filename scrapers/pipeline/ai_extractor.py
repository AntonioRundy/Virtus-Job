"""
AI Extraction Pipeline — Claude API integration.

Design:
- Two-tier model strategy: Haiku for fast/cheap extraction, Sonnet as fallback
- Structured JSON output with Pydantic validation
- Confidence score per extraction
- Graceful fallback when AI fails (returns low-confidence result)
- Prompt caching for repeated system prompts (cost reduction)
"""
from __future__ import annotations

import json
import re
from datetime import date

import anthropic
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scrapers.config import settings
from scrapers.models import AIExtractionResult, OpportunityType, RawPage, SalaryRange

# ─── Prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é um extractor de dados especializado para a plataforma Virtus Job, um agregador angolano de oportunidades profissionais.

A sua tarefa: analisar texto de páginas web angolanas e extrair informação estruturada sobre oportunidades de emprego, concursos públicos, bolsas e estágios.

REGRAS OBRIGATÓRIAS:
1. Nunca invente informação que não esteja no texto
2. Extraia apenas o que está explicitamente mencionado
3. Datas devem estar no formato YYYY-MM-DD
4. Resumo deve ser em Português de Angola, máximo 5 frases
5. Seja conservador — se tiver dúvida, use null e reduza o confidence
6. categories deve ter 2-5 tags relevantes em Português

TIPOS VÁLIDOS (type):
- VAGA: emprego privado ou público com contrato
- CONCURSO: concurso público, concurso de acesso a cargo
- BOLSA: bolsa de estudos, financiamento académico
- ESTAGIO: estágio profissional ou académico
- FORMACAO: curso, formação, workshop, capacitação

PROVÍNCIAS ANGOLANAS VÁLIDAS:
Luanda, Benguela, Huambo, Bié, Malanje, Kuanza Sul, Uíge, Zaire, Cabinda, Cunene, Huíla, Kuando Kubango, Kuanza Norte, Lunda Norte, Lunda Sul, Moxico, Namibe, Bengo

Responda APENAS com JSON válido, sem texto adicional, sem markdown."""

EXTRACTION_TEMPLATE = """Analise o seguinte texto extraído de uma página web angolana e extraia a informação estruturada.

FONTE: {source_name}
URL: {url}

TEXTO:
---
{text}
---

Retorne um JSON com EXATAMENTE esta estrutura:
{{
  "title": "título exacto da oportunidade (string, obrigatório)",
  "type": "VAGA | CONCURSO | BOLSA | ESTAGIO | FORMACAO (obrigatório)",
  "description": "resumo em português, 2-5 frases (string, obrigatório)",
  "organization": "nome da instituição ou null",
  "province": "província angolana ou null",
  "municipality": "município ou null",
  "deadline": "YYYY-MM-DD ou null",
  "raw_deadline_text": "texto original do prazo ou null",
  "requirements": ["requisito 1", "requisito 2"] ou [],
  "benefits": ["benefício 1"] ou [],
  "salary_range": {{"min": número ou null, "max": número ou null, "currency": "AOA"}} ou null,
  "categories": ["categoria1", "categoria2"],
  "confidence": 0.0 a 1.0,
  "requires_review": true ou false
}}"""


# ─── Extractor ───────────────────────────────────────────────────────────────

class AIExtractor:
    """
    Wraps the Anthropic Claude API for structured extraction.

    Tier strategy:
    1. Try claude-haiku (fast, ~$0.00025/1K input tokens)
    2. If parse fails or confidence < threshold, retry with claude-sonnet
    3. If both fail, return a low-confidence fallback result
    """

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not set — AI extraction disabled")
            self._client = None
        else:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def extract(self, raw: RawPage) -> AIExtractionResult:
        """
        Extract structured data from a raw page.
        Never raises — returns low-confidence fallback on error.
        """
        if not self._client:
            return self._fallback_result(raw, reason="No API key configured")

        if not raw.text or len(raw.text.strip()) < settings.MIN_CONTENT_LENGTH:
            return self._fallback_result(raw, reason="Content too short")

        text = raw.text[: settings.MAX_CONTENT_LENGTH]

        # Try primary model first
        result = await self._try_extract(raw, text, model=settings.AI_MODEL)
        if result and result.confidence >= settings.AI_CONFIDENCE_THRESHOLD:
            return result

        # Low confidence → escalate to more capable model
        logger.info(
            "Low confidence ({:.2f}) for {} — escalating to {}",
            result.confidence if result else 0,
            raw.url,
            settings.AI_FALLBACK_MODEL,
        )
        result = await self._try_extract(raw, text, model=settings.AI_FALLBACK_MODEL)
        if result:
            return result

        return self._fallback_result(raw, reason="Extraction failed after escalation")

    async def _try_extract(
        self,
        raw: RawPage,
        text: str,
        model: str,
    ) -> AIExtractionResult | None:
        prompt = EXTRACTION_TEMPLATE.format(
            source_name=raw.source_name,
            url=raw.url,
            text=text,
        )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(2),
                wait=wait_exponential(min=3, max=15),
                retry=retry_if_exception_type((anthropic.APIConnectionError, anthropic.RateLimitError)),
                reraise=True,
            ):
                with attempt:
                    message = await self._client.messages.create(  # type: ignore[union-attr]
                        model=model,
                        max_tokens=settings.AI_MAX_TOKENS,
                        system=[
                            {
                                "type": "text",
                                "text": SYSTEM_PROMPT,
                                "cache_control": {"type": "ephemeral"},  # prompt caching
                            }
                        ],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=settings.AI_TEMPERATURE,
                    )

            raw_json = message.content[0].text.strip()
            return self._parse_response(raw_json, raw.url)

        except anthropic.APIStatusError as e:
            logger.error("Claude API error for {}: {} {}", raw.url, e.status_code, e.message)
            return None
        except Exception as e:
            logger.error("Unexpected AI error for {}: {}", raw.url, e)
            return None

    def _parse_response(self, raw_json: str, url: str) -> AIExtractionResult | None:
        """Parse and validate the AI JSON response."""
        # Strip markdown code blocks if model wraps response
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json, flags=re.MULTILINE).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON from AI for {}: {}", url, e)
            return None

        # Parse salary_range sub-object
        if sr := data.get("salary_range"):
            data["salary_range"] = SalaryRange(**sr) if isinstance(sr, dict) else None

        # Parse deadline string → date
        if dl := data.get("deadline"):
            try:
                data["deadline"] = date.fromisoformat(dl)
            except (ValueError, TypeError):
                logger.debug("Could not parse deadline '{}' for {}", dl, url)
                data["deadline"] = None

        try:
            result = AIExtractionResult(**data)
            logger.info(
                "AI extracted: '{}' | type={} | confidence={:.2f} | review={}",
                result.title[:60],
                result.type,
                result.confidence,
                result.requires_review,
            )
            return result
        except Exception as e:
            logger.warning("Pydantic validation failed for {}: {}", url, e)
            return None

    @staticmethod
    def _fallback_result(raw: RawPage, reason: str) -> AIExtractionResult:
        """Minimal fallback when AI extraction is impossible."""
        logger.warning("Using fallback extraction for {}: {}", raw.url, reason)
        return AIExtractionResult(
            title=raw.title or "Oportunidade sem título",
            type=OpportunityType.VAGA,
            description=f"Oportunidade publicada por {raw.source_name}. Consultar fonte original para detalhes.",
            confidence=0.1,
            requires_review=True,
        )
