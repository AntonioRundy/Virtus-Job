"""
Source registry — all spiders are registered here.
The runner imports this to discover available sources.
"""
from scrapers.sources.jornal_angola import JornalAngolaSpider
from scrapers.sources.maptess import MaptessSpider

REGISTRY: dict[str, type] = {
    "maptess": MaptessSpider,
    "jornal_angola": JornalAngolaSpider,
}

__all__ = ["REGISTRY"]
