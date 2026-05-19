"""
JdA Full SSO Authentication via PressReader.

Correct flow:
  1. Start at edicoesnovembro.pressreader.com
  2. Click ENTRAR -> redirects to jornaldeangola.ao login
  3. Fill credentials at jornaldeangola.ao
  4. JdA redirects BACK to PressReader with SSO token
  5. PressReader creates its own session
  6. Save combined state (JdA + PressReader cookies/localStorage)

This is the only flow that gives access to the PressReader content.
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

def p(*args):
    try:
        print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii", errors="replace").decode("ascii"))


async def full_sso_auth() -> None:
    from playwright.async_api import async_playwright

    email        = os.environ.get("JDA_EMAIL", "")
    password     = os.environ.get("JDA_PASSWORD", "")
    session_file = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
    portal_url   = "https://edicoesnovembro.pressreader.com/jornal-de-angola"

    if not email or not password:
        p("ERROR: JDA_EMAIL / JDA_PASSWORD not set.")
        sys.exit(1)

    p("=" * 60)
    p("  JdA Full SSO Authentication")
    p(f"  Start: {portal_url}")
    p(f"  Email: {email}")
    p("=" * 60)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False, slow_mo=200,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-AO", viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        # Track all navigations
        def on_nav(url):
            p(f"  -> {url[:80]}")
        page.on("framenavigated", lambda frame: on_nav(frame.url) if frame == page.main_frame else None)

        # ─── Step 1: PressReader portal ───────────────────────────────────────
        p(f"\n[1] Opening PressReader portal...")
        try:
            await page.goto(portal_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            p(f"  Warning: {e}")
        await asyncio.sleep(3)
        p(f"  URL  : {page.url}")
        p(f"  Title: {await page.evaluate('document.title')}")

        # ─── Step 2: Click ENTRAR on PressReader ──────────────────────────────
        p(f"\n[2] Clicking ENTRAR on PressReader portal...")
        entrar_selectors = [
            "a:has-text('Entrar')",
            "a[href*='signin']",
            "a[href*='login']",
            "a[href*='accounting']",
        ]
        clicked = False
        for sel in entrar_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    href = await btn.get_attribute("href") or ""
                    text = (await btn.inner_text()).strip()
                    p(f"  Clicking: '{text}' -> {href}")
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            p("  ENTRAR not found — navigating to accounting/signin directly")
            await page.goto("https://edicoesnovembro.pressreader.com/accounting/signin",
                           wait_until="domcontentloaded", timeout=20000)

        await asyncio.sleep(4)
        p(f"  After click URL: {page.url}")

        # Should now be on jornaldeangola.ao login
        if "jornaldeangola" not in page.url:
            p(f"  Unexpected URL — checking for redirect...")
            await asyncio.sleep(3)

        # ─── Step 3: Fill credentials at JdA ─────────────────────────────────
        p(f"\n[3] Filling credentials at JdA login...")
        p(f"  Login URL: {page.url}")

        # Wait for Angular to bootstrap and render the form
        p("  Waiting for Angular form (#email)...")
        try:
            await page.wait_for_selector("#email", timeout=20000)
        except Exception:
            await asyncio.sleep(5)

        p(f"  Form ready at: {page.url}")

        # Fill email
        await page.click("#email")
        await asyncio.sleep(0.2)
        await page.fill("#email", email)
        await page.evaluate("document.querySelector('#email').dispatchEvent(new Event('blur', {bubbles:true}))")
        await asyncio.sleep(0.3)

        # Fill password
        await page.click("#senha")
        await asyncio.sleep(0.2)
        await page.fill("#senha", password)
        await page.evaluate("document.querySelector('#senha').dispatchEvent(new Event('blur', {bubbles:true}))")
        await asyncio.sleep(0.3)

        email_val = await page.evaluate("document.querySelector('#email')?.value")
        pwd_len   = len(await page.evaluate("document.querySelector('#senha')?.value || ''"))
        p(f"  email={email_val}  pwd_len={pwd_len}")

        # Submit
        await page.locator("button").filter(has_text="Entrar").last.click()
        p(f"  Submitted.")

        # Wait for redirect back to PressReader
        p(f"\n[4] Waiting for SSO redirect back to PressReader...")
        for i in range(20):
            await asyncio.sleep(2)
            current = page.url
            p(f"  [{i*2}s] {current[:80]}")
            if "pressreader.com" in current and "signin" not in current and "login" not in current:
                p(f"  PressReader session established!")
                break
            if "assinaturas" in current or "reservada" in current:
                p(f"  JdA subscriber area — may need to navigate to reader from here")
                # Look for and click the reader link
                reader_link = await page.query_selector("a[href*='edicoesnovembro'], a[href*='pressreader'], a[href*='ja.edicoes']")
                if reader_link:
                    href = await reader_link.get_attribute("href")
                    p(f"  Found reader link: {href}")
                    # Try to open pressreader directly
                    await page.goto("https://edicoesnovembro.pressreader.com/jornal-de-angola",
                                   wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(3)
                    break

        final_url = page.url
        final_title = await page.evaluate("document.title")
        p(f"\n[5] Final state:")
        p(f"  URL  : {final_url}")
        p(f"  Title: {final_title}")

        # Save combined session
        storage_state = await context.storage_state()
        cookies = storage_state.get("cookies", [])
        origins = storage_state.get("origins", [])

        p(f"\n  Cookies ({len(cookies)}):")
        for c in cookies:
            p(f"    {c['domain']:40} | {c['name']}")

        p(f"\n  Origins ({len(origins)}):")
        for o in origins:
            ls = o.get("localStorage", [])
            p(f"    {o['origin']:50} | {len(ls)} localStorage items")

        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(
            json.dumps({"saved_at": time.time(), "storage_state": storage_state}, indent=2),
            encoding="utf-8"
        )
        p(f"\n  Session saved: {len(cookies)} cookies, {len(origins)} origins -> {session_file}")

        # Check if PressReader is accessible
        has_pressreader = any("pressreader.com" in c.get("domain", "") for c in cookies)
        has_jda = any("jornaldeangola" in o.get("origin", "") for o in origins)

        p(f"\n  JdA localStorage: {'YES' if has_jda else 'NO'}")
        p(f"  PressReader cookies: {'YES' if has_pressreader else 'NO'}")

        if not has_pressreader:
            p("\n  NOTE: No PressReader cookies saved.")
            p("  The newspaper reader at edicoesnovembro.pressreader.com")
            p("  may still require separate PressReader authentication.")

        p("\n  Browser closes in 15s.")
        await asyncio.sleep(15)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(full_sso_auth())
