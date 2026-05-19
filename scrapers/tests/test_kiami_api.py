"""
Kiami API Explorer — Find JdA opportunity sections and extract articles.

The Kiami backend (kiami-ja-back.kiamisoft.ao) is the API that powers
jornaldeangola.ao. We can query it directly for articles by section.

This bypasses PressReader entirely and gets HTML/JSON content directly.
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

import httpx

KIAMI_BASE = "https://kiami-ja-back.kiamisoft.ao"
SESSION_FILE = Path(os.environ.get("JDA_SESSION_FILE", "scrapers/sessions/jda_session.json"))
OUTPUT_DIR = Path(__file__).parent / "output"

def p(*args):
    try: print(*args)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii","replace").decode("ascii"))

def get_jwt() -> str:
    """Get JWT from saved session localStorage."""
    if not SESSION_FILE.exists():
        return ""
    data = json.loads(SESSION_FILE.read_text())
    storage = data.get("storage_state", data)
    for origin in storage.get("origins", []):
        if "jornaldeangola" in origin.get("origin", ""):
            for item in origin.get("localStorage", []):
                if item.get("name") == "_token_accesso":
                    return item.get("value", "")
    return ""


async def explore_kiami() -> None:
    jwt = get_jwt()
    if not jwt:
        p("ERROR: No JWT in session. Run test_jda_auth.py first.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://jornaldeangola.ao",
        "Referer": "https://jornaldeangola.ao/",
    }

    p("=" * 65)
    p("  Kiami API Explorer — JdA News Sections")
    p("=" * 65)
    p(f"  JWT: {jwt[:30]}...")

    async with httpx.AsyncClient(timeout=30, headers=headers) as client:

        # ─── 1. Get all news sections/menu ────────────────────────────────────
        p("\n[1] Getting news menu (all sections)...")
        r = await client.get(f"{KIAMI_BASE}/cms/api/v1/noticias/menu")
        if r.status_code == 200:
            menu = r.json()
            p(f"  Status: {r.status_code}")
            sections = menu.get("objecto", [])
            p(f"  Sections ({len(sections)}):")
            for sec in sections:
                p(f"    id={sec.get('idTipoNoticia',0):3d} | {sec.get('categoria','?'):20s} | count={sec.get('totalNoticias',0)}")
        else:
            p(f"  Status: {r.status_code}")

        # ─── 2. Get all sub-sections ──────────────────────────────────────────
        p("\n[2] Getting section details (seccoesNoticias)...")
        r2 = await client.get(f"{KIAMI_BASE}/cms/api/v1/seccoesNoticias/1")
        if r2.status_code == 200:
            data = r2.json().get("objecto", [])
            p(f"  All sub-sections ({len(data)}):")
            for sec in data:
                sid = sec.get("idSeccao", 0)
                name = sec.get("nome", "?")
                parent = sec.get("idSeccaoPai", 0)
                p(f"    idSeccao={sid:4d} | parent={parent:3d} | {name}")

        # ─── 3. Search for opportunity sections ───────────────────────────────
        p("\n[3] Searching for opportunity-related sections...")
        opportunity_keywords = [
            "concurso", "emprego", "recrutamento", "vaga", "bolsa",
            "estagi", "licitac", "edital", "especial", "classificad",
        ]
        r3 = await client.get(f"{KIAMI_BASE}/cms/api/v1/seccoesNoticias/1")
        if r3.status_code == 200:
            all_secs = r3.json().get("objecto", [])
            found = []
            for sec in all_secs:
                name = sec.get("nome", "").lower()
                if any(kw in name for kw in opportunity_keywords):
                    found.append(sec)
                    p(f"  MATCH: id={sec['idSeccao']} | {sec['nome']}")
            if not found:
                p("  No exact matches — checking all section names:")
                for sec in all_secs:
                    p(f"    {sec.get('idSeccao',0):4d} | {sec.get('nome','?')}")

        # ─── 4. Try known sections for each opportunity type ──────────────────
        p("\n[4] Sampling articles from key sections...")
        test_sections = [
            (78, "Política (from trace)"),
            (53, "Section 53"),
            (52, "Section 52"),
            (44, "Section 44"),
            (45, "Section 45"),
            (46, "Section 46"),
            (73, "Section 73"),
            (74, "Section 74"),
        ]

        for sec_id, label in test_sections:
            r4 = await client.post(
                f"{KIAMI_BASE}/cms/api/v1/noticias",
                json={"activo": True, "idsSecoes": [sec_id], "itensPorPagina": 2}
            )
            if r4.status_code == 200:
                items = r4.json().get("objecto", [])
                if items:
                    titles = [i.get("titulo", "?")[:50] for i in items]
                    p(f"  Section {sec_id:4d} ({label}): {titles}")
                else:
                    p(f"  Section {sec_id:4d}: (empty)")
            await asyncio.sleep(0.5)

        # ─── 5. Get a full article ─────────────────────────────────────────────
        p("\n[5] Getting full article content (first article from section 78)...")
        r5 = await client.post(
            f"{KIAMI_BASE}/cms/api/v1/noticias",
            json={"activo": True, "idsSecoes": [78], "itensPorPagina": 1}
        )
        if r5.status_code == 200:
            items = r5.json().get("objecto", [])
            if items:
                first = items[0]
                article_id = first.get("idNoticia")
                p(f"  First article: id={article_id} title={first.get('titulo','?')[:60]}")

                # Get full article
                r6 = await client.get(f"{KIAMI_BASE}/cms/api/v1/noticias/{article_id}/pt")
                if r6.status_code == 200:
                    article = r6.json().get("objecto", {})
                    p(f"  Full article fields: {list(article.keys())}")
                    p(f"  Text preview: {str(article.get('noticia',''))[:200]}")
                else:
                    p(f"  Article fetch status: {r6.status_code}")

        # ─── 6. Try to find today's opportunity articles ──────────────────────
        p("\n[6] Searching for today's opportunity articles (17/05/2026)...")
        r7 = await client.post(
            f"{KIAMI_BASE}/cms/api/v1/noticias",
            json={
                "activo": True,
                "dataInicio": "2026-05-17",
                "dataFim": "2026-05-17",
                "itensPorPagina": 50,
            }
        )
        if r7.status_code == 200:
            items = r7.json().get("objecto", [])
            p(f"  Articles for 17/05/2026: {len(items)}")
            for item in items[:10]:
                title = item.get("titulo", "?")[:60]
                cats = [c.get("nome","?") for c in item.get("categorias",[])]
                p(f"    [{item.get('idNoticia')}] {title} | cats={cats}")
        else:
            p(f"  Status: {r7.status_code}")

        # ─── 7. Search with opportunity keywords ──────────────────────────────
        p("\n[7] Keyword search for 'concurso'...")
        r8 = await client.post(
            f"{KIAMI_BASE}/cms/api/v1/noticias",
            json={"activo": True, "pesquisa": "concurso", "itensPorPagina": 10}
        )
        if r8.status_code == 200:
            items = r8.json().get("objecto", [])
            p(f"  Results: {len(items)}")
            for item in items[:5]:
                p(f"    [{item.get('idNoticia')}] {item.get('titulo','?')[:60]}")
        else:
            p(f"  Status: {r8.status_code}")

    p("\n  Saving full menu to output...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    result = {
        "menu": r.json() if r.status_code == 200 else {},
        "sections": r3.json() if r3.status_code == 200 else {},
    }
    (OUTPUT_DIR / "kiami_api_exploration.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    p("  Done.")


if __name__ == "__main__":
    asyncio.run(explore_kiami())
