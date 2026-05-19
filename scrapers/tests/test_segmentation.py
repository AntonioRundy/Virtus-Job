"""
Visual Segmentation Test — Jornal de Angola ESPECIAL section.

Tests the two-pass pipeline on real captured screenshots.
Reads from: scrapers/tests/output/especial/
Saves crops to: scrapers/tests/output/crops/
Saves results to: scrapers/tests/output/segmentation_results.json

Usage (workspace root):
    scrapers\\.venv\\Scripts\\python -m scrapers.tests.test_segmentation

IMPORTANT: set ANTHROPIC_API_KEY in .env to enable Vision extraction.
Without it, OCR fallback is used (limited results).
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapers.pipeline.visual_segmenter import VisualSegmenter
from scrapers.pipeline.page_processor   import PageProcessor

ESPECIAL_DIR = Path(__file__).parent / "output" / "especial"
CROPS_DIR    = Path(__file__).parent / "output" / "crops"
OUTPUT_FILE  = Path(__file__).parent / "output" / "segmentation_results.json"
SOURCE_URL   = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))


async def run_segmentation() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    p("=" * 65)
    p("  Visual Segmentation Test — Jornal de Angola 17/05/2026")
    p(f"  Claude Vision: {'ENABLED' if api_key else 'DISABLED (OCR fallback)'}")
    p("=" * 65)

    # Find screenshots to process
    screenshots = sorted(ESPECIAL_DIR.glob("spread_*_A_top.jpg"))
    if not screenshots:
        p(f"  ERROR: No screenshots in {ESPECIAL_DIR}")
        p("  Run test_especial_extract.py first to capture pages.")
        sys.exit(1)

    p(f"\n  Found {len(screenshots)} page screenshots to process")
    p(f"  Crops will be saved to: {CROPS_DIR}")
    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    processor = PageProcessor(
        source_url   = SOURCE_URL,
        source_name  = "Jornal de Angola",
        dry_run      = True,
        save_crops   = CROPS_DIR,
    )

    all_results = []
    total_segments = 0

    # Process each top screenshot (representative of each spread)
    for shot_path in screenshots:
        spread_num = int(shot_path.stem.split("_")[1])
        p(f"\n[Spread {spread_num:2d}] {shot_path.name}")

        screenshot = shot_path.read_bytes()
        results = await processor.process(screenshot, page_num=spread_num)

        if results:
            p(f"  Found {len(results)} opportunities:")
            for r in results:
                org  = str(r.get("organization") or r.get("title","?"))[:45]
                typ  = r.get("type","?")
                conf = r.get("confidence", 0)
                p(f"    [{typ:10}] conf={conf:.2f}  {org}")
            all_results.extend(results)
            total_segments += len(results)
        else:
            p(f"  No opportunities detected")

        await asyncio.sleep(0.5)

    # Save results
    output = {
        "extraction_date"  : datetime.now().isoformat(),
        "source"           : SOURCE_URL,
        "spreads_processed": len(screenshots),
        "total_opportunities": total_segments,
        "vision_enabled"   : bool(api_key),
        "results"          : all_results,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    p(f"\n{'='*65}")
    p(f"  SEGMENTATION COMPLETE")
    p(f"  Spreads processed   : {len(screenshots)}")
    p(f"  Total opportunities : {total_segments}")
    p(f"  Results saved       : {OUTPUT_FILE}")
    p(f"  Crops saved         : {len(list(CROPS_DIR.glob('*.jpg')))} images")
    p(f"{'='*65}")

    if total_segments > 0:
        p(f"\n  ALL DETECTED OPPORTUNITIES:")
        by_type: dict[str, int] = {}
        for r in all_results:
            t = r.get("type", "?")
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items()):
            p(f"    {t:12}: {count}")

        p(f"\n  TOP RESULTS:")
        sorted_results = sorted(all_results, key=lambda x: x.get("confidence", 0), reverse=True)
        for r in sorted_results[:10]:
            org   = str(r.get("organization") or r.get("title","?"))[:50]
            typ   = r.get("type","?")
            conf  = r.get("confidence", 0)
            email = r.get("contact_email", "")
            loc   = r.get("location", "")
            p(f"  [{typ:10}] {org}")
            p(f"              conf={conf:.2f} | email={email or '-'} | loc={loc or '-'}")


if __name__ == "__main__":
    asyncio.run(run_segmentation())
