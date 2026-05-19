"""
Navegar page-by-page no PressReader com ArrowRight e capturar cada spread de páginas.
Continua até encontrar página com anúncios de emprego OU chegar ao fim do jornal.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import anthropic

OUTPUT = Path(__file__).parent / "output" / "jda_page_nav"
OUTPUT.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job")


async def login_and_open_pressreader(context):
    from scrapers.config import settings

    page = await context.new_page()
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

    em = await page.query_selector("input[formcontrolname='email']")
    pw = await page.query_selector("input[type='password']")
    if em and pw:
        await em.fill(settings.JDA_EMAIL)
        await pw.fill(settings.JDA_PASSWORD)
        await pw.press("Enter")
        await asyncio.sleep(5)

    ler = await page.query_selector("button:has-text('LER O JORNAL')")
    if not ler:
        print("ERRO: LER O JORNAL não encontrado")
        return None

    async with context.expect_page(timeout=15000) as np_info:
        await ler.click()
    pr = await np_info.value
    await pr.wait_for_load_state("domcontentloaded", timeout=20000)
    await asyncio.sleep(20)
    print(f"    PressReader aberto: {pr.url[:60]}")
    return pr


async def capture_current_pages(pr, nav_step: int, captured_srcs: set, output_dir: Path) -> list[dict]:
    """Captura as páginas visíveis no estado actual do reader."""
    pages = []
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
            kb = len(shot) // 1024
            if kb < 10:
                continue

            captured_srcs.add(src)

            page_num = 0
            if "page=" in src:
                try:
                    page_num = int(src.split("page=")[1].split("&")[0])
                except ValueError:
                    pass

            w = await pr.evaluate("el => el.naturalWidth || el.offsetWidth", img)
            h = await pr.evaluate("el => el.naturalHeight || el.offsetHeight", img)

            fname = f"step{nav_step:02d}_page{page_num:03d}_{w}x{h}.png"
            (output_dir / fname).write_bytes(shot)
            pages.append({"page": page_num, "w": w, "h": h, "kb": kb, "fname": fname})

        except Exception:
            pass

    return pages


async def main():
    from playwright.async_api import async_playwright

    print("=== JDA → Navegação Página a Página ===\n")
    client = anthropic.AsyncAnthropic()

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

        print("[1] Login...")
        pr = await login_and_open_pressreader(context)
        if not pr:
            await browser.close()
            return

        captured_srcs: set[str] = set()
        all_pages: list[dict] = []
        best_page: tuple | None = None

        # Capturar estado inicial (páginas 1-5)
        print("\n[2] Capturar estado inicial...")
        initial = await capture_current_pages(pr, 0, captured_srcs, OUTPUT)
        all_pages.extend(initial)
        print(f"    {len(initial)} páginas: {[p['page'] for p in initial]}")

        # Navegar com ArrowRight para chegar às últimas páginas
        print("\n[3] Navegação com ArrowRight...")
        for step in range(1, 16):
            await pr.keyboard.press("ArrowRight")
            await asyncio.sleep(2)

            new_pages = await capture_current_pages(pr, step, captured_srcs, OUTPUT)
            if new_pages:
                all_pages.extend(new_pages)
                nums = [p["page"] for p in new_pages]
                print(f"    Step {step}: páginas {nums}")

                # Analisar imediatamente se tem anúncios
                for info in new_pages:
                    img_bytes = (OUTPUT / info["fname"]).read_bytes()
                    if len(img_bytes) < 5000:
                        continue
                    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
                    msg = await client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=100,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": "image/png", "data": img_b64,
                            }},
                            {"type": "text", "text": (
                                "Tem anúncios de emprego, vagas, licitações, "
                                "concursos ou classificados? SIM (descreve) ou NAO."
                            )},
                        ]}]
                    )
                    ans = msg.content[0].text.strip()
                    has = ans.upper().startswith("SIM")
                    print(f"      p{info['page']:02d}: {ans[:70]}")
                    if has and not best_page:
                        best_page = (info["fname"], img_bytes, info["page"])

                if best_page:
                    print(f"\n    ENCONTRADO! Página {best_page[2]}")
                    break
            else:
                print(f"    Step {step}: sem novas páginas (possível fim do jornal)")

        # ── RESULTADO ──────────────────────────────────────────────────────────
        print(f"\n=== RESULTADO: {len(all_pages)} páginas únicas capturadas ===")
        print("Páginas:", sorted(set(p["page"] for p in all_pages)))

        if best_page:
            fname, img_bytes, page_num = best_page
            out = Path("scrapers/tests/output/jda_pressreader_screenshot.png")
            out.write_bytes(img_bytes)
            Path("scrapers/tests/output/jda_pressreader_viewport.png").write_bytes(img_bytes)
            print(f"\nPágina com anúncios: p{page_num} → {out}")
        else:
            if all_pages:
                last = max(all_pages, key=lambda x: x["page"])
                img_bytes = (OUTPUT / last["fname"]).read_bytes()
                Path("scrapers/tests/output/jda_pressreader_screenshot.png").write_bytes(img_bytes)
                print(f"\nSem anúncios encontrados. Usando última página: p{last['page']}")

        # Guardar sessão
        storage = await context.storage_state()
        Path("scrapers/sessions/jda_session.json").write_text(
            json.dumps(storage, indent=2), encoding="utf-8"
        )
        await browser.close()


asyncio.run(main())
