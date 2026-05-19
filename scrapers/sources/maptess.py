"""
MAPTESS Spider — Ministério da Administração Pública, Trabalho e Segurança Social.

Source: https://maptess.gov.ao
Type: Concursos Públicos, Vagas

Architecture notes:
- The MAPTESS portal is server-rendered (no JS needed)
- Announcements appear in the "Publicações" / "Concursos" section
- Some announcements are PDFs — we skip these for now (Fase 2B)
- We parse the listing page and follow each announcement link
- BeautifulSoup extracts the text, AI structures the data

Selector resilience: we try multiple CSS selector patterns.
If none match, the AI handles unstructured text as fallback.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from scrapers.base.browser import BrowserManager
from scrapers.base.http_client import ScraperHTTPClient
from scrapers.base.spider import BaseSpider, SourceConfig
from scrapers.config import settings
from scrapers.models import RawPage

# ─── Source Configuration ────────────────────────────────────────────────────

SOURCE_CONFIG = SourceConfig(
    id="maptess",
    name="MAPTSS",
    base_url="https://www.maptss.gov.ao",
    requires_js=False,
    is_active=True,
    schedule_cron="0 8,14,20 * * *",    # 3x daily
    tags=["concurso", "emprego", "governo"],
)

# Entry points — ordered by priority
ENTRY_URLS = [
    "https://www.maptss.gov.ao/concursos-publicos",
    "https://www.maptss.gov.ao/publicacoes",
    "https://www.maptss.gov.ao/vagas",
    "https://www.maptss.gov.ao/emprego",
    "https://www.maptss.gov.ao",
    "https://maptss.gov.ao",
]

# CSS selectors to find opportunity links on listing pages
# Multiple patterns for resilience against site redesigns
LINK_SELECTORS = [
    "article a[href]",
    ".post-title a[href]",
    ".entry-title a[href]",
    ".news-item a[href]",
    ".publication a[href]",
    ".concurso a[href]",
    "h2 a[href]",
    "h3 a[href]",
    ".item-title a[href]",
    "li.post a[href]",
]

# Selectors to extract body content from detail pages
CONTENT_SELECTORS = [
    "article .entry-content",
    "article .post-content",
    ".single-content",
    ".page-content",
    "main article",
    ".content-area",
    "#content",
    "main",
]

# Keywords that indicate an opportunity (used to filter relevant links)
OPPORTUNITY_KEYWORDS = [
    "concurso", "vaga", "bolsa", "estágio", "estagio",
    "recrutamento", "candidatura", "contratação", "emprego",
    "formação", "formacao", "admissão", "admissao",
    "trabalhador", "funcionario", "funcionário",
]

# Skip URLs that are clearly not opportunities
SKIP_PATTERNS = [
    r"/(categoria|category|tag|author|page)/",
    r"\.(pdf|doc|docx|xls|xlsx|ppt)$",
    r"/(wp-content|wp-admin|feed|rss)/",
    r"/(sobre|about|contacto|contact|privacidade)/",
    r"^#",
]


class MaptessSpider(BaseSpider):
    """
    Spider for maptess.gov.ao — Angola's Ministry of Public Administration.

    Scraping approach:
    1. Visit each ENTRY_URL in order until we find opportunity links
    2. Filter links by keyword relevance
    3. Fetch each detail page and extract full text
    4. Pass text to AI pipeline for structured extraction
    """

    config = SOURCE_CONFIG

    async def discover_urls(
        self,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> list[str]:
        """Find opportunity URLs from listing pages."""
        found_urls: list[str] = []

        for entry_url in ENTRY_URLS:
            if len(found_urls) >= settings.MAX_ITEMS_PER_SOURCE:
                break

            try:
                response = await client.get(entry_url)
                if response.status_code != 200:
                    continue

                links = self._extract_links(response.text, base_url=entry_url)
                self.log("info", "Found {} candidates on {}", len(links), entry_url)

                for link in links:
                    if link not in found_urls:
                        found_urls.append(link)

                if found_urls:
                    break  # Got results from this entry point

            except httpx.HTTPStatusError as e:
                self.log("warning", "HTTP {} for {}", e.response.status_code, entry_url)
            except Exception as e:
                self.log("error", "Error discovering from {}: {}", entry_url, e)

        # Pagination: follow "next page" links
        if found_urls:
            found_urls = await self._follow_pagination(found_urls, client, ENTRY_URLS[0])

        self.log("info", "Discovered {} URLs to scrape", len(found_urls))
        return found_urls[: settings.MAX_ITEMS_PER_SOURCE]

    async def fetch_page(
        self,
        url: str,
        client: ScraperHTTPClient,
        browser: BrowserManager | None = None,
    ) -> RawPage:
        """Fetch a single detail page."""
        try:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "lxml")
            title = self._extract_title(soup)

            return RawPage(
                url=url,
                source_name=self.source_name,
                source_id=self.source_id,
                html=response.text,
                title=title,
                http_status=response.status_code,
            )
        except Exception as e:
            self.log("error", "Failed to fetch {}: {}", url, e)
            return RawPage(
                url=url,
                source_name=self.source_name,
                source_id=self.source_id,
                http_status=0,
            )

    async def parse_page(self, raw: RawPage) -> RawPage:
        """
        Extract meaningful text from the HTML.
        Tries targeted content selectors first, falls back to full body.
        Strips navigation, headers, footers.
        """
        if not raw.html:
            return raw

        soup = BeautifulSoup(raw.html, "lxml")

        # Remove noise elements
        for noise in soup.select(
            "nav, header, footer, .menu, .sidebar, script, style, "
            ".cookie-banner, .breadcrumb, .social-share, .comments, "
            ".widget, .advertisement, #wpadminbar"
        ):
            noise.decompose()

        # Try targeted content selectors
        content_el = None
        for selector in CONTENT_SELECTORS:
            content_el = soup.select_one(selector)
            if content_el:
                self.log("debug", "Content found with selector: {}", selector)
                break

        # Fallback: use the body
        if not content_el:
            content_el = soup.find("body") or soup

        text = self._clean_text(content_el.get_text(separator="\n"))

        # Prepend title for context
        if raw.title and raw.title not in text[:200]:
            text = f"{raw.title}\n\n{text}"

        raw.text = text
        self.log(
            "debug",
            "Parsed {} chars from {}",
            len(text),
            raw.url,
        )
        return raw

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(base_url).netloc
        found: list[str] = []

        for selector in LINK_SELECTORS:
            for anchor in soup.select(selector):
                href = anchor.get("href", "")
                if not href:
                    continue

                # Resolve relative URLs
                full_url = urljoin(base_url, str(href))
                parsed = urlparse(full_url)

                # Stay on same domain
                if parsed.netloc != base_domain:
                    continue

                # Skip unwanted patterns
                if any(re.search(p, full_url, re.I) for p in SKIP_PATTERNS):
                    continue

                # Only include if keyword-relevant
                link_text = (anchor.get_text() + " " + full_url).lower()
                if not any(kw in link_text for kw in OPPORTUNITY_KEYWORDS):
                    continue

                if full_url not in found:
                    found.append(full_url)

        # If no keyword-filtered links found, fall back to all internal links
        # (the AI will filter out irrelevant ones by returning low confidence)
        if not found:
            self.log("debug", "No keyword-filtered links found, using all internal links")
            for anchor in soup.find_all("a", href=True):
                href = anchor.get("href", "")
                full_url = urljoin(base_url, str(href))
                parsed = urlparse(full_url)
                if (
                    parsed.netloc == base_domain
                    and not any(re.search(p, full_url, re.I) for p in SKIP_PATTERNS)
                    and full_url not in found
                ):
                    found.append(full_url)

        return found[:settings.MAX_ITEMS_PER_SOURCE * 2]  # buffer for dedup filtering

    async def _follow_pagination(
        self,
        current_urls: list[str],
        client: ScraperHTTPClient,
        listing_url: str,
    ) -> list[str]:
        """Follow 'próxima página' links on listing pages."""
        all_urls = list(current_urls)

        try:
            response = await client.get(listing_url)
            soup = BeautifulSoup(response.text, "lxml")

            # Common pagination selectors
            next_patterns = [
                "a.next", "a[rel='next']",
                ".pagination a:last-child",
                ".nav-next a", "a.next-page",
                "a:contains('Próxima')", "a:contains('Seguinte')",
            ]

            pages_visited = 1
            while pages_visited < settings.MAX_PAGES_PER_SOURCE:
                next_link = None
                for sel in next_patterns:
                    try:
                        el = soup.select_one(sel)
                        if el and el.get("href"):
                            next_link = urljoin(listing_url, str(el["href"]))
                            break
                    except Exception:
                        continue

                if not next_link:
                    break

                try:
                    resp = await client.get(next_link)
                    new_links = self._extract_links(resp.text, base_url=next_link)
                    added = [u for u in new_links if u not in all_urls]
                    all_urls.extend(added)
                    self.log("debug", "Pagination page {}: +{} URLs", pages_visited + 1, len(added))
                    soup = BeautifulSoup(resp.text, "lxml")
                    pages_visited += 1
                except Exception as e:
                    self.log("warning", "Pagination error: {}", e)
                    break

        except Exception as e:
            self.log("debug", "Pagination discovery failed: {}", e)

        return all_urls

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        # og:title is most reliable on WordPress sites where H1 shows generic labels
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return str(og["content"]).strip()[:500]
        for selector in ["h1.entry-title", "h1.post-title", ".post-title", "h1", "title"]:
            el = soup.select_one(selector)
            if el:
                title = el.get_text(strip=True)
                # Skip generic CMS labels
                if title.lower() not in ("recentes", "recent", "publicacoes", "noticias"):
                    return title[:500]
        return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        """Collapse whitespace, remove boilerplate."""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            # Skip very short lines (navigation fragments)
            if len(line) > 3:
                lines.append(line)
        text = "\n".join(lines)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
