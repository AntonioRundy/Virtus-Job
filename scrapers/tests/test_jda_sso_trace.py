"""
SSO Trace — capture all network activity during PressReader Entrar click.
Goal: find the exact SSO mechanism (returnUrl, callback, API endpoint).
"""
import asyncio, json, os, sys
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
EDITION_URL  = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))


async def trace_sso() -> None:
    from playwright.async_api import async_playwright

    email    = os.environ.get("JDA_EMAIL", "")
    password = os.environ.get("JDA_PASSWORD", "")

    session_data = json.loads(SESSION_FILE.read_text())
    storage = session_data.get("storage_state", session_data)

    p("=" * 65)
    p("  SSO Trace — Finding PressReader ↔ JdA Authentication Mechanism")
    p("=" * 65)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=100,
            args=["--no-sandbox"])
        context = await browser.new_context(
            storage_state=storage,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="pt-AO", viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        # Capture EVERYTHING
        all_requests = []
        async def on_req(req):
            all_requests.append({
                "method": req.method,
                "url": req.url,
                "headers": dict(req.headers),
                "post": req.post_data or "",
            })
        async def on_resp(resp):
            for r in all_requests:
                if r["url"] == resp.url and "status" not in r:
                    r["status"] = resp.status
                    try:
                        body = await resp.body()
                        r["response_preview"] = body[:200].decode("utf-8", "replace")
                    except Exception:
                        pass
                    break

        page.on("request", on_req)
        page.on("response", on_resp)

        # ─── Step 1: Clear caches ─────────────────────────────────────────────
        await page.goto("https://jornaldeangola.ao", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)
        await page.evaluate("""
        () => {
            ['_token_accesso','utilizadorSessao','perfilCliente'].forEach(k => localStorage.removeItem(k));
        }
        """)

        await page.goto("https://edicoesnovembro.pressreader.com", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)
        old_ticket = await page.evaluate("localStorage.getItem('pr_/authTickets')")
        await page.evaluate("localStorage.removeItem('pr_/authTickets')")
        p(f"  Old authTickets: {old_ticket}")
        p(f"  Caches cleared.")

        # ─── Step 2: Load edition ─────────────────────────────────────────────
        all_requests.clear()
        await page.goto(EDITION_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        p(f"\n  Edition loaded: {page.url}")

        # ─── Step 3: Capture JS of Entrar button before clicking ──────────────
        p("\n  Inspecting 'Entrar' button JavaScript...")
        entrar_info = await page.evaluate("""
        () => {
            const links = [...document.querySelectorAll('a, button')];
            const entrar = links.find(el => el.innerText?.trim() === 'Entrar');
            if (!entrar) return null;
            return {
                tag: entrar.tagName,
                href: entrar.href || '',
                onclick: entrar.getAttribute('onclick') || '',
                class: entrar.className,
                dataset: JSON.stringify(entrar.dataset),
                parent_class: entrar.parentElement?.className || ''
            };
        }
        """)
        p(f"  Entrar element: {entrar_info}")

        # Capture PR localStorage state before click
        pr_ls_before = await page.evaluate("""
        () => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                items[key] = localStorage.getItem(key).substring(0, 80);
            }
            return items;
        }
        """)
        p(f"\n  PressReader localStorage before click: {pr_ls_before}")

        # ─── Step 4: Click and capture EVERYTHING ─────────────────────────────
        p("\n  Clicking 'Entrar' and capturing all network activity...")
        all_requests.clear()

        # Listen for navigation
        nav_urls = []
        def on_nav(frame):
            if frame == page.main_frame:
                nav_urls.append(frame.url)
                p(f"  NAV -> {frame.url[:100]}")
        page.on("framenavigated", on_nav)

        await page.click("a:has-text('Entrar')")
        await asyncio.sleep(10)  # Wait for all SSO redirects

        p(f"\n  Navigation chain: {nav_urls}")
        p(f"\n  Network requests after click ({len(all_requests)}):")
        for r in all_requests:
            method = r.get("method", "?")
            url = r["url"]
            status = r.get("status", "?")
            post = r.get("post", "")[:60]
            resp_preview = r.get("response_preview", "")[:80]

            # Highlight interesting requests
            interesting = any(x in url for x in [
                "pressreader", "jornaldeangola", "kiami", "auth", "login",
                "token", "sso", "callback", "redirect", "oauth"
            ])
            if interesting:
                p(f"  *** [{method}] {status} {url[:100]}")
                if post:
                    p(f"      POST body: {post}")
                if resp_preview:
                    p(f"      Response: {resp_preview}")
            else:
                p(f"      [{method}] {status} {url[:70]}")

        # Final PressReader localStorage state
        current_url = page.url
        if "pressreader" in current_url:
            pr_ls_after = await page.evaluate("""
            () => {
                const items = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    items[key] = localStorage.getItem(key).substring(0, 80);
                }
                return items;
            }
            """)
            p(f"\n  PressReader localStorage after: {pr_ls_after}")
        else:
            p(f"\n  Still on JdA: {current_url}")
            # Try clicking JdA ENTRAR
            p("  Clicking JdA ENTRAR...")
            try:
                await page.click("a:has-text('ENTRAR')")
                await asyncio.sleep(2)
                p(f"  URL: {page.url}")
            except Exception:
                pass

        await asyncio.sleep(30)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(trace_sso())
