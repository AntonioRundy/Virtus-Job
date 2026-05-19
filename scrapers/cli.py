"""
Virtus Job Scraper CLI

Usage examples:
  python -m scrapers.cli run                          # run all active sources
  python -m scrapers.cli run --source maptess         # run specific source
  python -m scrapers.cli run --dry-run                # test without saving
  python -m scrapers.cli list-sources                 # show registered sources
  python -m scrapers.cli test-ai --url <url>          # test AI extraction on URL
  python -m scrapers.cli test-fetch --url <url>       # test fetch + parse only
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from scrapers.sources import REGISTRY

app = typer.Typer(name="virtus-scraper", help="Virtus Job intelligent scraper")
console = Console()


def _configure_logging(verbose: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[spider]}</cyan> | "
            "{message}"
        ),
        filter=lambda r: "spider" in r["extra"],
        colorize=True,
    )
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "{message}"
        ),
        filter=lambda r: "spider" not in r["extra"],
        colorize=True,
    )
    # File log for persistence
    logger.add(
        "logs/scraper_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
    )


@app.command()
def run(
    source: list[str] = typer.Option(
        ["all"], "--source", "-s", help="Source IDs to run (use 'all' for all active)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Parse and extract but don't save to DB"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the scraping pipeline for one or more sources."""
    _configure_logging(verbose)

    from scrapers.runner import ScrapingRunner

    runner = ScrapingRunner(dry_run=dry_run)
    mode = "[DRY RUN] " if dry_run else ""
    sources_str = ", ".join(source)
    logger.info("{}Starting Virtus Job Scraper — sources: {}", mode, sources_str)

    results = asyncio.run(runner.run(source_ids=source))

    if not results:
        console.print("[red]No results — check source IDs or active status[/red]")
        raise typer.Exit(1)

    # Summary table
    table = Table(title="Scraping Results")
    table.add_column("Source", style="cyan")
    table.add_column("Status")
    table.add_column("New", style="green")
    table.add_column("Duplicates", style="yellow")
    table.add_column("Failed", style="red")
    table.add_column("Duration")

    for r in results:
        status = "✓ OK" if r.success else "✗ FAIL"
        table.add_row(
            r.source_name,
            status,
            str(r.items_new),
            str(r.items_skipped_dup),
            str(r.items_failed),
            f"{r.duration_seconds:.1f}s" if r.duration_seconds else "—",
        )

    console.print(table)


@app.command("list-sources")
def list_sources() -> None:
    """List all registered scraping sources."""
    table = Table(title="Registered Sources")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Active")
    table.add_column("Requires JS")
    table.add_column("Schedule")
    table.add_column("Base URL", style="dim")

    for sid, cls in REGISTRY.items():
        cfg = cls.config
        table.add_row(
            sid,
            cfg.name,
            "✓" if cfg.is_active else "✗",
            "✓" if cfg.requires_js else "✗",
            cfg.schedule_cron,
            cfg.base_url,
        )

    console.print(table)


@app.command("test-fetch")
def test_fetch(
    url: str = typer.Argument(..., help="URL to fetch and parse"),
    source: str = typer.Option("maptess", help="Source spider to use for parsing"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch and parse a single URL without AI extraction (for debugging)."""
    _configure_logging(verbose)

    async def _run():
        from scrapers.base.http_client import ScraperHTTPClient
        from scrapers.sources import REGISTRY

        if source not in REGISTRY:
            console.print(f"[red]Unknown source: {source}[/red]")
            return

        spider_cls = REGISTRY[source]
        spider = spider_cls()

        async with ScraperHTTPClient() as http:
            raw = await spider.fetch_page(url, http)
            raw = await spider.parse_page(raw)

        console.print(f"\n[cyan]URL:[/cyan] {raw.url}")
        console.print(f"[cyan]Title:[/cyan] {raw.title}")
        console.print(f"[cyan]Status:[/cyan] {raw.http_status}")
        console.print(f"[cyan]Text length:[/cyan] {len(raw.text or '')} chars")
        console.print("\n[cyan]First 1000 chars of text:[/cyan]")
        console.print(raw.text[:1000] if raw.text else "(empty)")

    asyncio.run(_run())


@app.command("test-ai")
def test_ai(
    url: str = typer.Argument(..., help="URL to fetch, parse and extract with AI"),
    source: str = typer.Option("maptess", help="Source spider to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Full pipeline test for a single URL — shows AI extraction result."""
    _configure_logging(verbose)

    async def _run():
        from scrapers.base.http_client import ScraperHTTPClient
        from scrapers.pipeline.ai_extractor import AIExtractor
        from scrapers.pipeline.normalizer import Normalizer
        from scrapers.sources import REGISTRY

        if source not in REGISTRY:
            console.print(f"[red]Unknown source: {source}[/red]")
            return

        spider = REGISTRY[source]()
        ai = AIExtractor()
        normalizer = Normalizer()

        async with ScraperHTTPClient() as http:
            raw = await spider.fetch_page(url, http)
            raw = await spider.parse_page(raw)

        console.print(f"\n[cyan]Fetched:[/cyan] {url}")
        console.print(f"[cyan]Title:[/cyan] {raw.title}")
        console.print(f"[cyan]Text chars:[/cyan] {len(raw.text or '')}")

        console.print("\n[yellow]Running AI extraction...[/yellow]")
        extracted = await ai.extract(raw)

        console.print("\n[green]AI Extraction Result:[/green]")
        console.print(f"  Title:      {extracted.title}")
        console.print(f"  Type:       {extracted.type}")
        console.print(f"  Org:        {extracted.organization}")
        console.print(f"  Province:   {extracted.province}")
        console.print(f"  Deadline:   {extracted.deadline}")
        console.print(f"  Confidence: {extracted.confidence:.2f}")
        console.print(f"  Review:     {extracted.requires_review}")
        console.print(f"  Categories: {extracted.categories}")
        console.print(f"  Desc:       {extracted.description[:200]}")

        normalised = normalizer.normalise(raw, extracted)
        console.print(f"\n[green]Normalised Status:[/green] {normalised.status}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
