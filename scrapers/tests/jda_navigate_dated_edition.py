"""
Navegar para edição específica do JDA via URL datada e capturar screenshot de página com anúncios.
Usa cookies da sessão existente.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from datetime import date

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

    session_file = Path("scrapers/sessions/jda_session.json")
    storage = json.loads(session_file.read_text(encoding="utf-8")) if session_file.exists() else {}
    cookies = storage.get("cookies", [])
    print(f"Cookies na sessao: {len(cookies)}")

    today = date.today().strftime("%Y%m%d")
    yesterday = date.fromordinal(date.today().toordinal() - 1).strftime("%Y%m%d")

    # URLs a tentar — edição de hoje e de ontem
    urls_to_try = [
        f"https://edicoesnovembro.pressreader.com/jornal-de-angola/{today}",
        f"https://edicoesnovembro.pressreader.com/jornal-de-angola/{yesterday}",
        "https://edicoesnovembro.pressreader.com/jornal-de-angola",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            storage_state=storage if cookies else None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-AO",
        )
        page = await context.new_page()

        best_screenshot = None
        best_size = 0
        best_url = None

        for url in urls_to_try:
            print(f"\n[TENTAR] {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(12)

                title = await page.title()
                img_count = await page.evaluate("document.images.length")
                final_url = page.url

                # Verificar se há canvas (indica reader com jornal real)
                canvas = await page.query_selector("canvas")
                has_canvas = canvas is not None

                shot = await page.screenshot(type="png")
                kb = len(shot) // 1024
                print(f"  URL final: {final_url[:80]}")
                print(f"  Titulo: {title}")
                print(f"  imgs={img_count} canvas={has_canvas} size={kb}KB")

                shot_name = url.split("/")[-1] or "home"
                (OUTPUT_DIR / f"dated_{shot_name}.png").write_bytes(shot)

                if kb > best_size:
                    best_size = kb
                    best_screenshot = shot
                    best_url = final_url

            except Exception as e:
                print(f"  ERRO: {e}")

        # Guardar melhor screenshot
        if best_screenshot and best_size > 200:
            (OUTPUT_DIR / "jda_pressreader_screenshot.png").write_bytes(best_screenshot)
            (OUTPUT_DIR / "jda_pressreader_viewport.png").write_bytes(best_screenshot)
            print(f"\nMelhor screenshot: {best_size}KB de {best_url}")
        else:
            print(f"\nNenhum screenshot > 200KB. Melhor foi {best_size}KB")

        # Actualizar sessao
        new_storage = await context.storage_state()
        session_file.write_text(json.dumps(new_storage, indent=2), encoding="utf-8")
        print(f"Sessao actualizada: {len(new_storage.get('cookies',[]))} cookies")

        await browser.close()


asyncio.run(main())
