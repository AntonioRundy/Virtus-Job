"""Diagnóstico: clicar 'Entrar' no JDA e mapear o formulário de login."""
import asyncio
from playwright.async_api import async_playwright


async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("=== Navegar para login JDA ===")
        await page.goto(
            "https://edicoesnovembro.pressreader.com/accounting/signin",
            wait_until="networkidle",
            timeout=30000,
        )
        await asyncio.sleep(2)
        print("URL:", page.url)

        # Dismissar overlay inicial se existir
        overlay = await page.query_selector(".cdk-overlay-backdrop")
        if overlay:
            print("Overlay inicial detectado — dismissar com Escape...")
            await page.keyboard.press("Escape")
            await asyncio.sleep(1.5)

        # Verificar se overlay foi removido
        overlay_after = await page.query_selector(".cdk-overlay-backdrop")
        print("Overlay apos Escape:", "presente" if overlay_after else "removido")

        # Clicar no botao Entrar
        print("\n=== Clicar botao Entrar ===")
        entrar_btn = await page.query_selector("button:has-text('Entrar')")
        if not entrar_btn:
            # Tentar pelo texto exacto
            entrar_btn = await page.query_selector("button.bg-black")
        if entrar_btn:
            vis = await entrar_btn.is_visible()
            print(f"Botao Entrar encontrado (visible={vis})")
            await entrar_btn.click()
            print("Clique efectuado — aguardar modal...")
            await asyncio.sleep(3)
        else:
            print("BOTAO ENTRAR NAO ENCONTRADO")

        # Procurar inputs apos abertura do modal
        print("\n=== Inputs apos abrir modal de login ===")
        inputs = await page.query_selector_all("input")
        print(f"Total inputs: {len(inputs)}")
        for i, el in enumerate(inputs):
            t = await el.get_attribute("type")
            n = await el.get_attribute("name")
            id_ = await el.get_attribute("id")
            ph = await el.get_attribute("placeholder")
            fc = await el.get_attribute("formcontrolname")
            vis = await el.is_visible()
            cls = (await el.get_attribute("class") or "")[:80]
            print(f"  [{i}] type={t} name={n} id={id_} formcontrolname={fc} placeholder={ph} visible={vis}")
            print(f"       class={cls}")

        # Overlays activos
        print("\n=== Overlays CDK activos ===")
        overlays = await page.query_selector_all(".cdk-overlay-pane")
        print(f"Total overlay panes: {len(overlays)}")
        for i, el in enumerate(overlays):
            vis = await el.is_visible()
            cls = (await el.get_attribute("class") or "")[:80]
            print(f"  [{i}] visible={vis} class={cls}")

        # HTML do overlay pane (pode conter o form)
        if overlays:
            html = await page.eval_on_selector(
                ".cdk-overlay-pane",
                "el => el.innerHTML.substring(0, 2000)"
            )
            print("\n=== HTML do primeiro overlay-pane ===")
            print(html)

        # Botoes dentro do overlay
        print("\n=== Buttons no overlay ===")
        overlay_btns = await page.query_selector_all(
            ".cdk-overlay-pane button, .cdk-overlay-container button[type=submit]"
        )
        for i, el in enumerate(overlay_btns):
            text = (await el.text_content() or "").strip()[:50]
            t = await el.get_attribute("type")
            vis = await el.is_visible()
            print(f"  [{i}] type={t} visible={vis} text={repr(text)}")

        await browser.close()


asyncio.run(diagnose())
