"""
Usando o fluxo de login comprovado: captura elementos .page img do PressReader
e analisa com Claude qual página tem anúncios de emprego.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import anthropic

OUTPUT = Path(__file__).parent / "output" / "jda_page_crops"
OUTPUT.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job")


async def login_and_open_pressreader(context):
    """Fluxo de login comprovado. Retorna a página PressReader."""
    from scrapers.config import settings

    page = await context.new_page()

    # 1. Login
    await page.goto("https://jornaldeangola.ao/#/assinantes/login",
                    wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # Dismiss overlay
    overlay = await page.query_selector(".cdk-overlay-backdrop")
    if overlay:
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.5)

    # Clicar Entrar
    entrar = await page.query_selector("button:has-text('Entrar'), button.bg-black")
    if entrar:
        await entrar.click()
        await asyncio.sleep(2)

    # Preencher form
    em = await page.query_selector("input[formcontrolname='email']")
    pw = await page.query_selector("input[type='password']")
    if em and pw:
        await em.fill(settings.JDA_EMAIL)
        await pw.fill(settings.JDA_PASSWORD)
        await pw.press("Enter")
        await asyncio.sleep(5)

    print(f"    URL pós-login: {page.url}")

    # 2. Clicar LER O JORNAL
    ler = await page.query_selector("button:has-text('LER O JORNAL')")
    if not ler:
        print("    AVISO: 'LER O JORNAL' não encontrado — tentar variantes...")
        for text in ["Leia o Jornal", "Ler Jornal", "Ver Jornal", "Aceder ao Jornal"]:
            btn = await page.query_selector(f"button:has-text('{text}')")
            if btn:
                ler = btn
                print(f"    Encontrado: {text}")
                break

    if not ler:
        print("    ERRO FATAL: nenhum botão LER encontrado")
        return None

    # 3. Abrir nova tab do PressReader
    async with context.expect_page(timeout=15000) as np_info:
        await ler.click()
    pr_page = await np_info.value
    await pr_page.wait_for_load_state("domcontentloaded", timeout=20000)
    await asyncio.sleep(20)  # PressReader precisa de tempo

    print(f"    PressReader URL: {pr_page.url[:80]}")
    return pr_page


async def main():
    from playwright.async_api import async_playwright

    print("=== JDA → Capturar Páginas do Jornal ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-AO",
        )

        print("[1] Login + PressReader...")
        pr = await login_and_open_pressreader(context)
        if not pr:
            await browser.close()
            return

        # Screenshot inicial
        shot0 = await pr.screenshot(type="png")
        (OUTPUT / "00_pressreader_initial.png").write_bytes(shot0)
        print(f"    Screenshot inicial: {len(shot0)//1024}KB")

        # Contar páginas disponíveis no DOM
        page_count = await pr.evaluate(
            "document.querySelectorAll('.page img').length"
        )
        print(f"    Páginas no DOM: {page_count}")

        # ── SCROLL + CAPTURA DE ELEMENTOS ─────────────────────────────────────
        print("\n[2] Capturar elementos de página...")

        captured_srcs: set[str] = set()
        pages_captured: list[dict] = []

        for scroll_n in range(15):
            scroll_px = scroll_n * 400
            await pr.evaluate(f"window.scrollBy(0, {scroll_px})")
            await asyncio.sleep(1)

            imgs = await pr.query_selector_all(".page img")
            for img in imgs:
                src = await img.get_attribute("src") or ""
                if not src or src in captured_srcs:
                    continue

                try:
                    visible = await img.is_visible()
                    if not visible:
                        continue

                    # Capturar screenshot do elemento
                    shot = await img.screenshot(type="png")
                    kb = len(shot) // 1024
                    if kb < 3:  # imagem em branco ou muito pequena
                        continue

                    captured_srcs.add(src)

                    # Extrair página da URL
                    page_num = 0
                    if "page=" in src:
                        try:
                            page_num = int(src.split("page=")[1].split("&")[0])
                        except ValueError:
                            pass

                    w = await pr.evaluate("el => el.naturalWidth || el.offsetWidth", img)
                    h = await pr.evaluate("el => el.naturalHeight || el.offsetHeight", img)

                    fname = f"page_{page_num:03d}_{w}x{h}.png"
                    (OUTPUT / fname).write_bytes(shot)
                    pages_captured.append({"page": page_num, "w": w, "h": h, "kb": kb, "fname": fname})
                    print(f"    p{page_num}: {w}x{h} {kb}KB → {fname}")

                except Exception as exc:
                    pass

        print(f"\n    Total capturadas: {len(pages_captured)}")

        if not pages_captured:
            # Tentar screenshot de todo o viewport como fallback
            print("    Nenhuma página capturada — usar viewport completo")
            shot = await pr.screenshot(type="png")
            fname = "viewport_fallback.png"
            (OUTPUT / fname).write_bytes(shot)
            pages_captured.append({"page": 0, "w": 1920, "h": 1080, "kb": len(shot)//1024, "fname": fname})

        # ── ANÁLISE COM CLAUDE ─────────────────────────────────────────────────
        print("\n[3] Análise com Claude Vision...")
        client = anthropic.AsyncAnthropic()
        best = None

        for info in sorted(pages_captured, key=lambda x: x["page"]):
            img_bytes = (OUTPUT / info["fname"]).read_bytes()
            if len(img_bytes) < 2000:
                continue

            img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
            msg = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=150,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": img_b64,
                    }},
                    {"type": "text", "text": (
                        "Esta é uma página do Jornal de Angola. "
                        "Tem anúncios de emprego, vagas, licitações, concursos ou classificados? "
                        "Responde apenas: SIM (descreve) ou NAO."
                    )},
                ]}]
            )
            ans = msg.content[0].text.strip()
            has_ads = ans.upper().startswith("SIM")
            print(f"    Pág {info['page']:02d}: {ans[:80]}")

            if has_ads and not best:
                best = (info["fname"], img_bytes, info["page"])

        # ── RESULTADO ──────────────────────────────────────────────────────────
        if best:
            fname, img_bytes, page_num = best
            out = Path("scrapers/tests/output/jda_pressreader_screenshot.png")
            out.write_bytes(img_bytes)
            Path("scrapers/tests/output/jda_pressreader_viewport.png").write_bytes(img_bytes)
            print(f"\nMelhor página com anúncios: p{page_num} ({fname})")
            print(f"Copiada para pipeline: {out}")
        else:
            print("\nNenhuma página com anúncios encontrada.")
            if pages_captured:
                # Usar maior para o pipeline de qualquer forma
                biggest = max(pages_captured, key=lambda x: x["w"] * x["h"])
                img_bytes = (OUTPUT / biggest["fname"]).read_bytes()
                Path("scrapers/tests/output/jda_pressreader_screenshot.png").write_bytes(img_bytes)
                print(f"Usando maior disponível: {biggest['fname']}")

        # Guardar sessão
        storage = await context.storage_state()
        Path("scrapers/sessions/jda_session.json").write_text(
            json.dumps(storage, indent=2), encoding="utf-8"
        )
        await browser.close()


asyncio.run(main())
