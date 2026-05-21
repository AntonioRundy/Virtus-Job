"""
Virtus Job — JDA Daily Pipeline
================================
Captura diária completa do Jornal de Angola via PressReader.

Fluxo:
  1. Verificar se já correu hoje (skip se sim)
  2. Login em jornaldeangola.ao → token SSO
  3. Abrir PressReader autenticado
  4. Navegar todas as páginas (ArrowRight) + capturar imagens
  5. Pipeline visual (Claude Vision segmentação + extracção)
  6. Persistir oportunidades na BD
  7. Promover automaticamente para ACTIVE
  8. Limpar ficheiros temporários
  9. Log completo com métricas

Uso:
  python -m scrapers.jda_daily
  python -m scrapers.jda_daily --force        # ignorar skip "já correu hoje"
  python -m scrapers.jda_daily --dry-run      # processar mas não guardar na BD
  python -m scrapers.jda_daily --pages 14-35  # só páginas específicas
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from loguru import logger

# ─── Paths ───────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent
PAGES_DIR   = SCRAPER_DIR / "output" / "jda_daily_pages"
CROPS_DIR   = SCRAPER_DIR / "output" / "jda_daily_crops"
LOG_DIR     = ROOT / "logs"
RUN_LOG     = LOG_DIR / "jda_daily_runs.json"
SESSION_FILE = SCRAPER_DIR / "sessions" / "jda_session.json"

for d in [PAGES_DIR, CROPS_DIR, LOG_DIR, SESSION_FILE.parent]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Config ───────────────────────────────────────────────────────────────────

MIN_CONFIDENCE = 0.65      # abaixo disto: não guardar
MAX_NAV_STEPS  = 18        # passos ArrowRight máximos (cobre ~36 páginas)
WAIT_AFTER_LOAD = 18       # segundos para PressReader renderizar
PAGE_DELAY      = 1.5      # segundos entre passos de navegação

import os
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job"
)


# ─── Logging setup ───────────────────────────────────────────────────────────

def setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
    )
    log_file = LOG_DIR / f"jda_daily_{date.today().isoformat()}.log"
    logger.add(log_file, level="DEBUG", encoding="utf-8",
               rotation="7 days", retention="30 days")


# ─── Already-ran check ───────────────────────────────────────────────────────

def already_ran_today() -> bool:
    """Retorna True se o pipeline já correu hoje com sucesso."""
    if not RUN_LOG.exists():
        return False
    try:
        runs = json.loads(RUN_LOG.read_text(encoding="utf-8"))
        today = date.today().isoformat()
        return any(r.get("date") == today and r.get("success") for r in runs)
    except Exception:
        return False


def record_run(success: bool, saved: int, duration: float, error: str = "") -> None:
    runs = []
    if RUN_LOG.exists():
        try:
            runs = json.loads(RUN_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    runs.append({
        "date": date.today().isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "saved": saved,
        "duration_s": round(duration, 1),
        "error": error,
    })
    # manter só os últimos 60 registos
    RUN_LOG.write_text(json.dumps(runs[-60:], indent=2), encoding="utf-8")


# ─── Browser: login + PressReader ────────────────────────────────────────────

async def open_pressreader(context) -> tuple:
    """
    Login no JDA + abre PressReader.
    Retorna (page, edition_date_str) ou (None, None) se falhar.
    """
    from scrapers.config import settings

    page = await context.new_page()

    # ── Login ──────────────────────────────────────────────────────────────
    logger.info("Login em jornaldeangola.ao...")
    await page.goto(
        "https://jornaldeangola.ao/#/assinantes/login",
        wait_until="domcontentloaded", timeout=30000,
    )
    await asyncio.sleep(3)

    overlay = await page.query_selector(".cdk-overlay-backdrop")
    if overlay:
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.5)

    entrar = await page.query_selector("button:has-text('Entrar'), button.bg-black")
    if entrar:
        await entrar.click()
        await asyncio.sleep(2)

    em = await page.query_selector("input[formcontrolname='email']")
    pw = await page.query_selector("input[type='password']")
    if not em or not pw:
        logger.error("Formulário de login não encontrado")
        return None, None

    await em.fill(settings.JDA_EMAIL)
    await pw.fill(settings.JDA_PASSWORD)
    await pw.press("Enter")
    await asyncio.sleep(5)

    post_login_url = page.url
    if "assinantes" not in post_login_url and "area-reservada" not in post_login_url:
        logger.error("Login falhou — URL: {}", post_login_url)
        return None, None
    logger.info("Login OK — {}", post_login_url)

    # ── Dispensar overlays/modais antes de clicar LER O JORNAL ───────────
    # A página de assinaturas pode ter popups publicitários (CDK overlay)
    for attempt in range(4):
        overlay = await page.query_selector(".cdk-overlay-backdrop, .cdk-overlay-container img")
        if not overlay:
            break
        logger.debug("Overlay detectado na página de assinaturas (tentativa {}) — a fechar...", attempt + 1)
        # Tentar fechar: Escape, depois clicar fora, depois clicar no X
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.0)
        close_btn = await page.query_selector(
            "button[mat-dialog-close], button[aria-label='Close'], "
            "button[aria-label='Fechar'], .mat-dialog-close, "
            "[mat-dialog-close], button:has-text('×'), button:has-text('✕')"
        )
        if close_btn:
            await close_btn.click(force=True)
            await asyncio.sleep(0.8)

    # ── LER O JORNAL ───────────────────────────────────────────────────────
    ler = await page.query_selector("button:has-text('LER O JORNAL')")
    if not ler:
        logger.error("Botão LER O JORNAL não encontrado")
        return None, None

    # Usar force=True para ignorar intercepções de overlay residuais
    async with context.expect_page(timeout=15000) as np_info:
        await ler.click(force=True)
    pr = await np_info.value
    await pr.wait_for_load_state("domcontentloaded", timeout=20000)
    await asyncio.sleep(WAIT_AFTER_LOAD)

    # Extrair data da edição (do título ou URL)
    edition_date = date.today().isoformat().replace("-", "")
    title = await pr.title()
    logger.info("PressReader carregado — Título: {} | URL: {}", title, pr.url[:60])

    # Guardar sessão actualizada
    storage = await context.storage_state()
    SESSION_FILE.write_text(json.dumps(storage, indent=2), encoding="utf-8")
    logger.debug("Sessão guardada: {} cookies", len(storage.get("cookies", [])))

    return pr, edition_date


# ─── Capture pages ───────────────────────────────────────────────────────────

async def capture_all_pages(pr, edition_date: str, pages_dir: Path) -> list[dict]:
    """
    Navega o PressReader página a página e captura imagens via element screenshot.
    Retorna lista de {page_num, path, kb}.
    """
    pages_dir.mkdir(parents=True, exist_ok=True)
    captured_srcs: set[str] = set()
    all_pages: list[dict] = []

    async def capture_visible(step: int) -> list[dict]:
        found = []
        imgs = await pr.query_selector_all(".page img")
        for img in imgs:
            src = await img.get_attribute("src") or ""
            if not src or src in captured_srcs or "prcdn.co" not in src:
                continue
            try:
                visible = await img.is_visible()
                if not visible:
                    continue
                shot = await img.screenshot(type="png")
                if len(shot) < 5000:  # imagem em branco
                    continue
                captured_srcs.add(src)
                page_num = 0
                if "page=" in src:
                    try:
                        page_num = int(src.split("page=")[1].split("&")[0])
                    except ValueError:
                        pass
                fname = f"p{page_num:03d}.png"
                fpath = pages_dir / fname
                fpath.write_bytes(shot)
                found.append({"page": page_num, "path": str(fpath),
                               "kb": len(shot) // 1024})
            except Exception:
                pass
        return found

    # Capturar estado inicial
    initial = await capture_visible(0)
    all_pages.extend(initial)
    if initial:
        logger.info("  Estado inicial: páginas {}", [p["page"] for p in initial])

    # Navegar com ArrowRight
    for step in range(1, MAX_NAV_STEPS + 1):
        await pr.keyboard.press("ArrowRight")
        await asyncio.sleep(PAGE_DELAY)
        new = await capture_visible(step)
        if new:
            all_pages.extend(new)
            logger.debug("  Step {}: páginas {}", step, [p["page"] for p in new])

    all_pages.sort(key=lambda x: x["page"])
    logger.info("Total páginas capturadas: {} (pages {})",
                len(all_pages), [p["page"] for p in all_pages])
    return all_pages


# ─── Process + persist ───────────────────────────────────────────────────────

async def process_and_persist(
    pages: list[dict],
    edition_date: str,
    crops_dir: Path,
    dry_run: bool,
    page_filter: tuple[int, int] | None = None,
) -> dict:
    """
    Corre pipeline visual em todas as páginas e persiste na BD.
    Retorna métricas do run.
    """
    from PIL import Image
    import io as _io
    from scrapers.pipeline.page_processor import PageProcessor
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from scrapers.config import settings
    from scrapers.pipeline.normalizer import Normalizer
    from scrapers.pipeline.saver import OpportunitySaver
    from scrapers.models import AIExtractionResult, RawPage, OpportunityType
    from app.services.opportunities import _make_slug

    source_url_base = f"https://edicoesnovembro.pressreader.com/jornal-de-angola/{edition_date}"
    total_segments = 0
    total_saved = 0
    total_skipped = 0
    api_calls = 0
    saved_slugs: list[str] = []

    type_map = {
        "VAGA": OpportunityType.VAGA, "CONCURSO": OpportunityType.CONCURSO,
        "BOLSA": OpportunityType.BOLSA, "ESTAGIO": OpportunityType.ESTAGIO,
        "FORMACAO": OpportunityType.FORMACAO,
    }

    # Filtro de páginas opcional
    if page_filter:
        pages = [p for p in pages if page_filter[0] <= p["page"] <= page_filter[1]]

    for page_info in pages:
        page_num = page_info["page"]
        img_path = Path(page_info["path"])
        if not img_path.exists():
            continue

        # Converter PNG → JPEG
        img = Image.open(img_path)
        buf = _io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=92)
        jpeg = buf.getvalue()

        page_crops = crops_dir / f"page{page_num:03d}"
        page_crops.mkdir(parents=True, exist_ok=True)

        processor = PageProcessor(
            source_url=f"{source_url_base}#p{page_num}",
            source_name="Jornal de Angola",
            dry_run=dry_run,
            save_crops=page_crops,
        )

        try:
            results = await processor.process(jpeg, page_num=page_num)
            api_calls += len(results) + 1  # pass1 + N pass2

            if results:
                logger.info("  Pág {:02d}: {} segmentos", page_num, len(results))
            total_segments += len(results)

            for ext in results:
                conf  = float(ext.get("confidence", 0))
                title = (ext.get("title") or "").strip()
                org   = (ext.get("organization") or "").strip()
                email = (ext.get("contact_email") or "").strip()
                seg   = ext.get("_segment_idx", 0)

                if conf < MIN_CONFIDENCE:
                    total_skipped += 1
                    continue
                if not org and not email:
                    total_skipped += 1
                    continue
                if not title:
                    total_skipped += 1
                    continue

                # Persistir
                opp_type = type_map.get(ext.get("type", "VAGA"), OpportunityType.VAGA)
                ai_result = AIExtractionResult(
                    title=title,
                    type=opp_type,
                    description=ext.get("description") or "",
                    organization=org or None,
                    province=ext.get("location"),
                    deadline=ext.get("deadline"),
                    requirements=ext.get("requirements", []),
                    confidence=conf,
                    requires_review=False,  # JDA é fonte confiável
                    categories=ext.get("categories", ["Jornal de Angola"]),
                )
                raw = RawPage(
                    url=f"{source_url_base}#p{page_num}s{seg}",
                    source_name="Jornal de Angola",
                    source_id="jornal_angola",
                    html="", title=title, http_status=200,
                )
                normalizer = Normalizer()
                normalised = normalizer.normalise(raw, ai_result)
                slug = _make_slug(normalised.title, normalised.type.value)

                if not dry_run:
                    engine = create_async_engine(
                        settings.DATABASE_URL, echo=False, pool_pre_ping=True
                    )
                    factory = async_sessionmaker(engine, class_=AsyncSession,
                                                 expire_on_commit=False)
                    async with factory() as db:
                        saver = OpportunitySaver(db, dry_run=False)
                        saved = await saver.save(normalised)
                        if saved:
                            await db.commit()
                            saved_slugs.append(slug)
                            total_saved += 1
                            logger.success(
                                "    SAVED [{} | {:.2f}] {} — {}",
                                ext.get("type", "?"), conf,
                                org[:35], title[:40],
                            )
                    await engine.dispose()
                else:
                    logger.info(
                        "    DRY [{} | {:.2f}] {} — {}",
                        ext.get("type", "?"), conf, org[:35], title[:40],
                    )
                    total_saved += 1
                    saved_slugs.append(slug)

        except Exception as exc:
            logger.error("  Pág {}: ERRO — {}", page_num, exc)

        await asyncio.sleep(0.5)

    return {
        "total_segments": total_segments,
        "total_saved": total_saved,
        "total_skipped": total_skipped,
        "api_calls": api_calls,
        "slugs": saved_slugs,
    }


async def promote_to_active(slugs: list[str]) -> int:
    """Promove oportunidades JDA recém-criadas para ACTIVE."""
    if not slugs:
        return 0
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import update
    from scrapers.config import settings
    from app.models.opportunity import Opportunity

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    promoted = 0
    async with factory() as db:
        result = await db.execute(
            update(Opportunity)
            .where(
                Opportunity.slug.in_(slugs),
                Opportunity.status == "UNVERIFIED",
            )
            .values(status="ACTIVE", trust_level="INSTITUTIONAL", trust_score=0.75)
        )
        promoted = result.rowcount
        await db.commit()
    await engine.dispose()
    return promoted


def cleanup_pages(pages_dir: Path, keep_days: int = 3) -> None:
    """Remove capturas antigas para poupar espaço em disco."""
    try:
        import shutil
        cutoff = time.time() - keep_days * 86400
        removed = 0
        for item in pages_dir.parent.iterdir():
            if item.is_dir() and item.stat().st_mtime < cutoff:
                shutil.rmtree(item, ignore_errors=True)
                removed += 1
        if removed:
            logger.debug("Limpeza: {} pastas antigas removidas", removed)
    except Exception:
        pass


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run(args) -> bool:
    t_start = time.time()
    today = date.today().isoformat()

    logger.info("=" * 60)
    logger.info("JDA Daily Pipeline — {}", today)
    logger.info("dry_run={} | force={}", args.dry_run, args.force)
    logger.info("=" * 60)

    # Skip check
    if not args.force and already_ran_today():
        logger.info("Pipeline já correu hoje com sucesso. Usa --force para repetir.")
        return True

    # Directórios desta corrida
    edition_pages = PAGES_DIR / today.replace("-", "")
    edition_crops = CROPS_DIR / today.replace("-", "")

    from playwright.async_api import async_playwright

    total_saved = 0
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pt-AO",
            )

            # ── 1. Login + PressReader ────────────────────────────────────
            pr_page, edition_date = await open_pressreader(context)
            if not pr_page:
                raise RuntimeError("Falha ao abrir PressReader")

            # ── 2. Capturar páginas ───────────────────────────────────────
            logger.info("Capturando páginas do jornal...")
            pages = await capture_all_pages(pr_page, edition_date, edition_pages)
            logger.info("{} páginas capturadas", len(pages))

            await browser.close()

        if not pages:
            raise RuntimeError("Nenhuma página capturada do PressReader")

        # ── 3. Pipeline visual ────────────────────────────────────────────
        logger.info("Iniciando pipeline visual Claude Vision...")

        page_filter = None
        if args.pages:
            try:
                lo, hi = args.pages.split("-")
                page_filter = (int(lo), int(hi))
                logger.info("Filtro de páginas: {}-{}", *page_filter)
            except Exception:
                pass

        metrics = await process_and_persist(
            pages, edition_date, edition_crops, args.dry_run, page_filter
        )
        total_saved = metrics["total_saved"]

        # ── 4. Promover para ACTIVE ───────────────────────────────────────
        if not args.dry_run and metrics["slugs"]:
            promoted = await promote_to_active(metrics["slugs"])
            logger.success("{} oportunidades promovidas para ACTIVE", promoted)

        # ── 5. Relatório ──────────────────────────────────────────────────
        duration = time.time() - t_start
        est_cost = metrics["api_calls"] * 0.006

        logger.info("")
        logger.info("─── Resultado ─────────────────────────────")
        logger.info("  Páginas processadas:  {}", len(pages))
        logger.info("  Segmentos detectados: {}", metrics["total_segments"])
        logger.info("  Guardadas (ACTIVE):   {} {}", total_saved,
                    "(DRY RUN)" if args.dry_run else "")
        logger.info("  Skipped:              {}", metrics["total_skipped"])
        logger.info("  Custo estimado:       ~${:.3f} USD", est_cost)
        logger.info("  Duração:              {:.0f}s ({:.1f}min)",
                    duration, duration / 60)
        logger.info("──────────────────────────────────────────")

        # ── 6. Limpeza ────────────────────────────────────────────────────
        cleanup_pages(PAGES_DIR)
        cleanup_pages(CROPS_DIR)

        if not args.dry_run:
            record_run(True, total_saved, duration)

        return True

    except Exception as exc:
        duration = time.time() - t_start
        logger.error("PIPELINE FALHOU: {}", exc)
        record_run(False, total_saved, duration, str(exc))
        return False


def main():
    parser = argparse.ArgumentParser(description="JDA Daily Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Processar mas não guardar na BD")
    parser.add_argument("--force", action="store_true",
                        help="Correr mesmo que já tenha corrido hoje")
    parser.add_argument("--pages", type=str, default=None,
                        help="Limitar páginas (ex: 14-35)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
                                       encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer,
                                       encoding="utf-8", errors="replace")

    success = asyncio.run(run(args))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
