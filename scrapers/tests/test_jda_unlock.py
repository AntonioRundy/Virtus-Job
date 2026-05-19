"""
JdA PressReader — Premium Unlock Flow.

Correct flow (matching human behaviour):
  1. Open specific edition in PressReader reader
  2. Click "Entrar" INSIDE the reader (top-right or sidebar)
  3. Complete JdA login — PressReader sends callback URL
  4. Redirect BACK to PressReader with auth token
  5. Content unlocks (padlocks disappear)
  6. Save final session
  7. Take clean screenshots to prove unlock

Usage (workspace root):
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_jda_unlock
"""
from __future__ import annotations
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
OUTPUT_DIR   = Path(__file__).parent / "output" / "unlocked"
EDITION_URL  = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))

def save(path: Path, data: bytes):
    if data:
        path.write_bytes(data)
        p(f"  saved: {path.name} ({len(data)//1024}KB)")

async def snap(page, label: str = "") -> bytes:
    """Screenshot with animations disabled to avoid font-loading timeout."""
    for attempt in range(3):
        try:
            return await page.screenshot(
                type="jpeg", quality=80,
                animations="disabled",
                timeout=15000,
            )
        except Exception as e:
            if attempt == 2:
                p(f"  Screenshot '{label}' failed: {e}")
                return b""
            await asyncio.sleep(2)
    return b""

async def is_unlocked(page) -> bool:
    """Check if premium content is unlocked (no padlocks visible)."""
    result = await page.evaluate("""
    () => {
        // Count lock/paywall indicators
        const locks = document.querySelectorAll(
            '[class*="lock"], [class*="paywall"], [class*="premium-overlay"]'
        );
        // Count actual article images (real content)
        const articleImgs = document.querySelectorAll(
            'img[src*="image"], img[src*="article"], img[src*="page"], img[src*="issue"]'
        );
        const body_text = document.body.innerText;
        const has_subscribe = body_text.includes('Assine') || body_text.includes('ASSINANTE');
        return {
            locks: locks.length,
            article_images: articleImgs.length,
            has_subscribe_prompt: has_subscribe,
            body_text_len: body_text.length
        };
    }
    """)
    p(f"    locks={result['locks']} article_imgs={result['article_images']} "
      f"subscribe_prompt={result['has_subscribe_prompt']} text={result['body_text_len']}")
    # Unlocked = no subscribe prompt + has article content
    return not result["has_subscribe_prompt"] and result["body_text_len"] > 1000


