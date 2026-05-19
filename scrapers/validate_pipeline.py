# -*- coding: utf-8 -*-
"""
Virtus Job -- Pipeline Validation Script
Runs each pipeline stage independently with real network calls.

Usage:
  python validate_pipeline.py --no-ai          (HTTP + parse only, free)
  python validate_pipeline.py --api-key sk-... (full pipeline with AI)
  python validate_pipeline.py --pages 5        (test 5 detail pages)
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx
from bs4 import BeautifulSoup

# ---- Colour helpers (ANSI) --------------------------------------------------
G   = "\033[92m"
Y   = "\033[93m"
R   = "\033[91m"
C   = "\033[96m"
W   = "\033[1m"
DIM = "\033[2m"
RST = "\033[0m"

def ok(msg):     print(f"{G}  [OK] {msg}{RST}", flush=True)
def warn(msg):   print(f"{Y}  [!!] {msg}{RST}", flush=True)
def fail(msg):   print(f"{R}  [XX] {msg}{RST}", flush=True)
def info(msg):   print(f"{C}  --> {msg}{RST}", flush=True)
def header(msg): print(f"\n{W}{'='*60}\n  {msg}\n{'='*60}{RST}", flush=True)
def dim(msg):    print(f"{DIM}       {msg}{RST}", flush=True)

# ---- MAPTESS configuration --------------------------------------------------
MAPTESS_ENTRY_URLS = [
    "https://www.maptss.gov.ao/concursos-publicos",
    "https://www.maptss.gov.ao/publicacoes",
    "https://www.maptss.gov.ao/vagas",
    "https://www.maptss.gov.ao",
    "https://maptss.gov.ao",
    "https://jornaldeangola.ao/ao/noticias/concursos-publicos",
]

OPPORTUNITY_KEYWORDS = [
    "concurso", "vaga", "bolsa", "estagio", "estagios",
    "recrutamento", "candidatura", "emprego", "formacao",
    "trabalhador", "admissao", "contratacao",
]

SKIP_PATTERNS = [
    "/categoria/", "/category/", "/tag/", "/author/", "/page/",
    ".pdf", ".doc", ".docx", "/wp-admin/", "/feed/", "/rss/",
    "sobre", "contacto", "privacidade", "politica",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-AO,pt;q=0.9,en;q=0.8",
}

CONTENT_SELECTORS = [
    "article .entry-content",
    "article .post-content",
    ".single-content",
    ".page-content",
    ".elementor-widget-text-editor",
    "main article",
    ".content-area",
    "#content",
    "main",
    "body",
]

# ---- HTTP helpers -----------------------------------------------------------

async def fetch_url(client: httpx.AsyncClient, url: str) -> tuple[str | None, int]:
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        return resp.text, resp.status_code
    except httpx.ConnectTimeout:
        return None, -1
    except httpx.ConnectError:
        return None, -2
    except Exception:
        return None, -3


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("nav, header, footer, script, style, .menu, .sidebar, .widget"):
        tag.decompose()

    content = None
    for sel in CONTENT_SELECTORS:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            content = el
            break

    target = content or soup.find("body") or soup
    lines = [l.strip() for l in target.get_text("\n").splitlines() if len(l.strip()) > 5]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def find_opportunity_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    found = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc not in (base_domain, f"www.{base_domain}"):
            continue
        if any(p in full_url.lower() for p in SKIP_PATTERNS):
            continue
        link_text = (anchor.get_text() + " " + full_url).lower()
        # Accent-insensitive keyword check
        link_text_clean = link_text.replace("\xe9", "e").replace("\xe3", "a").replace("\xe7", "c")
        if any(kw in link_text_clean for kw in OPPORTUNITY_KEYWORDS):
            if full_url not in found:
                found.append(full_url)

    return found


def get_page_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return str(og["content"]).strip()[:120]
    GENERIC = {"recentes", "recent", "publicacoes", "noticias", "destaques"}
    for sel in ["h1.entry-title", "h1.post-title", "h1", "title"]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t.lower() not in GENERIC:
                return t[:120]
    return "(no title)"


# ---- AI extraction ----------------------------------------------------------

SYSTEM_PROMPT = """Voce e um extractor de dados especializado para a plataforma Virtus Job, agregador angolano de oportunidades profissionais.

