"""
Navegar para as últimas páginas do Jornal de Angola (onde ficam os classificados)
e capturar screenshots de cada página para análise visual.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output" / "jda_pages"
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

    print("=== JDA → Navegar para Classificados ===\n")

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
        main_page = await context.new_page()

        # ── Login ─────────────────────────────────────────────────────────────
        print("[1] Login...")
        await main_page.goto("https://jornaldeangola.ao/#/assinantes/login",
                              wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        overlay = await main_page.query_selector(".cdk-overlay-backdrop")
        if overlay:
            await main_page.keyboard.press("Escape")
            await asyncio.sleep(1.5)
        entrar = await main_page.query_selector("button:has-text('Entrar'), button.bg-black")
        if entrar:
            await entrar.click()
            await asyncio.sleep(2)
        email_el = await main_page.query_selector("input[formcontrolname='email']")
        pwd_el = await main_page.query_selector("input[type='password']")
        if email_el and pwd_el:
            await email_el.fill(settings.JDA_EMAIL)
            await pwd_el.fill(settings.JDA_PASSWORD)
            await pwd_el.press("Enter")
            await asyncio.sleep(4)
        print(f"    URL: {main_page.url}")

        # ── LER O JORNAL ──────────────────────────────────────────────────────
        print("[2] LER O JORNAL...")
        ler = await main_page.query_selector("button:has-text('LER O JORNAL')")
        if not ler:
            print("    ERRO: botao nao encontrado")
            await browser.close()
            return

        async with context.expect_page(timeout=15000) as new_page_info:
            await ler.click()
        pr = await new_page_info.value
        await pr.wait_for_load_state("domcontentloaded", timeout=20000)
        await asyncio.sleep(15)
        token_url = pr.url
        print(f"    PressReader URL: {token_url[:100]}")

        # Screenshot da grade inicial
        shot0 = await pr.screenshot(type="png")
        (OUTPUT_DIR / "page_00_grid.png").write_bytes(shot0)
        print(f"    Grade: page_00_grid.png ({len(shot0)//1024}KB)")

        # ── EXPLORAR O DOM DO PRESSREADER ─────────────────────────────────────
        print("\n[3] Explorar DOM...")

        # Classes de elementos interactivos
        clickable_info = await pr.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll(
                    'a, button, [role="button"], [onclick], [class*="page"], [class*="thumb"]'
                ));
                return els.slice(0, 20).map(el => ({
                    tag: el.tagName,
                    cls: (el.className || '').slice(0, 60),
                    text: (el.textContent || '').trim().slice(0, 30),
                    href: el.getAttribute('href') || '',
                    visible: el.offsetParent !== null,
                    w: el.offsetWidth,
                    h: el.offsetHeight
                }));
            }
        """)
        print("    Elementos clicaveis:")
        for el in clickable_info:
            if el['visible'] and el['w'] > 5 and el['h'] > 5:
                print(f"      {el['tag']} ({el['w']}x{el['h']}) text={repr(el['text'][:25])} cls={el['cls'][:40]} href={el['href'][:40]}")

        # Contar imgs com dimensões
        img_info = await pr.evaluate("""
            () => Array.from(document.querySelectorAll('img')).map(img => ({
                src: (img.src || '').slice(0, 80),
                w: img.naturalWidth || img.offsetWidth,
                h: img.naturalHeight || img.offsetHeight,
                visible: img.offsetParent !== null
            }))
        """)
        print(f"\n    Imagens ({len(img_info)}):")
        for i, img in enumerate(img_info):
            if img['visible'] and img['w'] > 50:
                print(f"      [{i}] {img['w']}x{img['h']} src={img['src'][:70]}")

        # ── TENTAR CLICAR EM PÁGINA ESPECÍFICA ────────────────────────────────
        print("\n[4] Tentar abrir página do jornal...")

        # Clicar na maior imagem (provavelmente a capa/pagina)
        clicked = False
        for img_data in sorted(img_info, key=lambda x: x['w'] * x['h'], reverse=True)[:3]:
            if img_data['w'] > 100 and img_data['visible']:
                src = img_data['src']
                print(f"    Clicar imagem maior: {src[:60]}")
                # Encontrar o elemento pelo src
                el = await pr.query_selector(f"img[src='{src}']")
                if el:
                    await el.click()
                    await asyncio.sleep(8)
                    shot = await pr.screenshot(type="png")
                    (OUTPUT_DIR / "page_01_after_click.png").write_bytes(shot)
                    print(f"    Apos click: {len(shot)//1024}KB | URL: {pr.url[:80]}")
                    clicked = True
                    break

        # ── NAVEGAR COM TECLADO ────────────────────────────────────────────────
        print("\n[5] Navegar com teclas para ultimas paginas...")

        # Estratégias de navegação
        for strategy_name, keys in [
            ("PageDown x5", ["PageDown"] * 5),
            ("ArrowRight x10", ["ArrowRight"] * 10),
            ("End", ["End"]),
        ]:
            for key in keys:
                await pr.keyboard.press(key)
                await asyncio.sleep(0.5)

            await asyncio.sleep(4)
            shot = await pr.screenshot(type="png")
            fname = f"page_{strategy_name.replace(' ', '_').replace('x', '').replace('/', '')}.png"
            (OUTPUT_DIR / fname).write_bytes(shot)
            print(f"    {strategy_name}: {len(shot)//1024}KB → {fname}")

        # ── RESUMO ─────────────────────────────────────────────────────────────
        print("\n=== Screenshots capturados ===")
        for f in sorted(OUTPUT_DIR.iterdir()):
            if f.suffix == '.png':
                print(f"  {f.name}: {f.stat().st_size//1024}KB")

        # Guardar sessão
        storage = await context.storage_state()
        Path("scrapers/sessions/jda_session.json").write_text(
            json.dumps(storage, indent=2), encoding="utf-8"
        )

        await browser.close()


asyncio.run(main())
