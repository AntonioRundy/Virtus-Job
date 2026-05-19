"""
Captura autenticada do PressReader seguindo o fluxo humano real:
  jornaldeangola.ao → Login → Assinaturas → LER O JORNAL → PressReader URL → Screenshot

Guarda:
  - scrapers/tests/output/jda_pressreader_screenshot.png
  - scrapers/tests/output/jda_pressreader_url.txt
  - scrapers/sessions/jda_session.json  (cookies + localStorage actualizados)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_FILE = Path("scrapers/sessions/jda_session.json")

# Garante UTF-8 no Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.environ.setdefault("DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job")


async def capture() -> str | None:
    """Executa o fluxo completo e retorna a URL do PressReader ou None."""
    from playwright.async_api import async_playwright
    from scrapers.config import settings

    email    = settings.JDA_EMAIL
    password = settings.JDA_PASSWORD

    if not email or not password:
        print("ERRO: JDA_EMAIL e JDA_PASSWORD devem estar no .env")
        return None

    print(f"Credenciais: {email[:20]}... / {'*' * len(password)}")

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
        page = await context.new_page()
        pressreader_url = None

        # ── PASSO 1: Navegar e fazer login ────────────────────────────────────
        print("\n[1] Navegar para jornaldeangola.ao...")
        await page.goto(
            "https://jornaldeangola.ao/#/assinantes/login",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(3)
        print(f"    URL: {page.url}")

        # Fechar overlay se existir
        overlay = await page.query_selector(".cdk-overlay-backdrop")
        if overlay:
            print("    Overlay detectado — fechar com Escape...")
            await page.keyboard.press("Escape")
            await asyncio.sleep(1.5)

        # Clicar no botão "Entrar"
        print("[2] Clicar 'Entrar'...")
        entrar = await page.query_selector("button:has-text('Entrar'), button.bg-black")
        if not entrar:
            print("    AVISO: botão Entrar não encontrado — tentar login directo")
        else:
            await entrar.click()
            await asyncio.sleep(2)

        # Preencher email
        email_el = None
        for sel in ["input[formcontrolname='email']", "input[type='email']", "input[name='email']"]:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                email_el = el
                print(f"    Email field: {sel}")
                break

        if not email_el:
            print("    ERRO: campo email não encontrado")
            await browser.close()
            return None

        await email_el.fill(email)

        # Preencher password
        pwd_el = await page.query_selector("input[type='password']")
        if not pwd_el:
            print("    ERRO: campo password não encontrado")
            await browser.close()
            return None
        await pwd_el.fill(password)

        # Submeter
        submit = await page.query_selector("button[type='submit']")
        if submit:
            print("[3] Clicar submit...")
            await submit.click()
        else:
            print("[3] Submit não encontrado — Enter...")
            await pwd_el.press("Enter")

        await asyncio.sleep(4)
        print(f"    URL após login: {page.url}")

        # Verificar login (procurar elementos de utilizador autenticado)
        user_indicators = [
            "[class*='user']", "[class*='logged']", "[class*='subscriber']",
            "a[href*='assinante']", "a[href*='assinatura']",
            "button:has-text('Sair')", "button:has-text('Logout')",
        ]
        authenticated = False
        for sel in user_indicators:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                print(f"    Indicador de login: {sel}")
                authenticated = True
                break

        if not authenticated:
            print("    AVISO: sem indicador claro de login bem-sucedido")

        # ── PASSO 2: Navegar para Assinaturas → LER O JORNAL ─────────────────
        print("\n[4] Procurar 'LER O JORNAL' ou 'Leia o Jornal Digital'...")

        # Tentar clicar no botão "LER O JORNAL"
        ler_selectors = [
            "button:has-text('Leia o Jornal Digital')",
            "a:has-text('Leia o Jornal Digital')",
            "button:has-text('LER O JORNAL')",
            "a:has-text('LER O JORNAL')",
            "button:has-text('Ler')",
        ]
        ler_btn = None
        for sel in ler_selectors:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                ler_btn = el
                print(f"    Encontrado: {sel}")
                break

        if not ler_btn:
            # Tentar navegar para página de assinaturas
            print("    Botão LER não encontrado — tentar /assinaturas...")
            assin_urls = [
                "https://jornaldeangola.ao/#/assinantes",
                "https://jornaldeangola.ao/#/assinatura",
                "https://jornaldeangola.ao/#/assinantes/assinaturas",
            ]
            for url in assin_urls:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                for sel in ler_selectors:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        ler_btn = el
                        print(f"    Encontrado em {url}: {sel}")
                        break
                if ler_btn:
                    break

        if ler_btn:
            print("[5] Clicar 'LER O JORNAL' e capturar URL do PressReader...")
            # Botão pode abrir nova aba — escutar ambos
            async with context.expect_page(timeout=15000) as new_page_info:
                await ler_btn.click()

            try:
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("domcontentloaded", timeout=20000)
                await asyncio.sleep(5)
                pressreader_url = new_page.url
                print(f"    Nova aba aberta: {pressreader_url}")
                page = new_page  # trabalhar na nova aba
            except Exception as e:
                print(f"    Erro nova aba: {e} — usar página actual")
                await asyncio.sleep(4)
                pressreader_url = page.url
                print(f"    URL actual: {pressreader_url}")
        else:
            # Fallback: ir directamente para PressReader com token se existir em localStorage
            print("[5] Fallback — aceder PressReader directamente com sessão...")
            pressreader_url = "https://edicoesnovembro.pressreader.com/jornal-de-angola"

        # ── PASSO 3: Capturar screenshot do PressReader ───────────────────────
        print(f"\n[6] Navegar para PressReader: {pressreader_url}")

        if pressreader_url != page.url:
            await page.goto(pressreader_url, wait_until="domcontentloaded", timeout=45000)

        print("    Aguardar renderização do jornal (15s)...")
        await asyncio.sleep(15)
        print(f"    URL final: {page.url}")
        print(f"    Título: {await page.title()}")

        img_count = await page.evaluate("document.images.length")
        print(f"    Imagens na página: {img_count}")

        # Tentar navegar para as últimas páginas (CLASSIFICADOS / ESPECIAL)
        # PressReader suporta tecla End ou botão de última página
        print("\n[7] Tentar navegar para últimas páginas (classificados)...")
        for attempt in range(3):
            # Tentar clicar no botão de "última página" / "ir para página"
            for sel in [
                "button[title*='last' i]", "button[title*='final' i]",
                "button[aria-label*='last' i]", "button[aria-label*='last page' i]",
                "[class*='last-page']", "[class*='lastPage']",
                "button[data-page-last]",
            ]:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    print(f"    Botão última página: {sel}")
                    await el.click()
                    await asyncio.sleep(3)
                    break
            else:
                # Fallback: pressionar tecla End para ir ao fim
                await page.keyboard.press("End")
                await asyncio.sleep(1)

        # Screenshot das últimas páginas
        screenshot = await page.screenshot(full_page=True, type="png")
        screenshot_kb = len(screenshot) // 1024
        print(f"    Screenshot: {screenshot_kb}KB")

        # Guardar
        screenshot_path = OUTPUT_DIR / "jda_pressreader_screenshot.png"
        screenshot_path.write_bytes(screenshot)
        print(f"    Guardado: {screenshot_path}")

        # Screenshot adicional do viewport (mais legível para AI)
        viewport_shot = await page.screenshot(type="png", clip={"x": 0, "y": 0, "width": 1440, "height": 900})
        viewport_path = OUTPUT_DIR / "jda_pressreader_viewport.png"
        viewport_path.write_bytes(viewport_shot)
        print(f"    Viewport guardado: {viewport_path} ({len(viewport_shot)//1024}KB)")

        # Guardar URL
        url_path = OUTPUT_DIR / "jda_pressreader_url.txt"
        url_path.write_text(pressreader_url, encoding="utf-8")

        # Guardar sessão actualizada
        storage = await context.storage_state()
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps(storage, indent=2), encoding="utf-8")
        print(f"    Sessão guardada: {len(storage.get('cookies', []))} cookies, "
              f"{len(storage.get('origins', []))} origins")

        await browser.close()
        return pressreader_url if screenshot_kb > 50 else None


async def main():
    t0 = time.time()
    print("=" * 60)
    print("JDA → PressReader Screenshot Capture")
    print("=" * 60)

    url = await capture()

    print(f"\nDuração: {time.time()-t0:.1f}s")
    if url:
        print(f"Screenshot guardado em: scrapers/tests/output/jda_pressreader_screenshot.png")
        print("Pode agora executar o pipeline visual com este screenshot.")
    else:
        print("FALHOU: screenshot não capturado ou muito pequeno.")
        print("Verificar: scrapers/tests/output/jda_pressreader_screenshot.png")


asyncio.run(main())
