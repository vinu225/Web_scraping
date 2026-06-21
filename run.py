"""
run.py
=======
Command-line entry point for the News Scraper system.

Examples
--------
Search DuckDuckGo for two keywords::

    python run.py --keywords "AI regulation" "climate change" --ddg

Search NewsAPI (requires NEWSAPI_KEY in .env)::

    python run.py --keywords "machine learning" --newsapi

Scrape specific URLs directly::

    python run.py --urls https://example.com/article1 https://example.com/article2

Combined run::

    python run.py --keywords "OpenAI" --ddg --newsapi --lang en --workers 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on the Python path when run from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pipeline.orchestrator import Orchestrator
from src.utils.logger import get_logger

logger = get_logger("run")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="news_scraper",
        description="Production-ready news article scraping system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    p.add_argument(
        "--keywords", "-k",
        nargs="+",
        metavar="KEYWORD",
        help="Search keywords (can be quoted phrases)",
    )
    p.add_argument(
        "--urls", "-u",
        nargs="+",
        metavar="URL",
        help="Direct article URLs to scrape",
    )
    p.add_argument(
        "--ddg",
        action="store_true",
        default=False,
        help="Enable DuckDuckGo search (default: disabled)",
    )
    p.add_argument(
        "--newsapi",
        action="store_true",
        default=False,
        help="Enable NewsAPI search (requires NEWSAPI_KEY)",
    )
    p.add_argument(
        "--newsapi-key",
        metavar="KEY",
        help="Override NewsAPI key from .env",
    )
    p.add_argument(
        "--sources",
        nargs="+",
        metavar="SOURCE_ID",
        help="NewsAPI source IDs to filter by",
    )
    p.add_argument(
        "--lang",
        default="en",
        metavar="CODE",
        help="ISO 639-1 language filter (default: en)",
    )
    p.add_argument(
        "--from-date",
        metavar="YYYY-MM-DD",
        help="NewsAPI earliest publication date",
    )
    p.add_argument(
        "--to-date",
        metavar="YYYY-MM-DD",
        help="NewsAPI latest publication date",
    )
    p.add_argument(
        "--max-results",
        type=int,
        metavar="N",
        help="Maximum DuckDuckGo results per keyword",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=5,
        metavar="N",
        help="Thread-pool size for concurrent extraction (default: 5)",
    )
    p.add_argument(
        "--min-body",
        type=int,
        default=200,
        metavar="CHARS",
        help="Minimum article body character count (default: 200)",
    )
    p.add_argument(
        "--allow-social",
        action="store_true",
        default=False,
        help="Enable social media domains (Reddit, Twitter, etc.) in searches from the start (default: disabled)",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.keywords and not args.urls:
        parser.error("Provide at least one --keywords or --urls argument.")

    if not args.ddg and not args.newsapi and not args.urls:
        parser.error(
            "No data source selected. Use --ddg, --newsapi, or provide --urls."
        )

    logger.info("Starting news scraper | keywords=%s | ddg=%s | newsapi=%s",
                args.keywords, args.ddg, args.newsapi)

    orchestrator = Orchestrator(
        max_workers=args.workers,
        language_filter=args.lang if args.lang else None,
        min_body_length=args.min_body,
    )

    stats = orchestrator.run(
        keywords=args.keywords or [],
        direct_urls=args.urls or [],
        use_duckduckgo=args.ddg,
        use_newsapi=args.newsapi,
        newsapi_key=args.newsapi_key,
        newsapi_sources=args.sources,
        newsapi_language=args.lang or "en",
        newsapi_from_date=args.from_date,
        newsapi_to_date=args.to_date,
        ddg_max_results=args.max_results,
        allow_social=args.allow_social,
    )

    sys.exit(0 if stats.successful > 0 or stats.total_urls == 0 else 1)


if __name__ == "__main__":
    main()
