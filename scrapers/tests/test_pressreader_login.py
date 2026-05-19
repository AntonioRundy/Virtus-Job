"""
JdA → PressReader Correct Authentication Flow

Exact human flow:
  1. Open jornaldeangola.ao
  2. Login with credentials
  3. Click user name "António Rundi Manuel Fernando" (top bar)
  4. Dropdown: click "Assinaturas"
  5. On subscriptions page: click green "Ler o Jornal" button
  6. System redirects to edicoesnovembro.pressreader.com
  7. Already authenticated — no second login needed
  8. Save persistent session

Usage (workspace root):
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_pressreader_login
"""
import asyncio, json, os, sys, time
from pathlib import Path

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SESSION_FILE = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
OUTPUT_DIR   = Path(__file__).parent / "output" / "pressreader_unlocked"
EMAIL        = os.environ.get("JDA_EMAIL", "")
PASSWORD     = os.environ.get("JDA_PASSWORD", "")

JDA_HOME        = "https://jornaldeangola.ao"
JDA_LOGIN       = "https://jornaldeangola.ao/assinantes/login"
JDA_ASSINATURAS = "https://jornaldeangola.ao/area-reservada/assinaturas"
PRESSREADER_URL = "https://edicoesnovembro.pressreader.com/jornal-de-angola"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))

async def snap(page, label: str = "") -> bytes:
    try:
        return await page.screenshot(type="jpeg", quality=85, animations="disabled", timeout=15000)
    except Exception as e:
        p(f"  snap '{label}' error: {e}")
        return b""

def save(data: bytes, name: str):
    if data:
        path = OUTPUT_DIR / name
        path.write_bytes(data)
        p(f"  saved: {name} ({len(data)//1024}KB)")