async def run_unlock() -> None:
    from playwright.async_api import async_playwright

    p("=" * 65)
    p("  JdA PressReader — Premium Unlock")
    p(f"  Edition: {EDITION_URL}")
    p("=" * 65)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SESSION_FILE.exists():
        p("ERROR: No session. Run test_jda_auth.py first.")
        sys.exit(1)

    session_data = json.loads(SESSION_FILE.read_text())
    storage      = session_data.get("storage_state", session_data)
    age_h        = (time.time() - session_data.get("saved_at", 0)) / 3600
    p(f"  Session: {age_h:.1f}h old | "
      f"cookies={len(storage.get('cookies',[]))} "
      f"origins={len(storage.get('origins',[]))}")

    email    = os.environ.get("JDA_EMAIL", "")
    password = os.environ.get("JDA_PASSWORD", "")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=150,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=storage,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-AO",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        # Track ALL navigations with full URL
        nav_log = []
        def on_nav(frame):
            if frame == page.main_frame:
                url = frame.url
                nav_log.append(url)
                p(f"  -> {url[:100]}")
        page.on("framenavigated", on_nav)

        # Intercept requests to capture SSO tokens
        sso_data = {}
        async def on_request(req):
            url = req.url
            if any(x in url for x in ["returnUrl", "callback", "token", "sso", "oauth", "redirect"]):
                p(f"  [REQ] {req.method} {url[:100]}")

        # ─── Step 0: Clear both JdA JWT and PressReader authTicket ──────────────
        p(f"\n[0] Clearing session state to force full SSO flow...")

        # 0a. Clear JdA JWT so Angular shows the login form
        await page.goto("https://jornaldeangola.ao", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        tokens_before = await page.evaluate("""
        () => {
            const keys = ['_token_accesso','utilizadorSessao','perfilCliente'];
            const vals = {};
            keys.forEach(k => vals[k] = !!localStorage.getItem(k));
            keys.forEach(k => localStorage.removeItem(k));
            return vals;
        }
        """)
        p(f"  JdA tokens cleared: {tokens_before}")

        # 0b. Clear PressReader authTickets so PressReader requests fresh SSO
        await page.goto("https://edicoesnovembro.pressreader.com", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        pr_before = await page.evaluate("""
        () => {
            const ticket = localStorage.getItem('pr_/authTickets');
            localStorage.removeItem('pr_/authTickets');
            return !!ticket;
        }
        """)
        p(f"  PressReader authTickets cleared: {pr_before}")
        p(f"  Both caches cleared — SSO flow will generate fresh subscriber ticket")

        # ─── Step 1: Open the edition ─────────────────────────────────────────
        p(f"\n[1] Opening edition...")
        try:
            await page.goto(EDITION_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            p(f"  Warning: {e}")
        await asyncio.sleep(4)
        p(f"  URL  : {page.url}")
        p(f"  Title: {await page.evaluate('document.title')}")

        shot = await snap(page, "edition_loaded")
        save(OUTPUT_DIR / "01_edition_loaded.jpg", shot)

        # ─── Step 2: Find and click "Entrar" INSIDE the reader ────────────────
        p(f"\n[2] Finding 'Entrar' button inside PressReader reader...")

        # The Entrar button can be in several places:
        entrar_selectors = [
            # Top bar Entrar
            "button:has-text('Entrar')",
            "a:has-text('Entrar')",
            # Sidebar panel Entrar (the one we saw in the screenshot)
            ".sign-in-button",
            "[class*='login']",
            "[class*='signin']",
            "[data-action='login']",
            "[data-action='signin']",
        ]

        entrar_btn = None
        entrar_text = ""
        for sel in entrar_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    text = (await btn.inner_text()).strip()
                    href = await btn.get_attribute("href") or ""
                    p(f"  Found: [{sel}] text='{text}' href='{href[:60]}'")
                    entrar_btn = btn
                    entrar_text = text
                    break
            except Exception:
                pass

        if not entrar_btn:
            p("  'Entrar' not found with selectors — listing ALL buttons:")
            btns = await page.eval_on_selector_all(
                "button, a",
                "els => els.filter(e => e.innerText?.trim()).map(e => ({tag:e.tagName, text:e.innerText.trim().substring(0,30), href:(e.href||'')}))"
            )
            for b in btns[:20]:
                p(f"    {b['tag']:6} '{b['text']:30}' {b['href'][:50]}")
            # Try the user icon at top right (often triggers login in PressReader)
            entrar_btn = await page.query_selector("[class*='user-icon'], [class*='account'], [class*='profile']")
            if entrar_btn:
                p("  Using account/user icon instead.")

        if not entrar_btn:
            p("  Could not find login button. Browser open 90s for manual click.")
            await asyncio.sleep(90)
        else:
            p(f"\n  Clicking '{entrar_text or 'Entrar'}'...")
            await entrar_btn.click()
            await asyncio.sleep(3)

        p(f"  After click URL: {page.url}")
        # Skip intermediate screenshot (Angular fonts cause timeout)
        p(f"  Skipping screenshot during Angular font load")

        # ─── Step 3: Complete JdA login if redirected ─────────────────────────
        current_url = page.url
        if "jornaldeangola" in current_url:
            p(f"\n[3] On JdA — dismissing popups and waiting for login form...")

            # Dismiss any advertising popup that blocks the form
            for popup_sel in ["button.close", ".popup-close", "[class*='close']",
                              "button[aria-label*='close' i]", "button[aria-label*='fechar' i]",
                              ".modal-close", ".ad-close", "button.x-btn"]:
                try:
                    btn = await page.query_selector(popup_sel)
                    if btn:
                        await btn.click()
                        p(f"  Dismissed popup: {popup_sel}")
                        await asyncio.sleep(0.5)
                        break
                except Exception:
                    pass

            # Press Escape to dismiss any modal
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

            # Wait for login form (Angular route #/assinantes/login should render it)
            form_found = False
            for i in range(25):
                await asyncio.sleep(1)
                cur = page.url
                # Check if auto-redirect happened (JWT still present somehow)
                if "/area-reservada/" in cur:
                    p(f"  Auto-login detected at t={i+1}s — JWT somehow still present")
                    break
                # Check if login form rendered
                el = await page.query_selector("#email")
                if el:
                    form_found = True
                    p(f"  Login form ready at t={i+1}s")
                    break
                if i % 5 == 4:
                    text_len = await page.evaluate("document.body.innerText.length")
                    p(f"  t={i+1}s | url={cur[:50]} | text={text_len}")

            if form_found:
                p("  Filling login form...")
                await page.click("#email")
                await asyncio.sleep(0.2)
                await page.fill("#email", email)
                await page.evaluate("document.querySelector('#email').dispatchEvent(new Event('blur',{bubbles:true}))")
                await page.click("#senha")
                await asyncio.sleep(0.2)
                await page.fill("#senha", password)
                await page.evaluate("document.querySelector('#senha').dispatchEvent(new Event('blur',{bubbles:true}))")

                email_val = await page.evaluate("document.querySelector('#email')?.value")
                pwd_val   = await page.evaluate("document.querySelector('#senha')?.value || ''")
                p(f"  Filled: email={email_val} pwd_len={len(pwd_val)}")

                await page.locator("button").filter(has_text="Entrar").last.click()
                p("  Submitted — waiting for PressReader redirect back...")

                for i in range(35):
                    await asyncio.sleep(1)
                    cur = page.url
                    if "pressreader.com" in cur and "signin" not in cur:
                        p(f"  Redirected to PressReader at t={i+1}s: {cur[:80]}")
                        break
                    if "/area-reservada/" in cur:
                        p(f"  JdA subscriber area at t={i+1}s — no PressReader callback")
                        p(f"  Manually navigating to PressReader...")
                        await page.goto(EDITION_URL, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(5)
                        break
                    if i % 5 == 4:
                        p(f"  t={i+1}s: {cur[:60]}")
            else:
                p(f"  Login form not found after 25s — trying JdA nav ENTRAR button...")
                # The login MODAL opens when clicking the navigation "ENTRAR" button
                # The hash route just loads the homepage; ENTRAR opens the modal
                jda_entrar_selectors = [
                    "a:has-text('ENTRAR')",
                    "a:has-text('Entrar')",
                    "button:has-text('ENTRAR')",
                    "[class*='entrar']",
                    "[class*='login-btn']",
                    "[class*='auth']",
                ]
                modal_triggered = False
                for sel in jda_entrar_selectors:
                    try:
                        btns = await page.query_selector_all(sel)
                        for btn in btns:
                            try:
                                visible = await btn.is_visible()
                                if visible:
                                    text_val = (await btn.inner_text()).strip()
                                    p(f"  Clicking JdA btn: '{text_val}' ({sel})")
                                    await btn.click()
                                    await asyncio.sleep(2)
                                    # Check if modal appeared
                                    email_el = await page.query_selector("#email")
                                    if email_el:
                                        modal_triggered = True
                                        p(f"  Modal opened! Login form visible.")
                                        break
                            except Exception:
                                pass
                        if modal_triggered:
                            break
                    except Exception:
                        pass

                if modal_triggered:
                    await page.fill("#email", email)
                    await page.evaluate("document.querySelector('#email').dispatchEvent(new Event('blur',{bubbles:true}))")
                    await page.fill("#senha", password)
                    await page.evaluate("document.querySelector('#senha').dispatchEvent(new Event('blur',{bubbles:true}))")
                    await page.locator("button").filter(has_text="Entrar").last.click()
                    p("  Modal login submitted — waiting for PressReader redirect...")
                    for i in range(30):
                        await asyncio.sleep(1)
                        cur = page.url
                        if "pressreader.com" in cur:
                            p(f"  PressReader at t={i+1}s: {cur[:60]}")
                            break
                        if i % 5 == 4:
                            p(f"  t={i+1}s: {cur[:60]}")
                else:
                    p(f"  No modal found — navigating directly to PressReader")
                    await page.goto(EDITION_URL, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(5)
        else:
            p(f"\n[3] No JdA redirect — PressReader may use existing session.")

        # ─── Step 4: Wait for content to unlock ───────────────────────────────
        p(f"\n[4] Waiting for content to unlock...")
        await asyncio.sleep(5)

        # Navigate back to edition if needed
        if page.url != EDITION_URL and "20260517" not in page.url:
            p(f"  Re-navigating to edition...")
            await page.goto(EDITION_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)

        p(f"  URL  : {page.url}")
        p(f"  Title: {await page.evaluate('document.title')}")

        shot3 = await snap(page, "after_login")
        save(OUTPUT_DIR / "03_after_login.jpg", shot3)

        # Check unlock status
        unlocked = await is_unlocked(page)
        p(f"  Content unlocked: {unlocked}")

        if not unlocked:
            p("  Trying interactions to trigger unlock...")
            # Sometimes need to reload or interact after login
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(5)
            unlocked = await is_unlocked(page)
            p(f"  After reload, unlocked: {unlocked}")

        shot4 = await snap(page, "content_state")
        save(OUTPUT_DIR / "04_content_state.jpg", shot4)

        # ─── Step 5: Save final session ───────────────────────────────────────
        p(f"\n[5] Saving final session...")
        final_state = await context.storage_state()
        final_cookies = final_state.get("cookies", [])
        final_origins = final_state.get("origins", [])
        p(f"  Cookies ({len(final_cookies)}):")
        for c in final_cookies:
            p(f"    {c['domain']:45} | {c['name']}")
        p(f"  Origins ({len(final_origins)}):")
        for o in final_origins:
            ls = o.get("localStorage", [])
            p(f"    {o['origin']:50} | {len(ls)} localStorage items")

        SESSION_FILE.write_text(
            json.dumps({"saved_at": time.time(), "storage_state": final_state}, indent=2),
            encoding="utf-8"
        )
        p(f"  Session updated: {SESSION_FILE}")

        # ─── Step 6: Screenshot edition sections ──────────────────────────────
        p(f"\n[6] Taking screenshots of newspaper sections...")

        # Navigate to ESPECIAL (classifieds/announcements) — where concursos are
        sections = [
            ("PRIMEIRA_PAGINA", 1),
            ("ESPECIAL",       10),  # classifieds/announcements — most likely to have concursos
            ("SOCIEDADE",       6),
            ("ECONOMIA",        4),
        ]

        for sec_name, _ in sections:
            # Try clicking the section tab
            try:
                btn = await page.query_selector(f"[class*='section']:has-text('{sec_name.replace('_',' ')}')")
                if not btn:
                    # Try number-based tab click
                    pass
            except Exception:
                pass

        # Just take screenshots of current state page by page
        for pg in range(1, 6):
            shot_pg = await snap(page, f"page_{pg}")
            save(OUTPUT_DIR / f"page_{pg:02d}.jpg", shot_pg)
            await page.keyboard.press("ArrowRight")
            await asyncio.sleep(2)

        # Navigate to ESPECIAL section specifically
        p("\n  Navigating to ESPECIAL section...")
        try:
            especial = await page.query_selector("text=ESPECIAL")
            if especial:
                await especial.click()
                await asyncio.sleep(3)
                shot_esp = await snap(page, "ESPECIAL")
                save(OUTPUT_DIR / "ESPECIAL_section.jpg", shot_esp)
        except Exception as e:
            p(f"  ESPECIAL nav error: {e}")

        p(f"\n  Browser stays open 15s for inspection.")
        await asyncio.sleep(15)
        await context.close()
        await browser.close()

    shots = sorted(OUTPUT_DIR.glob("*.jpg"))
    p(f"\n{'='*65}")
    p(f"  UNLOCK TEST COMPLETE — {len(shots)} screenshots saved")
    p(f"  Location: {OUTPUT_DIR}")
    p(f"{'='*65}")
    for s in shots:
        p(f"  {s.name:50} {s.stat().st_size//1024:5}KB")


if __name__ == "__main__":
    asyncio.run(run_unlock())
