"""
Visual Segmentation Engine — Jornal de Angola

Two-pass pipeline:
  Pass 1  (full page   → Claude Vision) → bounding boxes of ALL announcements
  Pass 2  (each crop   → Claude Vision) → structured extraction per announcement

The key insight: Claude Vision receives INDIVIDUAL CROPPED ANNOUNCEMENTS,
not chaotic full pages. This dramatically improves extraction accuracy.

Fallback without API key: pytesseract OCR + keyword-region heuristics.
"""
from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from scrapers.config import settings

# ─── Keywords that indicate an opportunity block ─────────────────────────────

OPPORTUNITY_KEYWORDS = frozenset({
    "recrutamento", "recruta", "recrutar", "vaga", "vagas", "emprego",
    "edital", "editais", "concurso", "bolsa", "estágio", "estagio",
    "candidatura", "candidaturas", "curriculum", "curriculo", "cv",
    "pretende recrutar", "e-mail", "email", "contrate", "admissão",
    "admissao", "selecção", "selecao", "processo seletivo",
    "anúncio", "anuncio", "classificado", "licitação", "licitacao",
    "inscricão", "inscricao", "vagas disponíveis", "oferta de emprego",
})

# ─── Data models ─────────────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    """Bounding box as percentage of image dimensions (0-100)."""
    x1: float
    y1: float
    x2: float
    y2: float

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        return (
            max(0, int(self.x1 / 100 * width)),
            max(0, int(self.y1 / 100 * height)),
            min(width,  int(self.x2 / 100 * width)),
            min(height, int(self.y2 / 100 * height)),
        )

    @property
    def area_pct(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1) / 100


@dataclass
class PageSegment:
    """One detected announcement region."""
    image_bytes: bytes            # cropped JPEG
    opp_type: str                 # VAGA | EDITAL | CONCURSO | BOLSA | CLASSIFICADO
    bbox_pct: BoundingBox
    company_hint: str | None      # company name detected in pass 1
    keywords: list[str]           # keywords that triggered detection
    confidence: float             # 0-1 from pass 1
    page_num: int = 0
    segment_idx: int = 0
    extracted: dict[str, Any] = field(default_factory=dict)  # filled by pass 2


# ─── Prompts ─────────────────────────────────────────────────────────────────

SEGMENTATION_PROMPT = """Analyze this Jornal de Angola (Angolan newspaper) page carefully.

Find ALL visible advertisement blocks that contain:
- Job announcements / vagas de emprego
- Public procurement notices / editais
- Scholarships / bolsas
- Internships / estágios
- Corporate recruitment ads
- Classified ads / classificados
- Any block with: RECRUTAMENTO, VAGA, EDITAL, CV, candidatura, e-mail, bolsa, estágio

For EACH block found, return its approximate bounding box as percentages of this image.
Be VERY thorough — find EVERY announcement even if small or partially visible.

IMPORTANT: Return ONLY valid JSON array, nothing else:
[
  {
    "type": "VAGA|EDITAL|CONCURSO|BOLSA|CLASSIFICADO|RECRUTAMENTO|ANUNCIO",
    "bbox_pct": [x1, y1, x2, y2],
    "company_hint": "company name or null",
    "keywords": ["keyword1", "keyword2"],
    "confidence": 0.0-1.0
  }
]

Where x1,y1 = top-left corner, x2,y2 = bottom-right, all in % (0-100).
If NO announcements found, return: []"""

