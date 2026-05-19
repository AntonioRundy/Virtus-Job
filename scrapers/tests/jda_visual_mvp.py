"""
JDA Visual Pipeline MVP
=======================
1 screenshot do PressReader → segmentação visual → Claude Vision → JSON → BD → API

Prova que o pipeline ponta-a-ponta funciona sem spider HTML.

Outputs em: scrapers/tests/output/
  jda_page_screenshot.png   — screenshot completo da página
  jda_segments/             — crops de cada bloco detectado
  jda_extraction_log.json   — log completo de cada extracção

Uso:
  python -m scrapers.tests.jda_visual_mvp [--dry-run]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).parent.parent.parent   # projecto root
OUTPUT_DIR  = Path(__file__).parent / "output"
SEGMENTS_DIR = OUTPUT_DIR / "jda_segments"
LOG_FILE    = OUTPUT_DIR / "jda_extraction_log.json"
SCREENSHOT  = OUTPUT_DIR / "jda_page_screenshot.png"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── DRY RUN flag ─────────────────────────────────────────────────────────────

DRY_RUN = "--dry-run" in sys.argv

# ─── Persistence thresholds ───────────────────────────────────────────────────

MIN_CONFIDENCE  = 0.70
REQUIRE_COMPANY = True   # empresa OU email obrigatório
REQUIRE_TITLE   = True   # cargo/title obrigatório

# ─── PressReader URLs ─────────────────────────────────────────────────────────
# Tentar múltiplas secções — parar na primeira que tiver conteúdo visual

PRESSREADER_TARGETS = [
    {
        "label": "Última edição (página principal)",
        "url":   "https://edicoesnovembro.pressreader.com/jornal-de-angola",
    },
]

# ─── AI cost tracking ─────────────────────────────────────────────────────────

class CostTracker:
    """Approximate cost tracking for Claude Sonnet 4.6 Vision."""
    INPUT_COST_PER_1K  = 0.003   # USD per 1K input tokens
    OUTPUT_COST_PER_1K = 0.015   # USD per 1K output tokens
    IMAGE_COST         = 0.0048  # ~$0.0048 per image (base64 encoded)

    def __init__(self):
        self.api_calls    = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.images       = 0

    def add_call(self, input_tok: int = 1000, output_tok: int = 500, images: int = 1):
        self.api_calls    += 1
        self.input_tokens += input_tok
        self.output_tokens += output_tok
        self.images       += images

    @property
    def estimated_usd(self) -> float:
        text_cost  = (self.input_tokens / 1000 * self.INPUT_COST_PER_1K +
                      self.output_tokens / 1000 * self.OUTPUT_COST_PER_1K)
        image_cost = self.images * self.IMAGE_COST
        return text_cost + image_cost

    def report(self) -> str:
        return (f"API calls: {self.api_calls} | "
                f"Images: {self.images} | "
                f"~{self.input_tokens} input tokens | "
                f"~{self.output_tokens} output tokens | "
                f"Custo estimado: ${self.estimated_usd:.4f} USD")


cost = CostTracker()


# ─── Browser screenshot ───────────────────────────────────────────────────────

async def capture_pressreader_screenshot(session_file: Path, url: str) -> bytes | None:
    """
    Navegar para o PressReader com sessão autenticada e capturar screenshot.
    Retorna bytes PNG ou None se falhar.
    """
    from playwright.async_api import async_playwright

    if not session_file.exists():
        logger.error("Sessão JDA não encontrada: {}", session_file)
        return None

    storage_state = json.loads(session_file.read_text(encoding="utf-8"))
    logger.info("Sessão JDA carregada ({} cookies)", len(storage_state.get("cookies", [])))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (compatible; VirtusJobBot/1.0; "
                "+https://virtusjob.ao/bot; contact@virtusjob.ao)"
            ),
            locale="pt-AO",
            # NÃO bloquear imagens — precisamos do jornal visual
        )
        page = await context.new_page()

        try:
            logger.info("Navegando para PressReader: {}", url)
            t0 = time.time()

            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            logger.info("DOM carregado em {:.1f}s", time.time() - t0)

            # Aguardar renderização do jornal (Angular SPA pesado)
            await asyncio.sleep(8)

            # Tentar esperar por conteúdo visual
            for selector in [
                ".issue-page",
                ".newspaper-page",
                "canvas",
                "[class*='page']",
                "[class*='issue']",
                "[class*='reader']",
                "img[src*='pressreader']",
                ".page-container",
            ]:
                el = await page.query_selector(selector)
                if el:
                    logger.info("Conteúdo visual detectado: selector='{}'", selector)
                    await asyncio.sleep(2)
                    break
            else:
                logger.warning("Sem selector de conteúdo visual encontrado — aguardar 3s adicional")
                await asyncio.sleep(3)

            logger.info("URL actual: {}", page.url)
            logger.info("Título: {}", await page.title())

            # Capturar screenshot completo
            screenshot = await page.screenshot(
                full_page=True,
                type="png",
            )
            logger.info(
                "Screenshot capturado: {:.0f}KB | {:.1f}s total",
                len(screenshot) / 1024,
                time.time() - t0,
            )
            return screenshot

        except Exception as exc:
            logger.error("Erro a capturar screenshot: {}", exc)
            return None
        finally:
            await context.close()
            await browser.close()


# ─── Persistence ──────────────────────────────────────────────────────────────

async def persist_result(extracted: dict, source_url: str, page_num: int, seg_idx: int) -> str | None:
    """
    Persiste um resultado extraído na BD.
    Retorna o slug criado ou None.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from scrapers.config import settings
    from scrapers.pipeline.normalizer import Normalizer
    from scrapers.pipeline.saver import OpportunitySaver
    from scrapers.models import AIExtractionResult, RawPage, OpportunityType

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Converter formato visual → AIExtractionResult
    type_map = {
        "VAGA": OpportunityType.VAGA,
        "CONCURSO": OpportunityType.CONCURSO,
        "BOLSA": OpportunityType.BOLSA,
        "ESTAGIO": OpportunityType.ESTAGIO,
        "FORMACAO": OpportunityType.FORMACAO,
    }
    opp_type = type_map.get(extracted.get("type", "VAGA"), OpportunityType.VAGA)

    ai_result = AIExtractionResult(
        title=extracted.get("title") or "Anúncio JDA (visual)",
        type=opp_type,
        description=extracted.get("description") or "",
        organization=extracted.get("organization"),
        province=extracted.get("location"),
        deadline=extracted.get("deadline"),
        requirements=extracted.get("requirements", []),
        confidence=float(extracted.get("confidence", 0.7)),
        requires_review=True,  # sempre requer revisão para visual
        categories=extracted.get("categories", ["Jornal de Angola", "Visual"]),
    )

    raw = RawPage(
        url=f"{source_url}#p{page_num}s{seg_idx}",
        source_name="Jornal de Angola",
        source_id="jornal_angola",
        html="",
        title=ai_result.title,
        http_status=200,
    )

    normalizer = Normalizer()
    normalised = normalizer.normalise(raw, ai_result)

    # Gerar slug antecipadamente (mesmo algoritmo do saver)
    from app.services.opportunities import _make_slug
    slug = _make_slug(normalised.title, normalised.type.value)

    async with factory() as db:
        saver = OpportunitySaver(db, dry_run=DRY_RUN)
        saved = await saver.save(normalised)
        if saved:
            await db.commit()
            logger.success("Persistido: {} (slug: {})", normalised.title[:60], slug[:40])
            return slug

    await engine.dispose()
    return None


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def run_visual_mvp():
    from scrapers.config import settings
    from scrapers.pipeline.page_processor import PageProcessor

    logger.info("=" * 65)
    logger.info("JDA Visual Pipeline MVP  |  dry_run={}", DRY_RUN)
    logger.info("=" * 65)

    session_file = Path(settings.JDA_SESSION_FILE)
    t_start = time.time()

    # ─── 1. Capturar screenshot ───────────────────────────────────────────────
    # Se já existe um screenshot do PressReader, usar esse (mais fiel ao jornal)
    pressreader_shot = OUTPUT_DIR / "jda_pressreader_screenshot.png"
    url_file = OUTPUT_DIR / "jda_pressreader_url.txt"

    # Preferir o viewport screenshot (mais limpo para AI)
    viewport_shot = OUTPUT_DIR / "jda_pressreader_viewport.png"
    if viewport_shot.exists() and viewport_shot.stat().st_size > 50_000:
        pressreader_shot = viewport_shot

    if pressreader_shot.exists() and pressreader_shot.stat().st_size > 50_000:
        logger.info("[BROWSER] Usar screenshot PressReader já capturado ({:.0f}KB)",
                    pressreader_shot.stat().st_size / 1024)
        screenshot = pressreader_shot.read_bytes()
        source_url = url_file.read_text(encoding="utf-8").strip() if url_file.exists() else PRESSREADER_TARGETS[0]["url"]
        SCREENSHOT.write_bytes(screenshot)
    else:
        screenshot = None
        source_url = ""
        for target in PRESSREADER_TARGETS:
            logger.info("\n[BROWSER] Tentar: {}", target["label"])
            screenshot = await capture_pressreader_screenshot(session_file, target["url"])
            if screenshot:
                source_url = target["url"]
                break

        if not screenshot:
            logger.error("Não foi possível capturar screenshot de nenhum URL.")
            return
        SCREENSHOT.write_bytes(screenshot)

    logger.info("[SAVED] Screenshot → {} ({:.0f}KB)", SCREENSHOT.name, len(screenshot) / 1024)

    # ─── 2. Pipeline visual ───────────────────────────────────────────────────
    logger.info("\n[PIPELINE] Iniciando segmentação visual...")
    processor = PageProcessor(
        source_url=source_url,
        source_name="Jornal de Angola",
        dry_run=DRY_RUN,
        save_crops=SEGMENTS_DIR,
    )

    # Converter PNG para JPEG para eficiência
    from PIL import Image
    import io as _io
    img = Image.open(_io.BytesIO(screenshot))
    buf = _io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    jpeg_bytes = buf.getvalue()

    cost.add_call(input_tok=2000, output_tok=500, images=1)  # Pass 1

    results = await processor.process(jpeg_bytes, page_num=1)

    logger.info("\n[RESULTS] Segmentos extraídos: {}", len(results))

    # ─── 3. Filtrar e persistir ───────────────────────────────────────────────
    extraction_log = []
    persisted = []

    for i, ext in enumerate(results):
        conf      = float(ext.get("confidence", 0))
        title     = ext.get("title") or ""
        org       = ext.get("organization") or ""
        email     = ext.get("contact_email") or ""
        seg_idx   = ext.get("_segment_idx", i)
        crop_kb   = ext.get("_crop_size_kb", 0)

        cost.add_call(input_tok=1200, output_tok=400, images=1)  # Pass 2

        log_entry = {
            "segment": seg_idx,
            "title":   title,
            "type":    ext.get("type"),
            "org":     org,
            "email":   email,
            "conf":    conf,
            "bbox":    ext.get("_bbox"),
            "crop_kb": crop_kb,
            "persisted": False,
            "slug":    None,
        }

        logger.info(
            "\n  Seg {}: [{}] {} | org='{}' | email='{}' | conf={:.2f}",
            seg_idx, ext.get("type", "?"), title[:50], org[:30], email[:30], conf,
        )

        # Decisão de persistência
        skip_reason = None
        if conf < MIN_CONFIDENCE:
            skip_reason = f"confidence {conf:.2f} < {MIN_CONFIDENCE}"
        elif REQUIRE_COMPANY and not org and not email:
            skip_reason = "empresa e email ausentes"
        elif REQUIRE_TITLE and not title:
            skip_reason = "título ausente"

        if skip_reason:
            logger.warning("  SKIP: {}", skip_reason)
            log_entry["skip_reason"] = skip_reason
        else:
            logger.info("  PASS — persistindo...")
            slug = await persist_result(ext, source_url, page_num=1, seg_idx=seg_idx)
            if slug:
                log_entry["persisted"] = True
                log_entry["slug"] = slug
                persisted.append(slug)

        extraction_log.append(log_entry)

    # ─── 4. Guardar log completo ──────────────────────────────────────────────
    log_data = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "source_url":  source_url,
        "dry_run":     DRY_RUN,
        "screenshot_kb": len(screenshot) // 1024,
        "segments_found": len(results),
        "persisted_count": len(persisted),
        "persisted_slugs": persisted,
        "cost": cost.estimated_usd,
        "api_calls": cost.api_calls,
        "duration_s": round(time.time() - t_start, 1),
        "extractions": extraction_log,
    }
    LOG_FILE.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ─── 5. Relatório final ───────────────────────────────────────────────────
    duration = time.time() - t_start
    logger.info("\n" + "=" * 65)
    logger.info("RELATÓRIO FINAL")
    logger.info("=" * 65)
    logger.info("Duração total:       {:.1f}s", duration)
    logger.info("Screenshot:          {} ({:.0f}KB)", SCREENSHOT.name, len(screenshot) / 1024)
    logger.info("Segmentos detectados: {}", len(results))
    logger.info("Persistidos:         {} {}", len(persisted), "(DRY RUN)" if DRY_RUN else "")
    logger.info("{}", cost.report())
    logger.info("Log completo →       {}", LOG_FILE)

    if persisted:
        logger.info("\n  Slugs persistidos:")
        for slug in persisted:
            logger.info("    → {}", slug)
            logger.info("      API: http://localhost:8000/api/v1/opportunities/{}", slug)

    if not results:
        logger.warning("\n  Sem segmentos extraídos.")
        logger.warning("  Provável causa: página renderizada como UI chrome sem conteúdo de jornal.")
        logger.warning("  Verificar screenshot salvo em: {}", SCREENSHOT)
        logger.warning("  Pode ser necessário aguardar mais tempo para o PressReader renderizar.")

    logger.info("=" * 65)
    return log_data


if __name__ == "__main__":
    import os
    # Configurar encoding para Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job"
    )

    asyncio.run(run_visual_mvp())