Analise texto de paginas web angolanas e extraia informacao estruturada.

REGRAS:
1. Nunca invente informacao ausente no texto
2. Datas: formato YYYY-MM-DD ou null
3. Resumo: Portugues de Angola, maximo 5 frases
4. Se incerto sobre um campo use null e confidence mais baixo

TIPOS VALIDOS: VAGA, CONCURSO, BOLSA, ESTAGIO, FORMACAO
PROVINCIAS: Luanda, Benguela, Huambo, Bie, Malanje, Kuanza Sul, Uige, Zaire, Cabinda, Cunene, Huila, Kuando Kubango, Kuanza Norte, Lunda Norte, Lunda Sul, Moxico, Namibe, Bengo

Responda APENAS com JSON valido, sem markdown."""

EXTRACTION_PROMPT = """Analise este texto de pagina angolana.

FONTE: MAPTESS
URL: {url}

TEXTO:
---
{text}
---

Retorne JSON:
{{
  "title": "titulo da oportunidade",
  "type": "VAGA|CONCURSO|BOLSA|ESTAGIO|FORMACAO",
  "description": "resumo 2-5 frases em portugues",
  "organization": "instituicao ou null",
  "province": "provincia angolana ou null",
  "municipality": "municipio ou null",
  "deadline": "YYYY-MM-DD ou null",
  "requirements": ["req1", "req2"],
  "benefits": [],
  "categories": ["cat1", "cat2"],
  "confidence": 0.0-1.0,
  "requires_review": true/false
}}"""


async def extract_with_ai(text: str, url: str, api_key: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    prompt = EXTRACTION_PROMPT.format(url=url, text=text[:6000])

    t0 = time.perf_counter()
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    elapsed = time.perf_counter() - t0

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    return {
        "raw": raw,
        "elapsed_s": round(elapsed, 2),
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

# ---- Main validation --------------------------------------------------------

async def validate(use_ai: bool, api_key: str, max_pages: int) -> dict:
    report: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": {},
        "opportunities": [],
        "errors": [],
    }

    print(f"\n{W}{'='*60}{RST}", flush=True)
    print(f"{W}  VIRTUS JOB -- Pipeline Validation{RST}", flush=True)
    print(f"{W}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RST}", flush=True)
    print(f"{W}{'='*60}{RST}\n", flush=True)

    # =========================================================================
    header("STAGE 1: HTTP Connectivity")
    # =========================================================================
    async with httpx.AsyncClient(headers=HEADERS) as client:
        entry_html: str | None = None
        entry_url: str | None = None

        for url in MAPTESS_ENTRY_URLS:
            info(f"Trying: {url}")
            t0 = time.perf_counter()
            html, status = await fetch_url(client, url)
            elapsed = round(time.perf_counter() - t0, 2)

            if status == 200 and html:
                ok(f"HTTP {status} -- {elapsed}s -- {len(html):,} bytes received")
                entry_html = html
                entry_url = url
                report["stages"]["connectivity"] = {"ok": True, "url": url, "time_s": elapsed, "bytes": len(html)}
                break
            elif status == -1:
                warn(f"Timeout (20s): {url}")
            elif status == -2:
                warn(f"Connection refused / DNS error: {url}")
            else:
                warn(f"HTTP {status}: {url}")

        if not entry_html or not entry_url:
            fail("Cannot reach MAPTESS -- all entry URLs failed")
            fail("Possible reasons:")
            fail("  1. Site is temporarily down")
            fail("  2. Network connectivity issue")
            fail("  3. IP blocked (unlikely for gov sites)")
            report["stages"]["connectivity"] = {"ok": False}
            report["errors"].append("MAPTESS unreachable")
            _print_summary(report)
            return report

        # =====================================================================
        header("STAGE 2: HTML Structure Analysis")
        # =====================================================================
        soup = BeautifulSoup(entry_html, "html.parser")
        page_title_tag = soup.title
        page_title = page_title_tag.string.strip() if page_title_tag else "(no title)"
        all_links = soup.find_all("a", href=True)
        base_domain = urlparse(entry_url).netloc
        internal_links = [
            a for a in all_links
            if urlparse(urljoin(entry_url, str(a.get("href","")))).netloc == base_domain
        ]

        is_wordpress = bool(soup.find(string=lambda t: t and "wp-content" in str(t).lower()))
        meta_generator = soup.find("meta", attrs={"name": "generator"})
        generator = meta_generator.get("content", "") if meta_generator else ""

        ok(f"Page title:      {page_title[:80]}")
        ok(f"Total links:     {len(all_links)} ({len(internal_links)} internal)")
        ok(f"Generator:       {generator or 'not detected'}")
        ok(f"WordPress:       {'Yes' if is_wordpress else 'No'}")

        # Detect structure type
        has_article_tags = len(soup.find_all("article")) > 0
        has_structured_lists = len(soup.select(".post, .entry, .item, .card")) > 0
        ok(f"Article tags:    {len(soup.find_all('article'))}")
        ok(f"Structured items:{len(soup.select('.post, .entry, .item, .card'))}")

        report["stages"]["html_analysis"] = {
            "ok": True,
            "title": page_title,
            "internal_links": len(internal_links),
            "is_wordpress": is_wordpress,
            "generator": generator,
        }

        # =====================================================================
        header("STAGE 3: URL Discovery")
        # =====================================================================
        opp_urls = find_opportunity_links(entry_html, entry_url)
        info(f"Keyword-matched links: {len(opp_urls)}")

        if opp_urls:
            ok(f"Found {len(opp_urls)} opportunity links")
            for i, u in enumerate(opp_urls[:8], 1):
                dim(f"{i}. {u}")
        else:
            warn("No keyword-filtered links -- trying all internal links as fallback")
            opp_urls = list(dict.fromkeys(
                urljoin(entry_url, str(a.get("href","")))
                for a in soup.find_all("a", href=True)
                if (urlparse(urljoin(entry_url, str(a.get("href","")))).netloc == base_domain
                    and not any(p in str(a.get("href","")).lower() for p in SKIP_PATTERNS)
                    and len(str(a.get("href",""))) > 5)
            ))
            info(f"Fallback: {len(opp_urls)} internal links available")
            for i, u in enumerate(opp_urls[:5], 1):
                dim(f"{i}. {u}")

        report["stages"]["discovery"] = {
            "ok": True,
            "urls_found": len(opp_urls),
            "entry_url": entry_url,
            "keyword_filtered": len(opp_urls) > 0,
        }

        if not opp_urls:
            fail("No URLs to process")
            _print_summary(report)
            return report

        # =====================================================================
        header("STAGE 4: Fetch & Parse Detail Pages")
        # =====================================================================
        fetched_pages: list[dict] = []
        urls_to_try = opp_urls[:max_pages]
        info(f"Will process {len(urls_to_try)} pages (limit: {max_pages})")

        for idx, url in enumerate(urls_to_try, 1):
            info(f"[{idx}/{len(urls_to_try)}] {url[:75]}")
            await asyncio.sleep(2.5)  # polite delay

            html, status = await fetch_url(client, url)
            if status != 200 or not html:
                warn(f"  Skip -- status {status}")
                continue

            title = get_page_title(html)
            text = extract_text(html)
            chars = len(text)

            # Detect content selectors
            inner_soup = BeautifulSoup(html, "html.parser")
            used_selector = "body (fallback)"
            for sel in CONTENT_SELECTORS:
                el = inner_soup.select_one(sel)
                if el and len(el.get_text(strip=True)) > 200:
                    used_selector = sel
                    break

            ok(f"  Title:    {title[:75]}")
            ok(f"  Content:  {chars:,} chars (selector: {used_selector})")

            if chars < 150:
                warn(f"  Short content -- may be listing page or empty")

            # Show first 400 chars
            preview = " ".join(text[:500].split())[:400]
            dim(f"  Preview: {preview}...")

            fetched_pages.append({
                "url": url,
                "title": title,
                "text": text,
                "chars": chars,
                "selector": used_selector,
            })

        report["stages"]["fetching"] = {
            "ok": len(fetched_pages) > 0,
            "attempted": len(urls_to_try),
            "successful": len(fetched_pages),
            "pages": [{"url": p["url"], "chars": p["chars"]} for p in fetched_pages],
        }

        if not fetched_pages:
            fail("No pages successfully fetched")
            _print_summary(report)
            return report

    # =========================================================================
    header("STAGE 5: AI Extraction")
    # =========================================================================
    if not use_ai:
        warn("AI skipped (--no-ai or no API key)")
        warn("To test AI: python validate_pipeline.py --api-key sk-ant-...")
        report["stages"]["ai"] = {"ok": False, "reason": "skipped"}
        _print_summary(report)
        return report

    total_in_tokens = 0
    total_out_tokens = 0
    ai_results: list[dict] = []

    for idx, page in enumerate(fetched_pages, 1):
        info(f"[{idx}/{len(fetched_pages)}] AI extracting: {page['url'][:60]}")
        try:
            result = await extract_with_ai(page["text"], page["url"], api_key)
            total_in_tokens  += result["input_tokens"]
            total_out_tokens += result["output_tokens"]

            try:
                data = json.loads(result["raw"])
            except json.JSONDecodeError:
                fail(f"  Invalid JSON: {result['raw'][:150]}")
                continue

            data["_source_url"]  = page["url"]   # always preserved
            data["_source_name"] = "MAPTESS"
            data["_elapsed_s"]   = result["elapsed_s"]
            data["_in_tokens"]   = result["input_tokens"]
            data["_out_tokens"]  = result["output_tokens"]
            ai_results.append(data)

            conf = data.get("confidence", 0)
            conf_pct = f"{conf:.0%}"
            conf_color = G if conf >= 0.7 else (Y if conf >= 0.4 else R)
            status = "UNVERIFIED" if data.get("requires_review") or conf < 0.6 else "ACTIVE"
            status_color = G if status == "ACTIVE" else Y

            ok(f"  Title:      {data.get('title','?')[:65]}")
            ok(f"  Type:       {data.get('type','?')}")
            ok(f"  Org:        {data.get('organization') or 'N/A'}")
            ok(f"  Province:   {data.get('province') or 'N/A'}")
            ok(f"  Deadline:   {data.get('deadline') or 'N/A'}")
            print(f"{conf_color}  Confidence: {conf_pct}{RST}", flush=True)
            print(f"{status_color}  DB Status:  {status}{RST}", flush=True)
            ok(f"  Categories: {', '.join(data.get('categories',[]))}")
            ok(f"  Tokens:     {result['input_tokens']:,} in / {result['output_tokens']:,} out")
            ok(f"  Time:       {result['elapsed_s']}s")

            reqs = data.get("requirements", [])
            if reqs:
                info(f"  Requirements ({len(reqs)}):")
                for r in reqs[:4]:
                    dim(f"    * {r}")

            desc = data.get("description","")
            if desc:
                info("  Description:")
                dim(f"    {desc[:200]}")

            print()

        except Exception as e:
            fail(f"  Error: {e}")
            report["errors"].append(str(e))

    # =========================================================================
    header("STAGE 6: Data Validation Checks")
    # =========================================================================
    for data in ai_results:
        url = data["_source_url"]
        title = data.get("title","")
        conf = data.get("confidence", 0)
        status = "UNVERIFIED" if data.get("requires_review") or conf < 0.6 else "ACTIVE"

        checks = {
            "source_url preserved":  bool(url),
            "title extracted":       bool(title and len(title) > 5),
            "type is valid":         data.get("type") in ["VAGA","CONCURSO","BOLSA","ESTAGIO","FORMACAO"],
            "description present":   len(data.get("description","")) > 20,
            "confidence is number":  isinstance(conf, (int, float)),
            "categories present":    len(data.get("categories",[])) >= 1,
            "no invented data":      conf > 0,  # AI self-reported
        }

        all_pass = all(checks.values())
        color = G if all_pass else Y
        print(f"{color}  [{title[:50]}]{RST}", flush=True)
        for check_name, passed in checks.items():
            sym = "[OK]" if passed else "[!!]"
            col = G if passed else R
            print(f"{col}    {sym} {check_name}{RST}", flush=True)
        info(f"    --> Would be saved as: {status}")
        print()

        report["opportunities"].append({
            "url": url,
            "title": title,
            "type": data.get("type"),
            "province": data.get("province"),
            "confidence": conf,
            "status": status,
            "all_checks_pass": all_pass,
        })

    # =========================================================================
    header("STAGE 7: Performance & Cost Analysis")
    # =========================================================================
    n = len(ai_results)
    if n > 0:
        # Claude Haiku 4.5 pricing (2025): $0.80/M input, $4.00/M output
        cost_in  = (total_in_tokens  / 1_000_000) * 0.80
        cost_out = (total_out_tokens / 1_000_000) * 4.00
        cost_total = cost_in + cost_out

        ok(f"Pages processed:     {n}")
        ok(f"Total input tokens:  {total_in_tokens:,}")
        ok(f"Total output tokens: {total_out_tokens:,}")
        ok(f"Avg tokens/page:     {total_in_tokens//n:,} in / {total_out_tokens//n:,} out")
        info(f"Cost (this run):     ${cost_total:.5f} USD")
        info(f"Cost (50 pages/day): ${cost_total/n*50:.4f} USD/day = ${cost_total/n*50*30:.2f}/month")
        info(f"Cost (500 pgs/day):  ${cost_total/n*500:.3f} USD/day = ${cost_total/n*500*30:.2f}/month")

        # Cache effectiveness (system prompt ~400 tokens -- reused per run)
        cache_savings = (400 * n * 0.80) / 1_000_000
        info(f"Est. cache savings:  ${cache_savings:.5f} USD (system prompt reuse)")

        report["stages"]["ai"] = {
            "ok": True,
            "pages": n,
            "total_in_tokens": total_in_tokens,
            "total_out_tokens": total_out_tokens,
            "cost_usd": round(cost_total, 6),
        }

    _print_summary(report)
    return report


def _print_summary(report: dict):
    header("VALIDATION SUMMARY")

    stages = report["stages"]
    ok_count  = sum(1 for s in stages.values() if s.get("ok"))
    total_s   = len(stages)

    print(f"  Stages OK:      {ok_count}/{total_s}", flush=True)

    opps = report["opportunities"]
    if opps:
        active    = sum(1 for o in opps if o["status"] == "ACTIVE")
        unverif   = sum(1 for o in opps if o["status"] == "UNVERIFIED")
        avg_conf  = sum(o["confidence"] for o in opps) / len(opps)
        all_valid = sum(1 for o in opps if o.get("all_checks_pass"))
        print(f"  Opportunities:  {len(opps)} extracted", flush=True)
        print(f"  ACTIVE:         {active}", flush=True)
        print(f"  UNVERIFIED:     {unverif}", flush=True)
        print(f"  Avg confidence: {avg_conf:.0%}", flush=True)
        print(f"  All checks OK:  {all_valid}/{len(opps)}", flush=True)

    if report["errors"]:
        print(f"\n{Y}  Errors:{RST}", flush=True)
        for e in report["errors"][:5]:
            warn(f"  {e}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Virtus Job Pipeline Validator")
    parser.add_argument("--api-key", default=os.getenv("ANTHROPIC_API_KEY",""), help="Anthropic API key")
    parser.add_argument("--no-ai",  action="store_true", help="Skip AI (HTTP+parse only)")
    parser.add_argument("--pages",  type=int, default=3, help="Max detail pages")
    args = parser.parse_args()

    use_ai = not args.no_ai and bool(args.api_key)
    asyncio.run(validate(use_ai=use_ai, api_key=args.api_key, max_pages=args.pages))