EXTRACTION_PROMPT = """This is a cropped advertisement from Jornal de Angola newspaper.

Extract ALL information visible in this announcement. Be precise and complete.

Return ONLY valid JSON:
{
  "title": "exact title of the announcement",
  "type": "VAGA|CONCURSO|BOLSA|ESTAGIO|FORMACAO",
  "organization": "company/institution name",
  "description": "2-4 sentence summary in Portuguese",
  "requirements": ["requirement 1", "requirement 2"],
  "contact_email": "email@example.ao or null",
  "contact_phone": "number or null",
  "deadline": "YYYY-MM-DD or null",
  "deadline_raw": "original deadline text or null",
  "location": "city/province or null",
  "salary_info": "salary info or null",
  "num_vacancies": number_or_null,
  "reference_number": "ref number or null",
  "application_method": "how to apply or null",
  "categories": ["category1", "category2"],
  "confidence": 0.0-1.0,
  "requires_review": true_or_false
}

If the image does not contain an opportunity announcement, return: {"type": "NOT_OPPORTUNITY", "confidence": 0.1}"""


# ─── Main Segmenter ───────────────────────────────────────────────────────────

class VisualSegmenter:
    """
    Two-pass visual segmentation for Jornal de Angola pages.

    Pass 1: Full page → Claude Vision → list of bounding boxes
    Pass 2: Each crop → Claude Vision → structured extraction
    """

    MIN_SEGMENT_AREA_PCT = 0.5   # ignore tiny regions < 0.5% of page
    MAX_SEGMENT_AREA_PCT = 40.0  # ignore suspiciously large "ads" > 40%
    JPEG_QUALITY = 88

    def __init__(self) -> None:
        self._has_vision = bool(settings.ANTHROPIC_API_KEY)
        if not self._has_vision:
            logger.warning("ANTHROPIC_API_KEY not set — Vision segmentation disabled. OCR fallback will be used.")

    # ─── Public API ──────────────────────────────────────────────────────────

    async def segment_page(
        self,
        screenshot: bytes,
        page_num: int = 0,
    ) -> list[PageSegment]:
        """
        Detect all announcement blocks in a screenshot.
        Returns list of PageSegment with cropped image bytes.
        """
        if self._has_vision:
            segments = await self._segment_with_claude(screenshot, page_num)
        else:
            segments = await self._segment_with_ocr(screenshot, page_num)

        # Filter by area constraints
        segments = [
            s for s in segments
            if self.MIN_SEGMENT_AREA_PCT <= s.bbox_pct.area_pct <= self.MAX_SEGMENT_AREA_PCT
        ]

        logger.info("Segmented page {}: {} blocks detected", page_num, len(segments))
        return segments

    async def extract_segment(self, segment: PageSegment) -> dict[str, Any]:
        """
        Pass 2: extract structured data from a single cropped segment.
        Returns the extracted dict (also stored in segment.extracted).
        """
        if not self._has_vision:
            return {"error": "No API key", "confidence": 0.0}

        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        try:
            img_b64 = base64.standard_b64encode(segment.image_bytes).decode("utf-8")
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }],
            )
            raw = response.content[0].text.strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            result = json.loads(cleaned)
            segment.extracted = result
            logger.info(
                "  Extracted [{}] {} (conf={:.2f})",
                result.get("type", "?"),
                str(result.get("organization") or result.get("title", "?"))[:50],
                result.get("confidence", 0),
            )
            return result
        except Exception as exc:
            logger.error("Extraction failed for segment {}: {}", segment.segment_idx, exc)
            return {"error": str(exc), "confidence": 0.0}

    # ─── Pass 1: Segmentation strategies ─────────────────────────────────────

    async def _segment_with_claude(
        self, screenshot: bytes, page_num: int
    ) -> list[PageSegment]:
        """Pass 1 via Claude Vision: detect bounding boxes of all announcements."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        raw = ""

        try:
            img_b64 = base64.standard_b64encode(screenshot).decode("utf-8")
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=(
                    "You are a JSON-only API. You MUST respond with ONLY valid JSON. "
                    "No explanation, no prose, no markdown. Only JSON."
                ),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": SEGMENTATION_PROMPT},
                    ],
                }],
            )
            raw = response.content[0].text.strip()

            blocks = self._extract_json_array(raw)
            if blocks is None:
                logger.warning("Pass 1 could not extract JSON array | raw={}", raw[:300])
                return []

            if not isinstance(blocks, list):
                logger.warning("Pass 1 returned non-list: {}", type(blocks))
                return []

            if blocks:
                logger.info("Pass 1: Claude detected {} blocks on page {}", len(blocks), page_num)
            else:
                logger.warning("Pass 1: Claude returned [] (no blocks) | raw_start={}", raw[:150])
            return self._blocks_to_segments(blocks, screenshot, page_num)

        except Exception as exc:
            logger.error("Pass 1 Claude error: {} | raw={}", exc, raw[:200])
            return []

    @staticmethod
    def _extract_json_array(text: str) -> list | None:
        """
        Robustly extract a JSON array from text that may contain prose.
        Tries multiple strategies before giving up.
        """
        # Strategy 1: direct parse
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: find first [...] block in the text
        match = re.search(r"\[[\s\S]*?\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Strategy 3: greedy — find the longest [...] block
        match = re.search(r"\[[\s\S]*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Strategy 4: if response indicates "no announcements found"
        no_ann_phrases = [
            "no announcement", "no job", "no opportunity", "no ads",
            "sem anuncio", "sem vaga", "nenhum", "nada encontrado",
            "not find", "cannot find", "don't see", "do not see",
            "no blocks", "nothing found",
        ]
        if any(p in text.lower() for p in no_ann_phrases):
            return []

        return None

    async def _segment_with_ocr(
        self, screenshot: bytes, page_num: int
    ) -> list[PageSegment]:
        """
        Fallback: pytesseract keyword detection + region heuristics.
        Splits page into a grid and checks each cell for opportunity keywords.
        """
        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            logger.warning("pytesseract not available — returning full-page segment")
            return self._full_page_segment(screenshot, page_num)

        try:
            img = Image.open(io.BytesIO(screenshot))
            w, h = img.size
            ocr_data = pytesseract.image_to_data(
                img, lang="por", output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            logger.warning("OCR failed: {} — returning full-page segment", exc)
            return self._full_page_segment(screenshot, page_num)

        # Find bounding boxes of keyword-rich regions
        keyword_boxes: list[tuple[int, int, int, int]] = []
        n = len(ocr_data["text"])
        for i in range(n):
            word = str(ocr_data["text"][i]).lower().strip()
            if any(kw in word for kw in OPPORTUNITY_KEYWORDS) and int(ocr_data["conf"][i]) > 30:
                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                bw = ocr_data["width"][i]
                bh = ocr_data["height"][i]
                keyword_boxes.append((x, y, x + bw, y + bh))

        if not keyword_boxes:
            logger.info("OCR: no keywords found on page {} — returning grid segments", page_num)
            return self._grid_segments(screenshot, page_num, w, h)

        # Merge nearby keyword boxes into announcement regions
        regions = self._merge_keyword_regions(keyword_boxes, w, h)
        return self._regions_to_segments(regions, screenshot, page_num, w, h)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _blocks_to_segments(
        self,
        blocks: list[dict],
        screenshot: bytes,
        page_num: int,
    ) -> list[PageSegment]:
        """Convert Claude's bounding box list to PageSegment list with crops."""
        from PIL import Image

        img = Image.open(io.BytesIO(screenshot))
        w, h = img.size
        segments = []

        for idx, block in enumerate(blocks):
            try:
                bbox_raw = block.get("bbox_pct", [0, 0, 100, 100])
                if len(bbox_raw) != 4:
                    continue
                bbox = BoundingBox(*[float(v) for v in bbox_raw])
                x1, y1, x2, y2 = bbox.to_pixels(w, h)
                if x2 - x1 < 50 or y2 - y1 < 30:
                    continue

                # Crop with small padding
                pad = 8
                crop = img.crop((
                    max(0, x1 - pad),
                    max(0, y1 - pad),
                    min(w, x2 + pad),
                    min(h, y2 + pad),
                ))
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=self.JPEG_QUALITY)
                crop_bytes = buf.getvalue()

                segments.append(PageSegment(
                    image_bytes=crop_bytes,
                    opp_type=block.get("type", "ANUNCIO"),
                    bbox_pct=bbox,
                    company_hint=block.get("company_hint"),
                    keywords=block.get("keywords", []),
                    confidence=float(block.get("confidence", 0.5)),
                    page_num=page_num,
                    segment_idx=idx,
                ))
            except Exception as exc:
                logger.warning("Failed to crop block {}: {}", idx, exc)

        return segments

    def _merge_keyword_regions(
        self,
        boxes: list[tuple[int, int, int, int]],
        img_w: int,
        img_h: int,
        expand_px: int = 100,
    ) -> list[tuple[int, int, int, int]]:
        """Expand keyword bboxes and merge overlapping regions."""
        expanded = [(
            max(0, x1 - expand_px),
            max(0, y1 - expand_px * 2),  # more vertical expansion
            min(img_w, x2 + expand_px),
            min(img_h, y2 + expand_px * 3),
        ) for x1, y1, x2, y2 in boxes]

        # Simple merge: union overlapping rects
        merged = []
        for box in expanded:
            found = False
            for i, m in enumerate(merged):
                if not (box[2] < m[0] or box[0] > m[2] or box[3] < m[1] or box[1] > m[3]):
                    merged[i] = (
                        min(box[0], m[0]), min(box[1], m[1]),
                        max(box[2], m[2]), max(box[3], m[3]),
                    )
                    found = True
                    break
            if not found:
                merged.append(box)
        return merged

    def _regions_to_segments(
        self,
        regions: list[tuple[int, int, int, int]],
        screenshot: bytes,
        page_num: int,
        img_w: int,
        img_h: int,
    ) -> list[PageSegment]:
        from PIL import Image
        img = Image.open(io.BytesIO(screenshot))
        segments = []
        for idx, (x1, y1, x2, y2) in enumerate(regions):
            crop = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=self.JPEG_QUALITY)
            bbox = BoundingBox(
                x1 / img_w * 100, y1 / img_h * 100,
                x2 / img_w * 100, y2 / img_h * 100,
            )
            segments.append(PageSegment(
                image_bytes=buf.getvalue(),
                opp_type="ANUNCIO",
                bbox_pct=bbox,
                company_hint=None,
                keywords=[],
                confidence=0.5,
                page_num=page_num,
                segment_idx=idx,
            ))
        return segments

    def _grid_segments(
        self,
        screenshot: bytes,
        page_num: int,
        img_w: int,
        img_h: int,
        cols: int = 2,
        rows: int = 3,
    ) -> list[PageSegment]:
        """Last resort: divide page into grid cells."""
        from PIL import Image
        img = Image.open(io.BytesIO(screenshot))
        segments = []
        cw, rh = img_w // cols, img_h // rows
        for r in range(rows):
            for c in range(cols):
                x1, y1 = c * cw, r * rh
                x2, y2 = min(img_w, x1 + cw), min(img_h, y1 + rh)
                crop = img.crop((x1, y1, x2, y2))
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=self.JPEG_QUALITY)
                bbox = BoundingBox(
                    x1 / img_w * 100, y1 / img_h * 100,
                    x2 / img_w * 100, y2 / img_h * 100,
                )
                segments.append(PageSegment(
                    image_bytes=buf.getvalue(),
                    opp_type="ANUNCIO",
                    bbox_pct=bbox,
                    company_hint=None,
                    keywords=[],
                    confidence=0.3,
                    page_num=page_num,
                    segment_idx=r * cols + c,
                ))
        return segments

    def _full_page_segment(
        self, screenshot: bytes, page_num: int
    ) -> list[PageSegment]:
        """Return the whole screenshot as a single segment."""
        return [PageSegment(
            image_bytes=screenshot,
            opp_type="ANUNCIO",
            bbox_pct=BoundingBox(0, 0, 100, 100),
            company_hint=None,
            keywords=[],
            confidence=0.2,
            page_num=page_num,
            segment_idx=0,
        )]
