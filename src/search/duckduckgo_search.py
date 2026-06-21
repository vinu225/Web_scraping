"""
src/search/duckduckgo_search.py
================================
DuckDuckGo search integration.

Uses the ``duckduckgo-search`` package to perform text searches and convert
raw results into typed ``DuckDuckGoResult`` objects.  Handles pagination,
rate-limiting, and deduplication.
"""

from __future__ import annotations

import time
import warnings
from typing import Optional

# Suppress the package renaming warning from duckduckgo_search
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*renamed to ddgs.*")

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException as DuckDuckGoSearchException
except ImportError:
    try:
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import DuckDuckGoSearchException
        
        # Monkeypatch DDGS constructor to suppress the renaming warning and warning filter override
        _orig_init = DDGS.__init__
        def _new_init(self, *args, **kwargs):
            import warnings
            orig_warn = warnings.warn
            orig_simplefilter = warnings.simplefilter
            try:
                # Ignore the renaming warning
                warnings.warn = lambda message, *a, **kw: None if "renamed" in str(message) and "ddgs" in str(message) else orig_warn(message, *a, **kw)
                # Ignore simplefilter calls to prevent it resetting warning configurations
                warnings.simplefilter = lambda *a, **kw: None
                _orig_init(self, *args, **kwargs)
            finally:
                warnings.warn = orig_warn
                warnings.simplefilter = orig_simplefilter
        DDGS.__init__ = _new_init
        
    except ImportError:
        class DuckDuckGoSearchException(Exception):
            pass

from config.settings import settings
from src.schemas.article_schema import DuckDuckGoResult
from src.schemas.response_schema import ScraperResponse, SearchResponse
from src.search.query_builder import build_query, sanitize_keyword
from src.search.result_filter import filter_results
from src.utils.helpers import Timer
from src.utils.logger import get_logger

logger = get_logger("duckduckgo")


class DuckDuckGoSearcher:
    """
    Thin wrapper around the ``duckduckgo-search`` library.

    Parameters
    ----------
    max_results:
        Maximum number of results to return per query (overrides setting).
    region:
        DuckDuckGo region code (e.g. ``"us-en"``, ``"wt-wt"``).
    safesearch:
        ``"on"``, ``"moderate"``, or ``"off"``.
    rate_limit_delay:
        Seconds to wait between paginated requests.
    """

    def __init__(
        self,
        max_results: Optional[int] = None,
        region: Optional[str] = None,
        safesearch: Optional[str] = None,
        rate_limit_delay: Optional[float] = None,
    ) -> None:
        self.max_results = max_results or settings.ddg_max_results
        self.region = region or settings.ddg_region
        self.safesearch = safesearch or settings.ddg_safesearch
        self.rate_limit_delay = rate_limit_delay or settings.rate_limit_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str,
        *,
        page_size: int = 10,
        pages: int = 5,
        site: Optional[str] = None,
        exclude_terms: Optional[list[str]] = None,
        apply_filters: bool = True,
        allow_social: bool = False,
    ) -> ScraperResponse[SearchResponse]:
        """
        Perform a paginated DuckDuckGo text search.

        Parameters
        ----------
        keyword:
            Search term (will be sanitised internally).
        page_size:
            Results per page (used for rate-limit pacing).
        pages:
            Maximum number of pages to fetch.
        site:
            Restrict to a specific domain.
        exclude_terms:
            Terms to exclude from results.
        apply_filters:
            Whether to run the result filter pipeline.
        allow_social:
            Whether to allow social media domains (Reddit, etc.) in the results.

        Returns
        -------
        ScraperResponse[SearchResponse]
        """
        keyword = sanitize_keyword(keyword)
        if not keyword:
            return ScraperResponse.fail("Empty or invalid keyword.")

        query = build_query(keyword, site=site, exclude_terms=exclude_terms)
        logger.info("DDG search | query=%r | max=%d", query, self.max_results)

        all_results: list[DuckDuckGoResult] = []
        seen_urls: set[str] = set()

        with Timer() as timer:
            try:
                with DDGS() as ddgs:
                    raw = ddgs.text(
                        query,
                        region=self.region,
                        safesearch=self.safesearch,
                        max_results=min(self.max_results, pages * page_size),
                    )
                    for rank, item in enumerate(raw or [], start=1):
                        url: str = item.get("href", "").strip()
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        all_results.append(
                            DuckDuckGoResult(
                                title=item.get("title", ""),
                                url=url,
                                snippet=item.get("body", ""),
                                rank=rank,
                            )
                        )
                        if len(all_results) >= self.max_results:
                            break
                        # Pace between page boundaries
                        if rank % page_size == 0:
                            time.sleep(self.rate_limit_delay)

            except DuckDuckGoSearchException as exc:
                logger.warning("DDG search error: %s", exc)
                return ScraperResponse.fail(
                    f"DuckDuckGo search failed: {exc}",
                    query=query,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected DDG error for query %r", query)
                return ScraperResponse.fail(
                    f"Unexpected error: {exc}",
                    query=query,
                )

        if apply_filters:
            all_results = filter_results(all_results, allow_social=allow_social)

        logger.info(
            "DDG search complete | query=%r | found=%d | elapsed=%.0fms",
            query,
            len(all_results),
            timer.elapsed_ms,
        )

        response = SearchResponse(
            query=query,
            results=all_results,
            total_found=len(all_results),
            elapsed_ms=timer.elapsed_ms,
            source="duckduckgo",
        )
        return ScraperResponse.ok(response, query=query)
