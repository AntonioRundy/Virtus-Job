"""Diagnóstico Angular CDK login JDA — dismissar overlay e mapear form."""
import asyncio
from playwright.async_api import async_playwright


async def diagnose_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("=== Carregando pagina de login ===")
        await page.goto(
            "https://jornaldeangola.ao/#/assinantes/login",
            wait_until="networkidle",
            timeout=30000,
        )
        await asyncio.sleep(3)
        print("URL:", page.url)

        # ─── Dismissar qualquer overlay/modal de boas-vindas ────────────────
        print("\n=== Verificar overlays ===")
        overlay = await page.query_selector(".cdk-overlay-backdrop")
        if overlay:
            print("Overlay CDK detectado — tentar fechar com Escape...")
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

            # Ou clicar no botao de fechar se existir
            close_btn = await page.query_selector(
                "button.mat-dialog-close, button[aria-label='Close'], "
                "button:has-text('Fechar'), button:has-text('×'), "
                ".mat-dialog-close, [mat-dialog-close]"
            )
            if close_btn:
                print("Botao fechar encontrado — clicando...")
                await close_btn.click()
                await asyncio.sleep(1)
            else:
                # Clicar no backdrop directamente
                print("Clicar no backdrop para fechar...")
                await page.mouse.click(10, 10)
                await asyncio.sleep(1)

        # ─── Inputs globais ──────────────────────────────────────────────────
        print("\n=== Inputs na pagina ===")
        inputs = await page.query_selector_all("input")
        print(f"Total inputs: {len(inputs)}")
        for i, el in enumerate(inputs):
            t = await el.get_attribute("type")
            n = await el.get_attribute("name")
            id_ = await el.get_attribute("id")
            ph = await el.get_attribute("placeholder")
            vis = await el.is_visible()
            cls = (await el.get_attribute("class") or "")[:60]
            print(f"  [{i}] type={t} name={n} id={id_} placeholder={ph} visible={vis} class={cls}")

        # ─── Inputs dentro do overlay ────────────────────────────────────────
        print("\n=== Inputs dentro do cdk-overlay-container ===")
        overlay_inputs = await page.query_selector_all(
            ".cdk-overlay-container input, mat-dialog-container input, .modal input"
        )
        print(f"Inputs no overlay: {len(overlay_inputs)}")
        for i, el in enumerate(overlay_inputs):
            t = await el.get_attribute("type")
            n = await el.get_attribute("name")
            id_ = await el.get_attribute("id")
            ph = await el.get_attribute("placeholder")
            vis = await el.is_visible()
            cls = (await el.get_attribute("class") or "")[:60]
            print(f"  [{i}] type={t} name={n} id={id_} placeholder={ph} visible={vis} class={cls}")

        # ─── Tentar preencher formulário ─────────────────────────────────────
        print("\n=== Tentar preencher formulario ===")
        email_selectors = [
            "input[type='email']",
            "input[name='email']",
            "input[formcontrolname='email']",
            "input[formcontrolname='username']",
            "#email", "#username",
            "input[placeholder*='email' i]",
            "input[placeholder*='utilizador' i]",
        ]
        email_el = None
        for sel in email_selectors:
            el = await page.query_selector(sel)
            if el:
                vis = await el.is_visible()
                print(f"Email field encontrado com selector: {sel} (visible={vis})")
                email_el = el
                break
        if not email_el:
            print("CAMPO DE EMAIL NAO ENCONTRADO com nenhum selector")

        # ─── Dump HTML do overlay ────────────────────────────────────────────
        print("\n=== HTML do cdk-overlay-container (primeiros 1000 chars) ===")
        overlay_html = await page.eval_on_selector(
            ".cdk-overlay-container",
            "el => el.innerHTML.substring(0, 1000)"
        )
        print(overlay_html if overlay_html else "(overlay vazio)")

        # ─── Buttons ────────────────────────────────────────────────────────
        print("\n=== Buttons ===")
        btns = await page.query_selector_all("button")
        for i, el in enumerate(btns[:15]):
            text = (await el.text_content() or "").strip()[:50]
            t = await el.get_attribute("type")
            cls = (await el.get_attribute("class") or "")[:60]
            vis = await el.is_visible()
            print(f"  [{i}] visible={vis} type={t} text={repr(text)} class={cls}")

        await browser.close()


asyncio.run(diagnose_login())
