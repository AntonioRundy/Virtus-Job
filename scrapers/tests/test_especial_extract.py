"""
JdA ESPECIAL Section — Full Page Extraction
Reads each page completely: top → scroll down → bottom, then next page.

Navigation pattern (4 directions):
  - ArrowRight : próxima página
  - ArrowLeft  : página anterior
  - Scroll Down: ver parte inferior da página actual
  - Scroll Up  : voltar ao topo

Per page capture:
  1. Screenshot TOPO (parte superior)
  2. Scroll down para ver parte inferior
  3. Screenshot FUNDO (parte inferior)
  4. ArrowRight para próxima página

Usage (workspace root):
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_especial_extract
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

SESSION_FILE   = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
OUTPUT_DIR     = Path(__file__).parent / "output" / "especial"
PRESSREADER    = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517"
MAX_PAGES      = 20   # max spreads to scan in ESPECIAL
SCROLL_AMOUNT  = 600  # pixels per scroll step

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))


async def snap(page, label: str = "") -> bytes:
    try:
        return await page.screenshot(
            type="jpeg", quality=88,
            animations="disabled",
            timeout=15000,
        )
    except Exception as e:
        p(f"  snap error [{label}]: {e}")
        return b""

def save(data: bytes, name: str) -> Path:
    if data:
        path = OUTPUT_DIR / name
        path.write_bytes(data)
        p(f"  [{len(data)//1024:4d}KB] {name}")
        return path
    return None


async def read_full_page(page, spread_num: int) -> list[Path]:
    """
    Capture a complete newspaper spread:
      - Screenshot top
      - Scroll down once (half page height)
      - Screenshot middle
      - Scroll down again
      - Screenshot bottom
      - Scroll back to top for next navigation
    Returns list of saved screenshot paths.
    """
    paths = []

    # TOP
    shot = await snap(page, f"spread{spread_num}_top")
    p_top = save(shot, f"spread_{spread_num:02d}_A_top.jpg")
    if p_top: paths.append(p_top)
    await asyncio.sleep(0.5)

    # SCROLL DOWN — half page
    await page.evaluate(f"window.scrollBy(0, {SCROLL_AMOUNT})")
    await asyncio.sleep(1)
    shot = await snap(page, f"spread{spread_num}_mid")
    p_mid = save(shot, f"spread_{spread_num:02d}_B_mid.jpg")
    if p_mid: paths.append(p_mid)
    await asyncio.sleep(0.5)

    # SCROLL DOWN AGAIN — full page bottom
    await page.evaluate(f"window.scrollBy(0, {SCROLL_AMOUNT})")
    await asyncio.sleep(1)
    shot = await snap(page, f"spread{spread_num}_bot")
    p_bot = save(shot, f"spread_{spread_num:02d}_C_bot.jpg")
    if p_bot: paths.append(p_bot)
    await asyncio.sleep(0.5)

    # SCROLL BACK TO TOP before moving to next page
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(0.5)

    return paths


async def main() -> None:
    from playwright.async_api import async_playwright

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SESSION_FILE.exists():
        p("ERROR: No session. Run test_pressreader_login.py first.")
        sys.exit(1)

    session_data = json.loads(SESSION_FILE.read_text())
    storage = session_data.get("storage_state", session_data)
    age_h = (time.time() - session_data.get("saved_at", 0)) / 3600
    p(f"  Session: {age_h:.1f}h old")

    p("=" * 60)
    p("  JdA ESPECIAL Section — Full Page Capture")
    p(f"  Output: {OUTPUT_DIR}")
    p("=" * 60)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=100,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=storage,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-AO",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        # ─── Load reader ──────────────────────────────────────────────────────
        p(f"\n[1] Loading PressReader...")
        await page.goto(PRESSREADER, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        p(f"  Title: {await page.evaluate('document.title')}")
        p(f"  URL  : {page.url}")

        # Check session validity
        is_authenticated = await page.evaluate("""
        () => !document.body.innerText.includes('Assine já')
        """)
        p(f"  Authenticated: {is_authenticated}")

        if not is_authenticated:
            p("  Session expired — re-running login flow...")
            p("  Please run test_pressreader_login.py to refresh session.")
            await browser.close()
            sys.exit(1)

        # ─── Navigate to ESPECIAL section ─────────────────────────────────────
        p(f"\n[2] Navigating to ESPECIAL (section 10)...")

        # Wait for the reader to fully render before clicking tabs
        await asyncio.sleep(3)

        # Try multiple approaches to click ESPECIAL
        especial_clicked = False

        # First: inspect the bottom navigation structure
        nav_info = await page.evaluate("""
        () => {
            // Find the bottom section navigation bar
            const allEls = [...document.querySelectorAll('*')];
            const navCandidates = allEls.filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.bottom > window.innerHeight - 60 &&
                       rect.bottom < window.innerHeight + 10 &&
                       rect.width > 100;
            });
            return navCandidates.slice(0,5).map(el => ({
                tag: el.tagName,
                cls: el.className.substring(0,50),
                text: el.innerText?.trim().substring(0,60),
                rect: {
                    x: Math.round(el.getBoundingClientRect().x),
                    y: Math.round(el.getBoundingClientRect().y),
                    w: Math.round(el.getBoundingClientRect().width),
                    h: Math.round(el.getBoundingClientRect().height),
                }
            }));
        }
        """)
        p(f"  Bottom nav candidates: {nav_info}")

        # Find "ESPECIAL" ONLY in the bottom navigation bar (y > 820px)
        especial_info = await page.evaluate("""
        () => {
            const allEls = [...document.querySelectorAll('*')];
            const especial = allEls.filter(el => {
                const text = (el.innerText || '').trim();
                const isEspecial = text === 'ESPECIAL' || text === '10 ESPECIAL';
                if (!isEspecial) return false;
                const rect = el.getBoundingClientRect();
                // Must be in bottom navigation (y > 820 for 900px viewport)
                return rect.y > 820 && rect.height < 50;
            });
            return especial.map(el => ({
                tag: el.tagName,
                text: el.innerText?.trim(),
                rect: {
                    x: Math.round(el.getBoundingClientRect().x + el.getBoundingClientRect().width/2),
                    y: Math.round(el.getBoundingClientRect().y + el.getBoundingClientRect().height/2),
                }
            }));
        }
        """)
        p(f"  ESPECIAL elements in bottom nav: {especial_info}")

        # Wait for the page content to fully render (not just loading state)
        p("  Waiting for page to fully render...")
        for i in range(15):
            await asyncio.sleep(1)
            body_len = await page.evaluate("document.body.innerText.length")
            if body_len > 3000:
                p(f"  Page rendered at t={i+1}s (text={body_len})")
                break
            if i % 3 == 2:
                p(f"  t={i+1}s: text={body_len}")

        await asyncio.sleep(2)  # extra render buffer

        # Take diagnostic screenshot to verify position
        diag = await snap(page, "before_especial_click")
        save(diag, "00_before_especial_click.jpg")

        # Hover at the very bottom to reveal/activate the tab bar
        p("  Hovering at bottom to activate tab bar...")
        await page.mouse.move(716, 890)
        await asyncio.sleep(1.5)
        await page.mouse.move(716, 875)
        await asyncio.sleep(1)

        # Find ESPECIAL in DOM — search ALL elements, no y-filter, small height only
        especial_coords = await page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const t = (el.innerText || el.textContent || '').trim();
                // Must contain ESPECIAL but be a small element (tab-sized)
                if ((t === 'ESPECIAL' || t === '10 ESPECIAL') &&
                    el.children.length < 3) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 20 && r.width < 300 && r.height > 0 && r.height < 60) {
                        results.push({
                            tag: el.tagName,
                            text: t,
                            cx: Math.round(r.x + r.width/2),
                            cy: Math.round(r.y + r.height/2),
                            w: Math.round(r.width),
                            h: Math.round(r.height)
                        });
                    }
                }
            });
            return results;
        }
        """)
        p(f"  ESPECIAL elements (all heights): {especial_coords}")

        if especial_coords:
            el = especial_coords[0]
            p(f"  Clicking DOM element at ({el['cx']}, {el['cy']}) size={el['w']}x{el['h']}")
            await page.mouse.click(el['cx'], el['cy'])
        elif especial_info:
            el = especial_info[0]
            await page.mouse.click(el['rect']['x'], el['rect']['y'])
        else:
            # Calibrated from DOM inspection after hover: cx=744, cy=877
            p("  Coordinate fallback: x=744, y=877 (verified via DOM)")
            await page.mouse.click(744, 877)

        especial_clicked = True
        await asyncio.sleep(5)
        p(f"  URL: {page.url}")

        # Verify section changed
        diag2 = await snap(page, "after_especial_click")
        save(diag2, "00_after_especial_click.jpg")

        # ─── Full page capture loop ───────────────────────────────────────────
        p(f"\n[3] Reading ESPECIAL pages (full top→bottom capture)...")
        p(f"  Pattern: TOP → scroll↓ MID → scroll↓ BOTTOM → ArrowRight next page")
        p()

        all_screenshots: list[Path] = []
        consecutive_empty = 0

        for spread in range(1, MAX_PAGES + 1):
            p(f"  Spread {spread:2d}/{MAX_PAGES}:")

            # Full page capture (top + mid + bottom)
            paths = await read_full_page(page, spread)
            all_screenshots.extend(paths)

            # Check if we're still in ESPECIAL (detect section change)
            try:
                current_section = await page.evaluate("""
                () => {
                    const active = document.querySelector('[class*="active"][class*="section"], [class*="section"][aria-selected="true"]');
                    return active ? active.innerText.trim() : '';
                }
                """)
                if current_section:
                    p(f"     Section: {current_section}")
            except Exception:
                pass

            # If screenshot is very small (empty page), likely end of section
            if paths and all(p_s.stat().st_size < 15000 for p_s in paths if p_s):
                consecutive_empty += 1
                p(f"     Empty spread ({consecutive_empty}/3)")
                if consecutive_empty >= 3:
                    p(f"  End of section detected.")
                    break
            else:
                consecutive_empty = 0

            # Navigate to next spread: ArrowRight
            await page.keyboard.press("ArrowRight")
            await asyncio.sleep(2.5)

        # ─── Summary ──────────────────────────────────────────────────────────
        p(f"\n{'='*60}")
        p(f"  ESPECIAL capture complete")
        p(f"  Spreads captured : {spread}")
        p(f"  Screenshots saved: {len(all_screenshots)}")
        p(f"  Output           : {OUTPUT_DIR}")
        p(f"{'='*60}")

        # List screenshots with sizes
        for s in sorted(OUTPUT_DIR.glob("*.jpg")):
            kb = s.stat().st_size // 1024
            bar = "█" * min(40, kb // 10)
            p(f"  {s.name:45} {kb:5}KB {bar}")

        p(f"\n  Browser closes in 15s.")
        await asyncio.sleep(15)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
