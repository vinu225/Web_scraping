"""
src/pipeline/orchestrator.py
==============================
Top-level orchestrator: ties together DuckDuckGo search, NewsAPI fetching,
and direct URL input into a single high-level ``run()`` call.

Usage example::

    from src.pipeline.orchestrator import Orchestrator

    orch = Orchestrator()
    stats = orch.run(
        keywords=["AI regulation"],
        use_duckduckgo=True,
        use_newsapi=True,
        direct_urls=["https://example.com/article"],
        language_filter="en",
    )
    print(stats)
"""

from __future__ import annotations

from typing import Optional

from config.settings import settings
from src.crawler.duplicate_checker import DuplicateChecker
from src.crawler.url_collector import URLCollector
from src.newsapi.news_fetcher import NewsFetcher
from src.newsapi.newsapi_client import NewsAPIClient
from src.pipeline.scraping_pipeline import ScrapingPipeline
from src.schemas.article_schema import ArticleSource, DuckDuckGoResult, NewsAPIArticle
from src.schemas.response_schema import PipelineStats
from src.search.duckduckgo_search import DuckDuckGoSearcher
from src.utils.logger import get_logger

logger = get_logger("pipeline.orchestrator")


class Orchestrator:
    """
    High-level entry point that wires all modules together.

    Parameters
    ----------
    max_workers:
        Thread-pool size for concurrent extraction.
    language_filter:
        ISO 639-1 code to drop non-matching articles (e.g. ``"en"``).
    min_body_length:
        Minimum article body character count.
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        language_filter: Optional[str] = None,
        min_body_length: int = 200,
    ) -> None:
        self._dedup = DuplicateChecker()
        self._collector = URLCollector(dedup_checker=self._dedup)
        self._pipeline = ScrapingPipeline(
            max_workers=max_workers,
            language_filter=language_filter,
            min_body_length=min_body_length,
        )
        self._ddg = DuckDuckGoSearcher()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        keywords: Optional[list[str]] = None,
        direct_urls: Optional[list[str]] = None,
        use_duckduckgo: bool = True,
        use_newsapi: bool = False,
        newsapi_key: Optional[str] = None,
        newsapi_sources: Optional[list[str]] = None,
        newsapi_language: str = "en",
        newsapi_from_date: Optional[str] = None,
        newsapi_to_date: Optional[str] = None,
        ddg_max_results: Optional[int] = None,
        on_stats: bool = True,
        allow_social: bool = False,
    ) -> PipelineStats:
        """
        Run the full orchestration pipeline.

        Parameters
        ----------
        keywords:
            List of search keywords (used for DDG and NewsAPI searches).
        direct_urls:
            URLs to scrape directly without a search step.
        use_duckduckgo:
            Enable DuckDuckGo search for each keyword.
        use_newsapi:
            Enable NewsAPI search for each keyword.
        newsapi_key:
            Override the NewsAPI key from ``.env``.
        newsapi_sources:
            List of NewsAPI source IDs to filter by.
        newsapi_language:
            ISO 639-1 language code for NewsAPI queries.
        newsapi_from_date:
            Earliest publication date for NewsAPI (``YYYY-MM-DD``).
        newsapi_to_date:
            Latest publication date for NewsAPI (``YYYY-MM-DD``).
        ddg_max_results:
            Override DDG max results per keyword.
        on_stats:
            If ``True``, print a summary when complete.
        allow_social:
            If ``True``, allow social media domains in the search results from the start.

        Returns
        -------
        PipelineStats
        """
        keywords = keywords or []
        direct_urls = direct_urls or []

        # 1. Direct URLs
        accepted_direct = self._collector.add_many(direct_urls)
        logger.info("Direct URLs accepted: %d", accepted_direct)

        # 2. NewsAPI (credible news sources first)
        if use_newsapi and keywords:
            self._collect_from_newsapi(
                keywords,
                api_key=newsapi_key,
                sources=newsapi_sources,
                language=newsapi_language,
                from_date=newsapi_from_date,
                to_date=newsapi_to_date,
            )

        # 3. DuckDuckGo search
        if use_duckduckgo and keywords:
            self._collect_from_duckduckgo(
                keywords,
                max_results=ddg_max_results,
                allow_social=allow_social,
            )

        # 4. Fallback search (socials check)
        if use_duckduckgo and keywords and not allow_social and self._collector.pending < 5:
            logger.info(
                "Fewer than 5 credible URLs found (%d). Switching to search socials (Reddit, Twitter, etc.)...",
                self._collector.pending,
            )
            self._collect_from_duckduckgo(
                keywords,
                max_results=ddg_max_results,
                allow_social=True,
            )

        # 5. Drain collector and run pipeline
        urls = self._collector.drain()
        if not urls:
            logger.warning("No URLs to process — pipeline exiting early.")
            return PipelineStats()

        logger.info("Total unique URLs to scrape: %d", len(urls))

        # Determine a shared query string for provenance
        query_label = ", ".join(keywords[:3]) if keywords else "direct"

        stats = self._pipeline.run(
            urls=urls,
            source=ArticleSource.DUCKDUCKGO if use_duckduckgo else ArticleSource.DIRECT,
            search_query=query_label,
        )

        if on_stats:
            self._print_stats(stats)

        return stats

    # ------------------------------------------------------------------
    # Source collection helpers
    # ------------------------------------------------------------------

    def _collect_from_duckduckgo(
        self,
        keywords: list[str],
        max_results: Optional[int] = None,
        allow_social: bool = False,
    ) -> None:
        if max_results:
            self._ddg.max_results = max_results

        for kw in keywords:
            resp = self._ddg.search(kw, allow_social=allow_social)
            if not resp.success or resp.data is None:
                logger.warning("DDG search failed for %r: %s", kw, resp.error)
                continue
            results: list[DuckDuckGoResult] = resp.data.results
            urls = [r.url for r in results]
            n = self._collector.add_many(urls)
            logger.info("DDG %r (socials=%s) -> %d new URLs", kw, allow_social, n)

    def _collect_from_newsapi(
        self,
        keywords: list[str],
        api_key: Optional[str],
        sources: Optional[list[str]],
        language: str,
        from_date: Optional[str],
        to_date: Optional[str],
    ) -> None:
        key = api_key or settings.newsapi_key
        if not key:
            logger.error("NewsAPI key not configured — skipping NewsAPI collection.")
            return

        try:
            with NewsAPIClient(api_key=key) as client:
                fetcher = NewsFetcher(client)
                for kw in keywords:
                    resp = fetcher.search_articles(
                        kw,
                        sources=sources,
                        language=language,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    if not resp.success or resp.data is None:
                        logger.warning("NewsAPI failed for %r: %s", kw, resp.error)
                        continue
                    articles: list[NewsAPIArticle] = resp.data.results
                    urls = [a.url for a in articles if a.url]
                    n = self._collector.add_many(urls)
                    logger.info("NewsAPI %r → %d new URLs", kw, n)
        except Exception as exc:  # noqa: BLE001
            logger.error("NewsAPI collection error: %s", exc)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def _print_stats(stats: PipelineStats) -> None:
        print("\n" + "=" * 60)
        print("  PIPELINE COMPLETE")
        print("=" * 60)
        print(f"  Total URLs processed : {stats.total_urls}")
        print(f"  Successful           : {stats.successful}")
        print(f"  Failed               : {stats.failed}")
        print(f"  Articles saved       : {stats.articles_saved}")
        print(f"  Elapsed              : {stats.elapsed_seconds:.1f}s")
        if stats.errors:
            print(f"  Errors ({len(stats.errors)}):")
            for err in stats.errors[:5]:
                print(f"    - {err}")
        print("=" * 60 + "\n")
