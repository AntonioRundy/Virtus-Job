"""
Virtus Job — JdA Vision Extraction Prototype
Edition: 17 Maio 2026
Strategy: PRESSREADER_VISION

Flow:
  1. Load authenticated session (JWT in localStorage)
  2. Navigate to jornaldeangola.ao subscriber area
  3. Find digital edition link for May 17, 2026
  4. Navigate page by page
  5. Screenshot each page
  6. Claude Vision scan (fast) → detect opportunity pages
  7. Claude Vision extract (full) → structured JSON per opportunity
  8. Save output to tests/output/jda_vision_20260517.json

No DB persistence — prototype only.

Usage:
    cd C:\\Users\\LENOVO\\Documents\\2026\\my-softwaree\\virtus-job
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_jda_vision
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# Add scrapers to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapers.pipeline.vision_extractor import VisionExtractor

# ─── Configuration ────────────────────────────────────────────────────────────

TARGET_DATE     = "2026-05-17"
TARGET_DATE_PT  = "17 Maio 2026"
SESSION_FILE    = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
OUTPUT_DIR      = Path(__file__).parent / "output"
OUTPUT_FILE     = OUTPUT_DIR / f"jda_vision_{TARGET_DATE.replace('-','')}.json"

JDA_BASE        = "https://jornaldeangola.ao"
SUBSCRIBER_URL  = f"{JDA_BASE}/area-reservada/assinaturas"
PRESSREADER_URL = "https://edicoesnovembro.pressreader.com/jornal-de-angola"

MAX_PAGES       = 60   # newspaper typically 40-60 pages
OPPORTUNITY_THRESHOLD = 0.3   # minimum confidence to trigger full extraction

# ─── Helpers ─────────────────────────────────────────────────────────────────

def p(*args):
    """Unicode-safe print for Windows."""
    try:
        print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii", errors="replace").decode("ascii"))


def load_session() -> dict:
    """Load saved Playwright storage_state (cookies + localStorage)."""
    if not SESSION_FILE.exists():
        p(f"ERROR: Session file not found: {SESSION_FILE}")
        p("Run: scrapers\\.venv\\Scripts\\python -m tests.test_jda_auth")
        sys.exit(1)
    data = json.loads(SESSION_FILE.read_text())
    state = data.get("storage_state", data)
    age_h = (time.time() - data.get("saved_at", 0)) / 3600
    p(f"[Vision] Session loaded ({age_h:.1f}h old)")
    return state


async def inject_session_to_page(page, storage_state: dict) -> None:
    """Inject localStorage tokens into the page context."""
    for origin_data in storage_state.get("origins", []):
        origin = origin_data.get("origin", "")
        if "jornaldeangola" in origin:
            for item in origin_data.get("localStorage", []):
                try:
                    await page.evaluate(
                        f"window.localStorage.setItem({json.dumps(item['name'])}, {json.dumps(item['value'])})"
                    )
                except Exception:
                    pass


async def go_to_next_page(page) -> bool:
    """Navigate to next newspaper page. Returns False if no more pages."""
    next_selectors = [
        "[class*='next-page']",
        "[class*='nextPage']",
        "[aria-label*='next' i]",
        "[aria-label*='proximo' i]",
        "[data-action='nextPage']",
        ".btn-next",
        "button.next",
        "[class*='arrow-right']",
        "[class*='page-forward']",
    ]
    for sel in next_selectors:
        try:
            btn = await page.query_selector(sel)
            if btn:
                is_disabled = await btn.get_attribute("disabled")
                if not is_disabled:
                    await btn.click()
                    await asyncio.sleep(2)
                    return True
        except Exception:
            pass

    # Fallback: ArrowRight keyboard
    try:
        await page.keyboard.press("ArrowRight")
        await asyncio.sleep(1.5)
        return True
    except Exception:
        return False


async def find_edition_link(page, target_date: str) -> str | None:
    """Find the link to the specific edition by date."""
    # Try various date formats that newspapers typically use
    date_formats = [
        target_date,           # 2026-05-17
        "17-05-2026",
        "17/05/2026",
        "17 de Maio de 2026",
        "17 Maio 2026",
        "17 maio 2026",
    ]

    # Look for edition links containing the date
    links = await page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => ({href: e.href, text: (e.innerText||e.title||'').trim()}))"
    )

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")
        for fmt in date_formats:
            if fmt in href or fmt in text:
                p(f"  Found edition link: {href[:80]} (text: {text[:40]})")
                return href

    # Look for date attributes
    dated_el = await page.query_selector(f"[data-date='{target_date}'], [data-edition='{target_date}']")
    if dated_el:
        href = await dated_el.get_attribute("href")
        return href

    return None


# ─── Main extraction routine ──────────────────────────────────────────────────

async def run_vision_extraction() -> None:
    from playwright.async_api import async_playwright

    p("=" * 60)
    p(f"  JdA Vision Extraction — {TARGET_DATE_PT}")
    p(f"  Strategy: PRESSREADER_VISION")
    p("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    storage_state = load_session()

    # Screenshot archive for debugging
    screenshots_dir = OUTPUT_DIR / f"screenshots_{TARGET_DATE.replace('-','')}"
    screenshots_dir.mkdir(exist_ok=True)

    extractor = VisionExtractor()
    all_results = {
        "edition_date": TARGET_DATE,
        "source": "Jornal de Angola",
        "strategy": "PRESSREADER_VISION",
        "extracted_at": datetime.now().isoformat(),
        "pages_scanned": 0,
        "opportunity_pages": [],
        "total_opportunities": 0,
        "opportunities": [],
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # Visible — easier to observe and debug
            slow_mo=100,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=storage_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="pt-AO",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        # ─── Step 1: Navigate to JdA and verify authentication ────────────────
        p(f"\n[1] Loading {SUBSCRIBER_URL}...")
        await page.goto(SUBSCRIBER_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        title = await page.evaluate("document.title")
        current_url = page.url
        p(f"  Title: {title}")
        p(f"  URL  : {current_url}")

        # Check if authenticated (no redirect to login)
        if "login" in current_url.lower() or "assinantes/login" in current_url:
            p("  Session expired — re-authenticating...")
            # Inject localStorage session
            await page.goto(JDA_BASE, wait_until="domcontentloaded", timeout=20000)
            await inject_session_to_page(page, storage_state)
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(2)

        p(f"  Authenticated: {page.url}")

        # ─── Step 2: Navigate directly to PressReader with session ──────────
        p(f"\n[2] Navigating to PressReader with authenticated session...")
        await page.goto(PRESSREADER_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        p(f"  PressReader URL  : {page.url}")
        p(f"  PressReader title: {await page.evaluate('document.title')}")

        # Take screenshot to see what PressReader shows
        pr_screenshot = await page.screenshot(type="jpeg", quality=80)
        (OUTPUT_DIR / "pressreader_landing.jpg").write_bytes(pr_screenshot)
        p(f"  Screenshot saved: {OUTPUT_DIR}/pressreader_landing.jpg")

        # Look for the May 17, 2026 edition or latest edition
        p(f"\n  Looking for {TARGET_DATE_PT} edition...")

        # Dump all links in current reader page to find edition
        all_links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href:e.href,text:(e.innerText||e.title||'').trim().substring(0,50)}))"
        )
        p(f"  Links in subscriber area ({len(all_links)}):")
        for l in all_links:
            if l["href"] and l["href"] != "javascript:void(0)":
                p(f"    '{l['text']:45}' -> {l['href'][:70]}")

        # Look for the reader link — try known patterns
        digital_selectors = [
            "a:has-text('LEIA O JORNAL')",
            "a:has-text('Leia o Jornal')",
            "a:has-text('JORNAL DIGITAL')",
            "a:has-text('Jornal Digital')",
            "a:has-text('Edição Digital')",
            "a:has-text('Edição do Dia')",
            "a:has-text('Ver Jornal')",
            "[href*='pressreader']",
            "[href*='edicoes']",
            "[href*='edicao']",
            "[href*='digital']",
            "[href*='leitor']",
        ]

        reader_url = None
        for sel in digital_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    href = await btn.get_attribute("href") or ""
                    text = (await btn.inner_text()).strip()
                    p(f"  Found reader link: '{text[:40]}' -> {href}")
                    if href and href != "javascript:void(0)":
                        reader_url = href
                        break
            except Exception:
                pass

        # Navigate to reader
        if reader_url:
            p(f"  Navigating to: {reader_url}")
            await page.goto(reader_url, wait_until="domcontentloaded", timeout=30000)
        else:
            # Fallback: PressReader portal with auth session
            reader_url = "https://edicoesnovembro.pressreader.com/jornal-de-angola"
            p(f"  Fallback: navigating to {reader_url}")
            await page.goto(reader_url, wait_until="domcontentloaded", timeout=30000)

        await asyncio.sleep(4)
        p(f"  Reader URL: {page.url}")
        p(f"  Title: {await page.evaluate('document.title')}")

        # Find edition for target date
        edition_url = await find_edition_link(page, TARGET_DATE)
        if edition_url:
            p(f"  Opening {TARGET_DATE} edition: {edition_url}")
            await page.goto(edition_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        else:
            p(f"  No specific {TARGET_DATE} edition link — scanning current reader page")
            reader_links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.slice(0,25).map(e => ({href:e.href,text:(e.innerText||'').trim().substring(0,40)}))"
            )
            for l in reader_links:
                if l["text"] or "2026" in l["href"] or "edicao" in l["href"]:
                    p(f"    '{l['text']:35}' -> {l['href'][:60]}")

        p(f"\n  Current reader URL: {page.url}")

        # ─── Step 3: Page-by-page screenshot + Vision analysis ────────────────
        p(f"\n[3] Starting page-by-page Vision extraction (max {MAX_PAGES} pages)...")
        p("    [S=scanned, O=opportunities found, -=no opportunities]\n")

        page_num = 1
        consecutive_empty = 0

        while page_num <= MAX_PAGES:
            # Take screenshot
            try:
                screenshot = await page.screenshot(
                    type="jpeg",
                    quality=80,
                    full_page=False,
                )
            except Exception as exc:
                p(f"  p{page_num}: Screenshot failed: {exc}")
                break

            # Save screenshot for debugging
            ss_path = screenshots_dir / f"page_{page_num:03d}.jpg"
            ss_path.write_bytes(screenshot)

            # Fast scan: detect opportunity keywords
            scan = await extractor.scan_page(screenshot, page_num)
            all_results["pages_scanned"] = page_num

            if scan.get("has_opportunities") and scan.get("confidence", 0) >= OPPORTUNITY_THRESHOLD:
                p(f"  p{page_num:3d} [O] {scan.get('keywords_found', [])} (conf={scan.get('confidence', 0):.2f})")

                # Full extraction
                extraction = await extractor.extract_opportunities(
                    screenshot=screenshot,
                    page_num=page_num,
                    edition_date=TARGET_DATE,
                    source_url=page.url,
                )

                if extraction.get("opportunities"):
                    all_results["opportunity_pages"].append(page_num)
                    for opp in extraction["opportunities"]:
                        opp["page_number"] = page_num
                        opp["source_url"] = page.url
                        all_results["opportunities"].append(opp)
                    all_results["total_opportunities"] = len(all_results["opportunities"])

                consecutive_empty = 0
            else:
                desc = scan.get("page_description", "")[:30]
                p(f"  p{page_num:3d} [-] {desc}")
                consecutive_empty += 1

            # Stop if many consecutive empty pages (likely end of newspaper)
            if consecutive_empty >= 8:
                p(f"\n  8 consecutive non-opportunity pages — likely end of newspaper.")
                break

            # Next page
            if not await go_to_next_page(page):
                p(f"\n  No more pages after p{page_num}")
                break

            page_num += 1

        # ─── Step 4: Save results ─────────────────────────────────────────────
        p(f"\n[4] Saving results...")
        all_results["extraction_completed_at"] = datetime.now().isoformat()

        OUTPUT_FILE.write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        p(f"\n{'=' * 60}")
        p(f"  EXTRACTION COMPLETE")
        p(f"  Pages scanned    : {all_results['pages_scanned']}")
        p(f"  Opportunity pages: {all_results['opportunity_pages']}")
        p(f"  Total extracted  : {all_results['total_opportunities']}")
        p(f"  Output           : {OUTPUT_FILE}")
        p(f"  Screenshots      : {screenshots_dir}")
        p(f"{'=' * 60}")

        if all_results["opportunities"]:
            p("\n  OPPORTUNITIES FOUND:")
            for opp in all_results["opportunities"]:
                p(f"  p{opp.get('page_number',0):3d} [{opp.get('type','?')}] {opp.get('title','?')[:60]}")
                p(f"       org={opp.get('organization','?')} | deadline={opp.get('deadline','?')} | conf={opp.get('confidence',0):.2f}")

        await asyncio.sleep(5)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_vision_extraction())