async def main() -> None:
    from playwright.async_api import async_playwright

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    p("=" * 60)
    p("  JdA → PressReader Correct Authentication Flow")
    p(f"  Email: {EMAIL}")
    p("=" * 60)

    if not EMAIL or not PASSWORD:
        p("ERROR: JDA_EMAIL / JDA_PASSWORD not set in .env")
        sys.exit(1)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=150,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-AO",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        def on_nav(f):
            if f == page.main_frame:
                p(f"  -> {f.url[:90]}")
        page.on("framenavigated", on_nav)

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Open jornaldeangola.ao and login
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 1] Opening jornaldeangola.ao...")
        await page.goto(JDA_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        p(f"  Title: {await page.evaluate('document.title')}")
        save(await snap(page, "home"), "01_home.jpg")

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Login
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 2] Logging in...")

        # Navigate to login page
        await page.goto(JDA_LOGIN, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        p(f"  Login URL: {page.url}")

        # Wait for form
        for i in range(15):
            await asyncio.sleep(1)
            if await page.query_selector("#email"):
                p(f"  Form ready at t={i+1}s")
                break

        # Fill credentials
        await page.click("#email")
        await page.fill("#email", EMAIL)
        await page.evaluate("document.querySelector('#email').dispatchEvent(new Event('blur',{bubbles:true}))")
        await asyncio.sleep(0.3)
        await page.click("#senha")
        await page.fill("#senha", PASSWORD)
        await page.evaluate("document.querySelector('#senha').dispatchEvent(new Event('blur',{bubbles:true}))")
        await asyncio.sleep(0.3)

        p(f"  Credentials filled. Submitting...")
        await page.locator("button").filter(has_text="Entrar").last.click()

        # Wait for redirect after login
        for i in range(30):
            await asyncio.sleep(1)
            if "login" not in page.url.lower():
                p(f"  Login success at t={i+1}s — URL: {page.url}")
                break
            if i % 5 == 4:
                p(f"  t={i+1}s: {page.url[:60]}")

        save(await snap(page, "after_login"), "02_after_login.jpg")
        p(f"  Current URL: {page.url}")

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Click user name in top bar
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 3] Clicking user name in top bar...")
        await asyncio.sleep(2)

        # Look for the authenticated user name
        user_selectors = [
            ".user-name", ".username", "[class*='user-name']",
            "[class*='utilizador']", "[class*='account']",
            ".navbar-user", ".header-user",
        ]
        user_btn = None
        for sel in user_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        p(f"  Found user element: '{text}' via {sel}")
                        user_btn = el
                        break
            except Exception:
                pass

        # Also try finding by text content
        if not user_btn:
            # Look for element containing the user's name
            user_btn = await page.query_selector("text=António")
            if not user_btn:
                user_btn = await page.query_selector("text=Rundy")
            if not user_btn:
                # Try the icon button near logout indicators
                user_btn = await page.query_selector("[class*='perfil'], [class*='avatar'], .user-icon, .account-icon")

        if user_btn:
            text = (await user_btn.inner_text()).strip()
            p(f"  Clicking: '{text}'")
            await user_btn.click()
            await asyncio.sleep(2)
        else:
            p("  User button not found — listing all top bar elements:")
            header_els = await page.eval_on_selector_all(
                "header *, nav *, .navbar *",
                "els => els.filter(e=>e.innerText?.trim()).map(e=>({tag:e.tagName,text:e.innerText.trim().substring(0,30),cls:e.className.substring(0,30)}))"
            )
            for el in header_els[:20]:
                p(f"    {el['tag']:8} '{el['text']:25}' {el['cls']}")
            save(await snap(page, "debug"), "03_debug_header.jpg")

        save(await snap(page, "after_click_user"), "03_after_user_click.jpg")

        # ═══════════════════════════════════════════════════════════════
        # STEP 4-5: Click "Assinaturas" in dropdown
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 4-5] Clicking 'Assinaturas' in dropdown...")
        assinaturas_selectors = [
            "a:has-text('Assinaturas')",
            "button:has-text('Assinaturas')",
            "[href*='assinaturas']",
        ]
        clicked_assinaturas = False
        for sel in assinaturas_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    clicked_assinaturas = True
                    p(f"  Clicked: {sel}")
                    break
            except Exception:
                pass

        if not clicked_assinaturas:
            # Navigate directly to subscriptions page
            p("  Dropdown not visible — navigating directly to assinaturas...")
            await page.goto(JDA_ASSINATURAS, wait_until="domcontentloaded", timeout=20000)

        await asyncio.sleep(4)
        p(f"  URL: {page.url}")
        save(await snap(page, "assinaturas"), "04_assinaturas.jpg")

        # ═══════════════════════════════════════════════════════════════
        # STEP 6: Verify subscription info on page
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 6] Checking subscription page...")
        page_text = await page.evaluate("document.body.innerText")
        has_jornal = "Jornal de Angola" in page_text
        has_plano  = "anual" in page_text.lower() or "plano" in page_text.lower()
        has_dates  = "2026" in page_text or "2027" in page_text
        p(f"  'Jornal de Angola': {has_jornal}")
        p(f"  'plano anual':      {has_plano}")
        p(f"  Dates (2026/2027):  {has_dates}")

        # ═══════════════════════════════════════════════════════════════
        # STEP 7: Click "Ler o Jornal" button
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 7] Looking for 'Ler o Jornal' button...")
        ler_selectors = [
            "button:has-text('Ler o Jornal')",
            "a:has-text('Ler o Jornal')",
            "button:has-text('LER O JORNAL')",
            "a:has-text('LER O JORNAL')",
            "[class*='btn']:has-text('Jornal')",
            "button:has-text('Ler Jornal')",
            ".btn-green", ".btn-success", ".btn-primary:has-text('Jornal')",
        ]

        ler_btn = None
        for sel in ler_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    text = (await el.inner_text()).strip()
                    p(f"  Found: '{text}' via {sel}")
                    ler_btn = el
                    break
            except Exception:
                pass

        if not ler_btn:
            p("  'Ler o Jornal' not found — listing all buttons on page:")
            btns = await page.eval_on_selector_all(
                "button, a[href], input[type='button'], input[type='submit']",
                "els => els.map(e=>({tag:e.tagName,text:(e.innerText||e.value||'').trim().substring(0,40),href:(e.href||''),cls:e.className.substring(0,30)}))"
            )
            for b in btns:
                if b["text"]:
                    p(f"  {b['tag']:8} '{b['text']:40}' {b['href'][:50]}")
            save(await snap(page, "debug_buttons"), "05_debug_buttons.jpg")
            p("  Browser stays open 60s for manual inspection.")
            await asyncio.sleep(60)
            await browser.close()
            sys.exit(1)

        # ═══════════════════════════════════════════════════════════════
        # STEP 8: Click "Ler o Jornal" → opens PressReader (new tab or same)
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 8] Clicking 'Ler o Jornal'...")

        # Listen for new page (new tab)
        async with context.expect_page() as new_page_info:
            await ler_btn.click()
            p("  Clicked — waiting for new tab or navigation...")
            try:
                pr_page = await new_page_info.value
                p(f"  New tab opened!")
            except Exception:
                pr_page = None

        if pr_page:
            # New tab opened
            await pr_page.wait_for_load_state("domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            p(f"  New tab URL: {pr_page.url}")
            save(await snap(pr_page, "pressreader"), "06_pressreader.jpg")
            page = pr_page  # Switch to the PressReader tab
        else:
            # Same tab navigation
            p("  No new tab — checking main page...")
            for i in range(20):
                await asyncio.sleep(1)
                if "pressreader.com" in page.url:
                    p(f"  PressReader in main tab at t={i+1}s")
                    break
                if i % 5 == 4:
                    p(f"  t={i+1}s: {page.url[:70]}")

            if "pressreader.com" not in page.url:
                p("  PressReader not reached — navigating directly with current session...")
                await page.goto(PRESSREADER_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)

            save(await snap(page, "pressreader"), "06_pressreader.jpg")

        p(f"  PressReader URL: {page.url}")

        # ═══════════════════════════════════════════════════════════════
        # STEP 9: Save session and validate
        # ═══════════════════════════════════════════════════════════════
        p(f"\n[STEP 9] Saving session and validating...")

        # Check if content is unlocked
        if "pressreader" in page.url:
            state = await page.evaluate("""
            () => ({
                url: location.href,
                title: document.title,
                has_entrar: document.body.innerText.includes('Assine'),
                body_len: document.body.innerText.length,
                locks: document.querySelectorAll('[class*="lock"]').length,
            })
            """)
            p(f"  locks={state['locks']} subscribe_prompt={state['has_entrar']} text={state['body_len']}")

            # Take screenshots of multiple pages
            p("\n  Taking page screenshots...")
            for pg in range(1, 8):
                shot = await snap(page, f"page_{pg}")
                save(shot, f"page_{pg:02d}.jpg")
                await page.keyboard.press("ArrowRight")
                await asyncio.sleep(2)

        # Save complete session
        final_state = await context.storage_state()
        cookies = final_state.get("cookies", [])
        origins = final_state.get("origins", [])

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(
            json.dumps({"saved_at": time.time(), "storage_state": final_state}, indent=2),
            encoding="utf-8"
        )
        p(f"\n  Cookies ({len(cookies)}):")
        for c in cookies:
            p(f"    {c['domain']:45} | {c['name']}")
        p(f"\n  Origins ({len(origins)}):")
        for o in origins:
            ls = o.get("localStorage", [])
            p(f"    {o['origin']:50} | {len(ls)} items")

        # Check for PressReader auth ticket
        pr_ticket = None
        for o in origins:
            if "pressreader" in o.get("origin", ""):
                for item in o.get("localStorage", []):
                    if "authTicket" in item.get("name", "") or "ticket" in item.get("name", "").lower():
                        pr_ticket = item.get("value", "")[:40]
        p(f"\n  PressReader auth ticket: {'SET: ' + pr_ticket if pr_ticket else 'NOT SET (session may rely on cookies)'}")
        p(f"\n  Session saved → {SESSION_FILE}")

        p(f"\n  Browser closes in 10s.")
        await asyncio.sleep(10)
        await context.close()
        await browser.close()

    shots = sorted(OUTPUT_DIR.glob("*.jpg"))
    p(f"\n{'='*60}")
    p(f"  COMPLETE — {len(shots)} screenshots in {OUTPUT_DIR}")
    for s in shots:
        p(f"  {s.name:45} {s.stat().st_size//1024:5}KB")


if __name__ == "__main__":
    asyncio.run(main())
