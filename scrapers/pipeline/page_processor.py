"""
Page Processor — Full pipeline orchestration.

Screenshot → Segment → Extract → Normalise → Persist

Integrates:
  VisualSegmenter  — detects announcement blocks
  VisionExtractor  — extracts structured data from each block
  Normalizer       — maps to NormalisedOpportunity
  Saver            — persists to PostgreSQL
"""
from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from scrapers.pipeline.visual_segmenter import PageSegment, VisualSegmenter
from scrapers.pipeline.normalizer import ensure_absolute_url, url_hash


class PageProcessor:
    """
    Processes a single newspaper page screenshot through the full pipeline.

    Usage:
        processor = PageProcessor(source_url="...", source_name="Jornal de Angola")
        results = await processor.process(screenshot_bytes, page_num=3)
        # results: list of NormalisedOpportunity
    """

    def __init__(
        self,
        source_url: str,
        source_name: str = "Jornal de Angola",
        dry_run: bool = True,
        save_crops: Path | None = None,
    ) -> None:
        self.source_url  = source_url
        self.source_name = source_name
        self.dry_run     = dry_run
        self.save_crops  = save_crops   # directory to save crop images for debugging
        self.segmenter   = VisualSegmenter()

    async def process(
        self,
        screenshot: bytes,
        page_num: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Full pipeline for one screenshot.
        Returns list of extraction results (raw dicts, not yet persisted).
        """
        logger.info("Processing page {}...", page_num)

        # ─── Pass 1: Segment page ─────────────────────────────────────────────
        segments = await self.segmenter.segment_page(screenshot, page_num)

        if not segments:
            logger.info("Page {}: no segments detected.", page_num)
            return []

        logger.info("Page {}: {} segments to extract", page_num, len(segments))

        # Save crop images if requested
        if self.save_crops:
            self.save_crops.mkdir(parents=True, exist_ok=True)
            for seg in segments:
                crop_path = self.save_crops / f"page{page_num:03d}_seg{seg.segment_idx:02d}_{seg.opp_type}.jpg"
                crop_path.write_bytes(seg.image_bytes)
                logger.debug("  Saved crop: {}", crop_path.name)

        # ─── Pass 2: Extract each segment ────────────────────────────────────
        results = []
        for seg in segments:
            await asyncio.sleep(0.3)  # rate limiting
            extracted = await self.segmenter.extract_segment(seg)

            # Skip non-opportunities
            if extracted.get("type") == "NOT_OPPORTUNITY":
                logger.debug("  Seg {}: not an opportunity, skipping", seg.segment_idx)
                continue
            if extracted.get("confidence", 0) < 0.3:
                logger.debug("  Seg {}: low confidence {:.2f}, skipping", seg.segment_idx, extracted.get("confidence", 0))
                continue
            if extracted.get("error"):
                continue

            # Enrich with source info
            extracted["_source_url"]     = self.source_url
            extracted["_source_name"]    = self.source_name
            extracted["_page_num"]       = page_num
            extracted["_segment_idx"]    = seg.segment_idx
            extracted["_company_hint"]   = seg.company_hint
            extracted["_bbox"]           = [
                seg.bbox_pct.x1, seg.bbox_pct.y1,
                seg.bbox_pct.x2, seg.bbox_pct.y2,
            ]
            extracted["_crop_size_kb"]   = len(seg.image_bytes) // 1024

            results.append(extracted)
            logger.success(
                "  ✓ [p{} s{}] {} — {} (conf={:.2f})",
                page_num, seg.segment_idx,
                extracted.get("type", "?"),
                str(extracted.get("organization") or extracted.get("title", "?"))[:50],
                extracted.get("confidence", 0),
            )

        return results

    async def process_multiple(
        self,
        screenshots: list[bytes],
        start_page: int = 1,
    ) -> list[dict[str, Any]]:
        """Process multiple pages. Returns all extraction results."""
        all_results = []
        for i, screenshot in enumerate(screenshots):
            page_num = start_page + i
            results = await self.process(screenshot, page_num)
            all_results.extend(results)
            await asyncio.sleep(1.0)  # pause between pages
        return all_results
