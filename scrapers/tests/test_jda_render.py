"""
JdA Render Validation Test
Proves: "o sistema consegue ver o Jornal de Angola"

Stages:
  1. Load PressReader with authenticated session
  2. Wait for canvas/WebGL to render (with pixel detection)
  3. Take progressive screenshots at intervals
  4. Detect when content is actually visible (not black)
  5. Try zoom/interact to expose newspaper content
  6. Save all screenshots for inspection
  7. Report render quality

NO Vision/OCR — only render validation.

Usage (from workspace root):
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_jda_render
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ─── Config ──────────────────────────────────────────────────────────────────

SESSION_FILE  = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
OUTPUT_DIR    = Path(__file__).parent / "output" / "render_validation"
PORTAL_URL    = "https://edicoesnovembro.pressreader.com/jornal-de-angola"

# PressReader edition URL formats to try
EDITION_URLS  = [
    "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517",
    "https://edicoesnovembro.pressreader.com/angola/jornal-de-angola/20260517",
    "https://edicoesnovembro.pressreader.com/jornal-de-angola",
]

def p(*args):
    try:
        print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii", "replace").decode("ascii"))

def save_shot(path: Path, data: bytes, label: str):
    path.write_bytes(data)
    kb = len(data) // 1024
    p(f"  Screenshot [{label}]: {path.name} ({kb}KB)")

# ─── Canvas / Render Detection ───────────────────────────────────────────────

CANVAS_PIXEL_CHECK_JS = """
() => {
    const results = {
        canvases: 0,
        canvas_with_content: 0,
        max_canvas_size: [0, 0],
        sample_pixel: null
    };
    const canvases = document.querySelectorAll('canvas');
    results.canvases = canvases.length;
    for (const c of canvases) {
        if (c.width > results.max_canvas_size[0]) {
            results.max_canvas_size = [c.width, c.height];
        }
        try {
            const ctx = c.getContext('2d');
            if (ctx && c.width > 50 && c.height > 50) {
                const mid_x = Math.floor(c.width / 2);
                const mid_y = Math.floor(c.height / 2);
                const d = ctx.getImageData(mid_x, mid_y, 1, 1).data;
                const is_black = d[0] === 0 && d[1] === 0 && d[2] === 0;
                if (!is_black) {
                    results.canvas_with_content++;
                    results.sample_pixel = [d[0], d[1], d[2], d[3]];
                }
            }
        } catch(e) {}
    }
    return results;
}
"""

PAGE_STATE_JS = """
() => {
    const body = document.body;
    const images = document.querySelectorAll('img[src]');
    const spinners = document.querySelectorAll('[class*="loading"], [class*="spinner"], [class*="loader"]');
    const pages = document.querySelectorAll('[class*="page"], [class*="Page"]');
    const text_nodes = document.querySelectorAll('p, span, div');
    let visible_text = '';
    for (const el of text_nodes) {
        const t = el.innerText?.trim();
        if (t && t.length > 10) { visible_text += t.substring(0, 50) + ' | '; if (visible_text.length > 200) break; }
    }
    return {
        url: window.location.href,
        title: document.title,
        images_count: images.length,
        loading_indicators: spinners.length,
        page_elements: pages.length,
        body_text_length: body.innerText.length,
        visible_text_sample: visible_text.substring(0, 200),
        window_size: [window.innerWidth, window.innerHeight],
        scroll_size: [document.documentElement.scrollWidth, document.documentElement.scrollHeight]
    };
}
"""

FIND_CONTENT_ELEMENTS_JS = """
() => {
    const selectors = [
        'img[src*="newspaper"]', 'img[src*="page"]', 'img[src*="issue"]',
        '[class*="reader"]', '[class*="viewer"]', '[class*="newspaper"]',
        '[class*="page-view"]', '[class*="issue"]', '[class*="edition"]',
        'canvas', 'iframe', 'svg[width]'
    ];
    const found = {};
    for (const sel of selectors) {
        const els = document.querySelectorAll(sel);
        if (els.length > 0) {
            found[sel] = els.length;
        }
    }
    return found;
}
"""


async def wait_for_render(page, timeout_s: int = 30) -> dict:
    """
    Poll until canvas has content OR timeout.
    Returns render status dict.
    """
    p(f"  Waiting for render (max {timeout_s}s)...")
    for t in range(timeout_s):
        await asyncio.sleep(1)
        try:
            canvas = await page.evaluate(CANVAS_PIXEL_CHECK_JS)
            state  = await page.evaluate(PAGE_STATE_JS)

            if t % 5 == 0 or canvas["canvas_with_content"] > 0:
                p(f"  t={t+1:3d}s | canvas={canvas['canvases']} content={canvas['canvas_with_content']} "
                  f"sz={canvas['max_canvas_size']} | img={state['images_count']} "
                  f"load={state['loading_indicators']} text={state['body_text_length']}")

            if canvas["canvas_with_content"] > 0:
                p(f"  Content detected at t={t+1}s! Pixel: {canvas['sample_pixel']}")
                return {"rendered": True, "time_s": t + 1, "canvas": canvas, "state": state}

            # Also check if body has substantial text (text-based reader)
            if state["body_text_length"] > 500 and state["images_count"] > 3:
                p(f"  Text+image content at t={t+1}s")
                return {"rendered": True, "time_s": t + 1, "canvas": canvas, "state": state}

        except Exception as exc:
            p(f"  t={t+1}s evaluation error: {exc}")

    return {"rendered": False, "time_s": timeout_s}


async def try_trigger_render(page) -> None:
    """Try various interactions to trigger the reader to render."""
    actions = [
        ("scroll down", lambda: page.evaluate("window.scrollTo(0, 300)")),
        ("scroll up",   lambda: page.evaluate("window.scrollTo(0, 0)")),
        ("click center", lambda: page.mouse.click(720, 450)),
        ("press Space", lambda: page.keyboard.press("Space")),
        ("press ArrowRight", lambda: page.keyboard.press("ArrowRight")),
    ]
    for label, action in actions:
        try:
            await action()
            await asyncio.sleep(0.5)
            p(f"  Triggered: {label}")
        except Exception:
            pass


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_render_validation() -> None:
    from playwright.async_api import async_playwright

    p("=" * 65)
    p("  JdA Render Validation — Proving Visual Content Works")
    p("=" * 65)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SESSION_FILE.exists():
        p(f"ERROR: No session — run test_jda_auth.py first")
        sys.exit(1)

    import time
    session_data = json.loads(SESSION_FILE.read_text())
    storage_state = session_data.get("storage_state", session_data)
    age_h = (time.time() - session_data.get("saved_at", 0)) / 3600
    p(f"  Session: {SESSION_FILE.name} ({age_h:.1f}h old)")
    cookies = storage_state.get("cookies", [])
    has_aprofile = any(c.get("name") == "AProfile" for c in cookies)
    p(f"  AProfile (PressReader auth): {'YES' if has_aprofile else 'NO'}")

    async with async_playwright() as pw:
        # Try both desktop and tablet viewport — some readers render better at specific sizes
        for viewport_label, vp in [("desktop_1440", {"width": 1440, "height": 900}),
                                    ("tablet_768",   {"width":  768, "height": 1024})]:
            p(f"\n{'─'*65}")
            p(f"  Viewport: {viewport_label} ({vp['width']}x{vp['height']})")
            p(f"{'─'*65}")

            browser = await pw.chromium.launch(
                headless=False,
                slow_mo=50,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--enable-accelerated-2d-canvas",
                    "--enable-gpu",
                ],
            )
            context = await browser.new_context(
                storage_state=storage_state,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                locale="pt-AO",
                viewport=vp,
                device_scale_factor=1,
            )
            page = await context.new_page()

            for url_idx, url in enumerate(EDITION_URLS):
                p(f"\n  [URL {url_idx+1}] {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    p(f"  Navigation error: {e}")
                    # Take screenshot anyway
                    shot = await page.screenshot(type="jpeg", quality=85)
                    save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_error.jpg", shot, "error")
                    continue

                p(f"  Landed at: {page.url}")

                # Screenshot immediately
                shot0 = await page.screenshot(type="jpeg", quality=85)
                save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_t0_immediate.jpg", shot0, "t=0s")

                # Initial state
                try:
                    state0 = await page.evaluate(PAGE_STATE_JS)
                    elements = await page.evaluate(FIND_CONTENT_ELEMENTS_JS)
                    p(f"  State: title='{state0['title']}' text={state0['body_text_length']} img={state0['images_count']}")
                    p(f"  Content elements: {elements}")
                    p(f"  Visible text: {state0['visible_text_sample'][:100]}")
                except Exception as e:
                    p(f"  State check error: {e}")

                # Wait 5s, screenshot
                await asyncio.sleep(5)
                shot5 = await page.screenshot(type="jpeg", quality=85)
                save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_t5_after5s.jpg", shot5, "t=5s")

                # Try interactions to trigger render
                await try_trigger_render(page)

                # Wait for render with pixel detection
                render = await wait_for_render(page, timeout_s=25)
                p(f"  Render result: {render.get('rendered')} in {render.get('time_s')}s")

                # Screenshot after render attempt
                shot_render = await page.screenshot(type="jpeg", quality=85)
                save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_render.jpg", shot_render, "render")

                # If content found, do detailed inspection
                if render.get("rendered"):
                    p(f"\n  Content visible! Taking detailed screenshots...")

                    # Full-page screenshot
                    shot_full = await page.screenshot(type="jpeg", quality=90, full_page=True)
                    save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_FULL.jpg", shot_full, "FULL")

                    # Try to zoom in on content area
                    try:
                        await page.evaluate("document.body.style.zoom = '1.5'")
                        await asyncio.sleep(1)
                        shot_zoom = await page.screenshot(type="jpeg", quality=90)
                        save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_zoom150.jpg", shot_zoom, "zoom 150%")
                        await page.evaluate("document.body.style.zoom = '1.0'")
                    except Exception:
                        pass

                    # Navigate to next page and screenshot
                    try:
                        await page.keyboard.press("ArrowRight")
                        await asyncio.sleep(3)
                        shot_p2 = await page.screenshot(type="jpeg", quality=90)
                        save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_page2.jpg", shot_p2, "page 2")
                    except Exception:
                        pass

                    # Try to find and click on an article/content area
                    try:
                        canvas = await page.query_selector("canvas")
                        if canvas:
                            box = await canvas.bounding_box()
                            if box:
                                p(f"  Canvas found: {box['width']:.0f}x{box['height']:.0f} at ({box['x']:.0f},{box['y']:.0f})")
                                # Click center of canvas to open article
                                cx = box["x"] + box["width"] / 2
                                cy = box["y"] + box["height"] / 2
                                await page.mouse.click(cx, cy)
                                await asyncio.sleep(2)
                                shot_click = await page.screenshot(type="jpeg", quality=90)
                                save_shot(OUTPUT_DIR / f"{viewport_label}_url{url_idx+1}_canvas_click.jpg", shot_click, "canvas click")
                    except Exception as e:
                        p(f"  Canvas click error: {e}")

                    p(f"\n  SUCCESS: Content rendered for {url}")
                    break  # Found working URL, stop trying others

                else:
                    p(f"  No content after {render.get('time_s')}s — trying next URL")

            await context.close()
            await browser.close()

            # After finding content, stop trying viewports
            if render.get("rendered"):
                break

    # Report
    shots = sorted(OUTPUT_DIR.glob("*.jpg"))
    p(f"\n{'='*65}")
    p(f"  RENDER VALIDATION COMPLETE")
    p(f"  Screenshots saved: {len(shots)} files")
    p(f"  Location: {OUTPUT_DIR}")
    p(f"{'='*65}")
    for s in shots:
        kb = s.stat().st_size // 1024
        p(f"  {s.name:55} {kb:5}KB")


if __name__ == "__main__":
    asyncio.run(run_render_validation())
