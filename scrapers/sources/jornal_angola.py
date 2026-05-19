"""
Jornal de Angola Spider — Authenticated Premium Source.

Source:      https://jornaldeangola.ao
Trust level: INSTITUTIONAL (state-owned newspaper, Angola's paper of record)
Auth:        Email + password (subscriber session via Playwright)
JS required: Yes (React/JS-rendered frontend)

Editorial policy:
  - Only extract structured metadata (title, type, deadline, requirements).
  - Never replicate full article content — source_url always points back.
  - Responsible use of subscriber access: structure opportunities only.

Sections scraped (subset of newspaper focused on opportunities):
  /ao/noticias/concursos-publicos   — concursos públicos
  /ao/noticias/emprego              — vagas de emprego
  /ao/noticias/bolsas               — bolsas de estudo
  /ao/noticias/licitacoes           — licitações e editais

Requirements:
  JDA_EMAIL and JDA_PASSWORD must be set in .env
  Playwright must be installed (playwright install chromium)
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger

from scrapers.auth.jda_authenticator import AuthenticationError, JdaAuthenticator
from scrapers.base.authenticated_browser import AuthenticatedBrowserManager
from scrapers.base.browser import BrowserManager
from scrapers.base.http_client import ScraperHTTPClient
from scrapers.base.spider import BaseSpider, SourceConfig
from scrapers.config import settings
from scrapers.models import RawPage

# ─── Source configuration ────────────────────────────────────────────────────

SOURCE_CONFIG = SourceConfig(
    id="jornal_angola",
    name="Jornal de Angola",
    base_url=settings.JDA_BASE_URL,
    requires_js=True,
    is_active=True,
    schedule_cron="0 6,18 * * *",   # 2× daily (manhã + tarde)
    rate_limit_delay=5.0,            # Conservative — newspaper, not a jobs board
    tags=["concurso", "emprego", "bolsa", "jornal", "oficial"],
)

# ─── Opportunity sections to scrape ─────────────────────────────────────────

OPPORTUNITY_SECTIONS: list[dict] = [
    {
        "url": f"{settings.JDA_BASE_URL}/ao/noticias/concursos-publicos",
        "hint_type": "CONCURSO",
        "label": "Concursos Públicos",
    },
    {
        "url": f"{settings.JDA_BASE_URL}/ao/noticias/emprego",
        "hint_type": "VAGA",
        "label": "Emprego",
    },
    {
        "url": f"{settings.JDA_BASE_URL}/ao/noticias/bolsas",
        "hint_type": "BOLSA",
        "label": "Bolsas",
    },
    {
        "url": f"{settings.JDA_BASE_URL}/ao/noticias/licitacoes",
        "hint_type": "CONCURSO",
        "label": "Licitações",
    },
]

# ─── Keyword filter — only extract opportunity-related articles ───────────────
# Filters noise (general news, sports, politics) from opportunity listings.

OPPORTUNITY_KEYWORDS: frozenset[str] = frozenset({
    "concurso", "recrutamento", "vaga", "emprego", "bolsa", "estágio",
    "estagio", "licitação", "licitacao", "edital", "candidatura",
    "contratação", "contratacao", "oportunidade", "inscricão", "inscricao",
    "processo seletivo", "selecção", "selecao", "admissão", "admissao",
    "abertura de concurso", "convite à manifestação",
    "aquisição de bens", "aquisicão de servicos",
})

# Maximum characters of article text to send to AI (responsible use)
MAX_ARTICLE_TEXT_CHARS = 2500


class JornalAngolaSpider(BaseSpider):
    """
    Authenticated spider for the Jornal de Angola premium subscription.

    Authentication flow (transparent to the pipeline):
      1. Load session from scrapers/sessions/jda_session.json
      2. If session missing or too old: run Playwright login
      3. Inject session cookies into all browser contexts
      4. On 401/403 responses: re-authenticate once, then continue

    Content policy:
      - Extracts: title, ~2500 chars of text, publication date, URL
      - Does NOT cache: full article body, author, premium content
      - Always stores: exact source_url pointing to original article
    """

    config = SOURCE_CONFIG

    def __init__(self) -> None:
        super().__init__()
        self._authenticator = JdaAuthenticator()
        self._auth_browser: AuthenticatedBrowserManager | None = None
        self._authenticated = False

    # ─── BaseSpider interface ─────────────────────────────────────────────────

    async def discover_urls(
        self,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> list[str]:
        """
        Authenticate, then scrape each opportunity section listing.
        Returns deduplicated article URLs.
        """
        if not settings.JDA_EMAIL or not settings.JDA_PASSWORD:
            logger.error(
                "JornalAngola spider skipped — JDA_EMAIL and JDA_PASSWORD not set in .env. "
                "Add your subscriber credentials to enable this source."
            )
            return []

        try:
            self._auth_browser = await self._get_auth_browser()
        except AuthenticationError as exc:
            logger.error("JdA authentication failed: {}", exc)
            return []

        all_urls: list[str] = []

        for section in OPPORTUNITY_SECTIONS:
            try:
                urls = await self._scrape_section_listing(section)
                logger.info(
                    "JdA [{}]: found {} opportunity URLs",
                    section["label"],
                    len(urls),
                )
                all_urls.extend(urls)
                await asyncio.sleep(settings.rate_limit_delay
                    if hasattr(settings, "rate_limit_delay")
                    else 4.0)
            except Exception as exc:
                logger.warning("JdA section {} failed: {}", section["label"], exc)
                continue

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)

        logger.info("JdA: {} unique opportunity URLs discovered.", len(unique))
        return unique[:settings.MAX_ITEMS_PER_SOURCE]

    async def fetch_page(
        self,
        url: str,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> RawPage:
        """Fetch one article page with authenticated browser."""
        if not self._auth_browser:
            # Should not happen if discover_urls ran first
            self._auth_browser = await self._get_auth_browser()

        try:
            html, status = await self._auth_browser.get_page_html_authenticated(url)

            if status in (401, 403):
                logger.warning("JdA: HTTP {} on {} — re-authenticating.", status, url)
                self._authenticator.invalidate()
                self._auth_browser = await self._get_auth_browser()
                html, status = await self._auth_browser.get_page_html_authenticated(url)

            return RawPage(
                url=url,
                source_name=self.source_name,
                source_id=self.source_id,
                html=html,
                http_status=status,
                requires_js=True,
            )
        except Exception as exc:
            logger.error("JdA fetch failed for {}: {}", url, exc)
            return RawPage(
                url=url,
                source_name=self.source_name,
                source_id=self.source_id,
                http_status=0,
            )

    async def parse_page(self, raw: RawPage) -> RawPage:
        """
        Extract structured text from the article HTML.

        Extracts (responsible use — subscriber content not cached):
          - Article title
          - Publication date
          - First ~2500 chars of article body (enough for AI classification)
        """
        if not raw.html:
            return raw

        soup = BeautifulSoup(raw.html, "html.parser")

        # ─── Title ───────────────────────────────────────────────────────────
        raw.title = self._extract_title(soup)

        # ─── Article text — truncated for responsible use ────────────────────
        raw.text = self._extract_article_text(soup, raw.title or "")

        # ─── Quick keyword check — skip if not opportunity-related ───────────
        if raw.text and not self._is_opportunity_content(raw.text):
            logger.debug("JdA: non-opportunity content skipped → {}", raw.url[:80])
            raw.text = None  # pipeline will skip pages without text

        return raw

    # ─── Internal helpers ─────────────────────────────────────────────────────

    async def _get_auth_browser(self) -> AuthenticatedBrowserManager:
        """Ensure we have an authenticated browser manager ready."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )

        storage_state = await self._authenticator.ensure_authenticated(browser)

        auth_mgr = AuthenticatedBrowserManager(storage_state=storage_state)
        auth_mgr._playwright = pw     # type: ignore[attr-defined]
        auth_mgr._browser = browser   # type: ignore[attr-defined]
        return auth_mgr

    async def _scrape_section_listing(self, section: dict) -> list[str]:
        """
        Scrape one listing page and return article URLs.
        Handles pagination up to settings.MAX_PAGES_PER_SOURCE pages.
        """
        urls: list[str] = []
        page_url = section["url"]
        base = settings.JDA_BASE_URL

        for page_num in range(1, settings.MAX_PAGES_PER_SOURCE + 1):
            html, status = await self._auth_browser.get_page_html_authenticated(  # type: ignore[union-attr]
                page_url
            )
            if status not in (200, 304) or not html:
                break

            page_urls = self._extract_article_urls(html, base)
            if not page_urls:
                break  # no more results

            urls.extend(page_urls)

            # Find next page link
            next_url = self._find_next_page(html, base)
            if not next_url or next_url == page_url:
                break
            page_url = next_url
            await asyncio.sleep(settings.REQUEST_DELAY_MAX)

        return urls

    def _extract_article_urls(self, html: str, base_url: str) -> list[str]:
        """Extract article detail URLs from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []

        # Common patterns for newspaper article links
        selectors = [
            "article a[href]",
            ".article-item a[href]",
            ".news-item a[href]",
            "h2 a[href]",
            "h3 a[href]",
            ".entry-title a[href]",
            ".post-title a[href]",
        ]

        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get("href", "")
                    if href:
                        url = urljoin(base_url, str(href))
                        if self._is_valid_article_url(url, base_url):
                            urls.append(url)
                if urls:
                    break  # found results with this selector, no need to try others

        # Fallback: all internal links that look like articles
        if not urls:
            for link in soup.find_all("a", href=True):
                href = str(link["href"])
                url = urljoin(base_url, href)
                if self._is_valid_article_url(url, base_url):
                    urls.append(url)

        return list(dict.fromkeys(urls))  # deduplicate, preserve order

    def _find_next_page(self, html: str, base_url: str) -> str | None:
        """Extract pagination 'next page' URL."""
        soup = BeautifulSoup(html, "html.parser")
        next_link = (
            soup.find("a", rel="next")
            or soup.find("a", class_=re.compile(r"next|siguiente|proximo", re.I))
            or soup.find("a", string=re.compile(r"próximo|seguinte|next|›|»", re.I))
        )
        if next_link and next_link.get("href"):  # type: ignore[union-attr]
            return urljoin(base_url, str(next_link["href"]))  # type: ignore[union-attr]
        return None

    def _is_valid_article_url(self, url: str, base_url: str) -> bool:
        """True if url looks like a detail article from the same domain."""
        parsed = urlparse(url)
        base_parsed = urlparse(base_url)
        if parsed.netloc != base_parsed.netloc:
            return False
        # Must have a meaningful path (not root or category page)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        return len(parts) >= 2 and not url.endswith(("/", "#"))

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        """Extract article title from HTML."""
        for selector in ["h1.article-title", "h1.entry-title", "h1.post-title", "h1", ".article-title"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 10:
                    return text[:500]
        # Fallback: <title> tag
        title_tag = soup.find("title")
        if title_tag:
            t = title_tag.get_text(strip=True)
            # Remove site name suffix
            t = re.sub(r"\s*[-|–]\s*Jornal de Angola.*$", "", t, flags=re.I).strip()
            return t[:500] if t else None
        return None

    def _extract_article_text(self, soup: BeautifulSoup, title: str) -> str | None:
        """
        Extract truncated article text.

        Responsible use: we extract at most MAX_ARTICLE_TEXT_CHARS characters
        of the article body — enough for AI to classify and extract structured
        data, but not enough to replicate premium content.
        """
        # Remove non-content elements
        for tag in soup.select("nav, header, footer, .ads, .advertisement, script, style, .related"):
            tag.decompose()

        # Try common article body selectors
        body = None
        for selector in [
            "article .article-body",
            "article .entry-content",
            "article .post-content",
            ".article-content",
            ".story-body",
            "article",
            ".content-body",
        ]:
            el = soup.select_one(selector)
            if el:
                body = el.get_text(separator=" ", strip=True)
                break

        if not body:
            # Last resort: all paragraph text
            paras = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
            body = " ".join(paras)

        if not body:
            return None

        # Normalise whitespace
        body = re.sub(r"\s+", " ", body).strip()

        # Truncate — responsible use
        if len(body) > MAX_ARTICLE_TEXT_CHARS:
            body = body[:MAX_ARTICLE_TEXT_CHARS] + "…"

        # Prepend title if not already in text
        if title and title.lower() not in body.lower():
            body = f"{title}\n\n{body}"

        return body

    def _is_opportunity_content(self, text: str) -> bool:
        """Return True if the article text appears to be about an opportunity."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in OPPORTUNITY_KEYWORDS)
