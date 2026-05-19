"""
Processa TODAS as páginas capturadas do JDA através do pipeline visual completo.
Screenshot → Claude Vision (segmentação) → Claude Vision (extracção) → BD → API

Executa em todas as páginas de scrapers/tests/output/jda_page_nav/*.png
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from loguru import logger

PAGES_DIR = Path(__file__).parent / "output" / "jda_page_nav"
CROPS_DIR = Path(__file__).parent / "output" / "jda_segments_all"
LOG_FILE  = Path(__file__).parent / "output" / "jda_full_run_log.json"

CROPS_DIR.mkdir(parents=True, exist_ok=True)

MIN_CONFIDENCE  = 0.65   # threshold para persistir
SOURCE_URL      = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260519"
SOURCE_NAME     = "Jornal de Angola"

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job")


async def persist(extracted: dict, page_num: int, seg_idx: int, dry_run: bool) -> str | None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from scrapers.config import settings
    from scrapers.pipeline.normalizer import Normalizer
    from scrapers.pipeline.saver import OpportunitySaver
    from scrapers.models import AIExtractionResult, RawPage, OpportunityType
    from app.services.opportunities import _make_slug

    type_map = {
        "VAGA": OpportunityType.VAGA, "CONCURSO": OpportunityType.CONCURSO,
        "BOLSA": OpportunityType.BOLSA, "ESTAGIO": OpportunityType.ESTAGIO,
        "FORMACAO": OpportunityType.FORMACAO,
    }
    opp_type = type_map.get(extracted.get("type", "VAGA"), OpportunityType.VAGA)

    ai_result = AIExtractionResult(
        title=extracted.get("title") or "Anúncio JDA",
        type=opp_type,
        description=extracted.get("description") or "",
        organization=extracted.get("organization"),
        province=extracted.get("location"),
        deadline=extracted.get("deadline"),
        requirements=extracted.get("requirements", []),
        confidence=float(extracted.get("confidence", 0.7)),
        requires_review=True,
        categories=extracted.get("categories", ["Jornal de Angola"]),
    )

    raw = RawPage(
        url=f"{SOURCE_URL}#p{page_num}s{seg_idx}",
        source_name=SOURCE_NAME,
        source_id="jornal_angola",
        html="",
        title=ai_result.title,
        http_status=200,
    )

    normalizer = Normalizer()
    normalised = normalizer.normalise(raw, ai_result)
    slug = _make_slug(normalised.title, normalised.type.value)

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        saver = OpportunitySaver(db, dry_run=dry_run)
        saved = await saver.save(normalised)
        if saved:
            await db.commit()
            logger.success("  SAVED: {} (slug: {})", normalised.title[:55], slug[:35])
            await engine.dispose()
            return slug

    await engine.dispose()
    return None


async def process_page(
    img_path: Path,
    page_num: int,
    dry_run: bool,
    crops_dir: Path,
) -> dict:
    from scrapers.pipeline.page_processor import PageProcessor
    from PIL import Image
    import io as _io

    # Converter PNG → JPEG para Claude Vision
    img = Image.open(img_path)
    buf = _io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    jpeg = buf.getvalue()

    page_crops = crops_dir / f"page{page_num:03d}"
    page_crops.mkdir(exist_ok=True)

    processor = PageProcessor(
        source_url=SOURCE_URL,
        source_name=SOURCE_NAME,
        dry_run=dry_run,
        save_crops=page_crops,
    )

    t0 = time.time()
    results = await processor.process(jpeg, page_num=page_num)
    elapsed = time.time() - t0

    saved_slugs = []
    skipped = []

    for ext in results:
        conf  = float(ext.get("confidence", 0))
        title = ext.get("title") or ""
        org   = ext.get("organization") or ""
        email = ext.get("contact_email") or ""
        seg   = ext.get("_segment_idx", 0)

        if conf < MIN_CONFIDENCE:
            skipped.append({"reason": f"conf {conf:.2f} < {MIN_CONFIDENCE}", "title": title})
            continue
        if not org and not email:
            skipped.append({"reason": "sem empresa/email", "title": title})
            continue
        if not title:
            skipped.append({"reason": "sem título", "title": ""})
            continue

        slug = await persist(ext, page_num, seg, dry_run)
        if slug:
            saved_slugs.append(slug)

    return {
        "page": page_num,
        "file": img_path.name,
        "segments_found": len(results),
        "saved": len(saved_slugs),
        "skipped": len(skipped),
        "slugs": saved_slugs,
        "elapsed_s": round(elapsed, 1),
    }


async def main():
    dry_run = "--dry-run" in sys.argv

    logger.info("=" * 65)
    logger.info("JDA FULL PIPELINE — {} páginas", "TODAS AS")
    logger.info("dry_run={} | min_confidence={}", dry_run, MIN_CONFIDENCE)
    logger.info("=" * 65)

    # Ordenar páginas por número
    pages = sorted(PAGES_DIR.glob("*.png"))
    logger.info("Páginas encontradas: {}", len(pages))

    t_total = time.time()
    all_results = []
    total_saved = 0
    total_segments = 0
    api_calls = 0

    for img_path in pages:
        # Extrair número da página do nome do ficheiro
        name = img_path.stem  # ex: step09_page022_567x746
        page_num = 0
        if "page" in name:
            try:
                page_num = int(name.split("page")[1].split("_")[0])
            except (ValueError, IndexError):
                pass

        logger.info("\n[PÁG {:02d}] {} ({:.0f}KB)", page_num, img_path.name,
                    img_path.stat().st_size / 1024)

        try:
            result = await process_page(img_path, page_num, dry_run, CROPS_DIR)
            all_results.append(result)
            total_saved    += result["saved"]
            total_segments += result["segments_found"]
            api_calls      += result["segments_found"] + 1  # 1 pass1 + N pass2

            logger.info(
                "  → {} segmentos | {} guardados | {}s",
                result["segments_found"], result["saved"], result["elapsed_s"],
            )
            if result["slugs"]:
                for slug in result["slugs"]:
                    logger.info("    slug: {}", slug[:55])

        except Exception as exc:
            logger.error("  ERRO na pág {}: {}", page_num, exc)
            all_results.append({"page": page_num, "error": str(exc)})

        # Pausa entre páginas para não sobrecarregar API Anthropic
        await asyncio.sleep(1)

    # Relatório final
    duration = time.time() - t_total
    logger.info("\n" + "=" * 65)
    logger.info("RELATÓRIO FINAL")
    logger.info("=" * 65)
    logger.info("Páginas processadas: {}", len(pages))
    logger.info("Segmentos detectados: {}", total_segments)
    logger.info("Oportunidades guardadas: {} {}", total_saved,
                "(DRY RUN)" if dry_run else "")
    logger.info("Chamadas API estimadas: {}", api_calls)
    logger.info("Custo estimado: ~${:.3f} USD",
                api_calls * 0.006)  # ~$0.006 por chamada Claude Sonnet com imagem
    logger.info("Duração total: {:.0f}s ({:.1f}min)", duration, duration / 60)

    # Guardar log
    LOG_FILE.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": dry_run,
        "pages": len(pages),
        "total_segments": total_segments,
        "total_saved": total_saved,
        "duration_s": round(duration, 1),
        "results": all_results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Log: {}", LOG_FILE)


asyncio.run(main())
