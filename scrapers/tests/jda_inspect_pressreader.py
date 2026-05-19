"""
Abre PressReader com SSO e captura screenshot da página real do jornal.
Estratégia: login → LER O JORNAL → clicar edição → navegar para últimas páginas → screenshot.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job")


async def main():
    from playwright.async_api import async_playwright
    from scrapers.config import settings

    print("=== JDA PressReader — Captura Página Real ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
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
        page = await context.new_page()

        # ─── LOGIN ──────────────────────────────────────────────────────────
        print("[1] Login em jornaldeangola.ao...")
        await page.goto("https://jornaldeangola.ao/#/assinantes/login",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        overlay = await page.query_selector(".cdk-overlay-backdrop")
        if overlay:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1.5)

        entrar = await page.query_selector("button:has-text('Entrar'), button.bg-black")
        if entrar:
            await entrar.click()
            await asyncio.sleep(2)

        email_el = await page.query_selector("input[formcontrolname='email']")
        pwd_el = await page.query_selector("input[type='password']")
        if email_el and pwd_el:
            await email_el.fill(settings.JDA_EMAIL)
            await pwd_el.fill(settings.JDA_PASSWORD)
            await pwd_el.press("Enter")
            await asyncio.sleep(5)
            print(f"    URL pos login: {page.url}")
        else:
            print("    ERRO: campos de login nao encontrados")
            await browser.close()
            return

        # ─── LER O JORNAL ───────────────────────────────────────────────────
        print("[2] Clicar LER O JORNAL...")
        ler = await page.query_selector("button:has-text('LER O JORNAL')")
        if not ler:
            print("    ERRO: botao LER O JORNAL nao encontrado")
            shot = await page.screenshot(type="png")
            (OUTPUT_DIR / "debug_no_ler_button.png").write_bytes(shot)
            print(f"    Debug screenshot: debug_no_ler_button.png ({len(shot)//1024}KB)")
            await browser.close()
            return

        async with context.expect_page(timeout=15000) as new_page_info:
            await ler.click()

        pr_page = await new_page_info.value
        await pr_page.wait_for_load_state("domcontentloaded", timeout=20000)
        await asyncio.sleep(10)
        print(f"    PressReader URL: {pr_page.url[:80]}")

        # Screenshot inicial (grade de edições)
        shot_grid = await pr_page.screenshot(type="png")
        (OUTPUT_DIR / "pr_01_grid.png").write_bytes(shot_grid)
        print(f"    Grid screenshot: pr_01_grid.png ({len(shot_grid)//1024}KB)")

        # ─── CLICAR NA EDICAO MAIS RECENTE ──────────────────────────────────
        print("[3] Abrir edicao mais recente...")

        # Estratégias para clicar na primeira edição visível
        edition_clicked = False
        for sel in [
            "a[href*='/jornal-de-angola/20']",
            "a[href*='jornal-de-angola/2026']",
            "[class*='issue'] a", "[class*='Issue'] a",
            ".cover", ".cover a",
            "[class*='publication'] a",
            "article a",
        ]:
            els = await pr_page.query_selector_all(sel)
            for el in els:
                href = await el.get_attribute("href") or ""
                visible = await el.is_visible()
                if visible:
                    print(f"    Click: {sel} href={href[:60]}")
                    await el.click()
                    await asyncio.sleep(12)
                    edition_clicked = True
                    break
            if edition_clicked:
                break

        if not edition_clicked:
            print("    Edição não clicada — tentar clicar na primeira imagem grande...")
            imgs = await pr_page.query_selector_all("img")
            for img in imgs[:10]:
                w = await pr_page.evaluate("el => el.offsetWidth", img)
                h = await pr_page.evaluate("el => el.offsetHeight", img)
                src = await img.get_attribute("src") or ""
                visible = await img.is_visible()
                print(f"      img {w}x{h} visible={visible} src={src[:50]}")
                if w > 100 and h > 100 and visible:
                    await img.click()
                    await asyncio.sleep(12)
                    edition_clicked = True
                    break

        print(f"    URL apos click: {pr_page.url[:80]}")
        shot_reader = await pr_page.screenshot(type="png")
        (OUTPUT_DIR / "pr_02_reader.png").write_bytes(shot_reader)
        print(f"    Reader screenshot: pr_02_reader.png ({len(shot_reader)//1024}KB)")

        # ─── NAVEGAR PARA ÚLTIMAS PÁGINAS ───────────────────────────────────
        print("[4] Navegar para ultimas paginas (classificados)...")
        await asyncio.sleep(3)

        # Tentar End key ou botão de última página
        for _ in range(5):
            await pr_page.keyboard.press("ArrowRight")
            await asyncio.sleep(1)

        await asyncio.sleep(5)
        shot_last = await pr_page.screenshot(type="png")
        (OUTPUT_DIR / "pr_03_last_pages.png").write_bytes(shot_last)
        print(f"    Last pages screenshot: pr_03_last_pages.png ({len(shot_last)//1024}KB)")

        # ─── GUARDAR SESSAO E SCREENSHOT FINAL ──────────────────────────────
        import json
        storage = await context.storage_state()
        Path("scrapers/sessions/jda_session.json").write_text(
            json.dumps(storage, indent=2), encoding="utf-8"
        )
        print(f"\n    Sessão: {len(storage.get('cookies',[]))} cookies, {len(storage.get('origins',[]))} origins")

        # Screenshot final para o pipeline
        shot_final = await pr_page.screenshot(type="png")
        (OUTPUT_DIR / "jda_pressreader_viewport.png").write_bytes(shot_final)
        (OUTPUT_DIR / "jda_pressreader_screenshot.png").write_bytes(shot_final)
        print(f"    Screenshot final guardado: {len(shot_final)//1024}KB")

        await browser.close()

    print("\nFeito. Verificar:")
    for name in ["pr_01_grid.png", "pr_02_reader.png", "pr_03_last_pages.png"]:
        p = OUTPUT_DIR / name
        if p.exists():
            print(f"  {name}: {p.stat().st_size//1024}KB")


asyncio.run(main())
