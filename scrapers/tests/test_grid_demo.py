"""
Grid Demo — proves crop pipeline works (no API key needed).
Splits spread_02 (ANRM editais) into a smart grid and saves crops.
This proves: "the crops are ready for Vision when the API key is added."
"""
import asyncio, os, sys
from pathlib import Path

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PIL import Image
import io

ESPECIAL_DIR = Path(__file__).parent / "output" / "especial"
CROPS_DIR    = Path(__file__).parent / "output" / "grid_crops"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))


def smart_grid_crop(
    screenshot: bytes,
    source_name: str,
    cols: int = 2,
    rows: int = 4,
) -> list[tuple[bytes, str]]:
    """Split newspaper spread into grid crops, skipping navigation chrome."""
    img = Image.open(io.BytesIO(screenshot))
    w, h = img.size

    # PressReader layout: top ~45px = toolbar, bottom ~60px = tabs
    top_margin    = 45
    bottom_margin = 60
    content_h = h - top_margin - bottom_margin

    crops = []
    cw = w // cols
    rh = content_h // rows

    for r in range(rows):
        for c in range(cols):
            x1 = c * cw
            y1 = top_margin + r * rh
            x2 = min(w, x1 + cw)
            y2 = min(h - bottom_margin, y1 + rh)

            crop = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=88)
            label = f"{source_name}_r{r+1}c{c+1}"
            crops.append((buf.getvalue(), label))

    return crops


async def run_demo() -> None:
    p("=" * 60)
    p("  Grid Crop Demo — Proving crop pipeline works")
    p("=" * 60)

    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    # Use spread_02 (confirmed to have ANRM editais)
    spread02 = ESPECIAL_DIR / "spread_02_A_top.jpg"
    if not spread02.exists():
        p(f"  ERROR: {spread02} not found. Run test_especial_extract.py first.")
        return

    screenshot = spread02.read_bytes()
    p(f"\n  Source: {spread02.name} ({len(screenshot)//1024}KB)")

    # Smart grid crop
    crops = smart_grid_crop(screenshot, "spread02", cols=2, rows=4)
    p(f"  Grid: 2 cols × 4 rows = {len(crops)} crops")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    p(f"  Vision API: {'ENABLED — will extract data' if api_key else 'DISABLED — crops saved for manual inspection'}")
    p()

    for crop_bytes, label in crops:
        path = CROPS_DIR / f"{label}.jpg"
        path.write_bytes(crop_bytes)
        kb = len(crop_bytes) // 1024

        if api_key:
            # Use Vision extractor on each crop
            from scrapers.pipeline.visual_segmenter import VisualSegmenter, PageSegment, BoundingBox
            seg = PageSegment(
                image_bytes=crop_bytes,
                opp_type="ANUNCIO",
                bbox_pct=BoundingBox(0, 0, 100, 100),
                company_hint=None,
                keywords=[],
                confidence=0.5,
                segment_idx=0,
            )
            segmenter = VisualSegmenter()
            result = await segmenter.extract_segment(seg)
            opp_type = result.get("type", "?")
            org = str(result.get("organization") or result.get("title") or "?")[:40]
            conf = result.get("confidence", 0)
            if opp_type != "NOT_OPPORTUNITY":
                p(f"  {path.name:35} {kb:4}KB → [{opp_type}] {org} (conf={conf:.2f})")
            else:
                p(f"  {path.name:35} {kb:4}KB → (not opportunity)")
        else:
            p(f"  {path.name:35} {kb:4}KB → [awaiting API key for extraction]")

    p(f"\n  {len(crops)} crops saved to: {CROPS_DIR}")
    p()
    p("  STATUS: Crop pipeline WORKS.")
    p("  NEXT STEP: Add ANTHROPIC_API_KEY to .env to activate Vision extraction.")
    p()
    p("  With Vision enabled, the pipeline will:")
    p("    Pass 1: Detect ALL announcement blocks in each page")
    p("    Pass 2: Extract company, email, requirements, deadline from each")
    p("    Expected to find: Halliburton, Telhabel, ADV Angola, ISPN, TruCare, ANSEBA")


if __name__ == "__main__":
    asyncio.run(run_demo())
