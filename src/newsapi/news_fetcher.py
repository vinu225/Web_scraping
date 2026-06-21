"""
src/newsapi/news_fetcher.py
============================
High-level NewsAPI fetcher: top headlines and keyword searches
with date-range, source, and language filtering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.newsapi.newsapi_client import NewsAPIClient, NewsAPIError
from src.schemas.article_schema import ArticleSource, NewsAPIArticle
from src.schemas.response_schema import ScraperResponse, SearchResponse
from src.utils.date_utils import format_iso, parse_date
from src.utils.helpers import Timer
from src.utils.logger import get_logger

logger = get_logger("newsapi.fetcher")

_MAX_PAGE_SIZE = 100  # NewsAPI hard limit


class NewsFetcher:
    """
    Fetches articles from the NewsAPI /top-headlines and /everything endpoints.

    Parameters
    ----------
    client:
        Authenticated ``NewsAPIClient`` instance.
    """

    def __init__(self, client: NewsAPIClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Top Headlines
    # ------------------------------------------------------------------

    def top_headlines(
        self,
        *,
        query: Optional[str] = None,
        sources: Optional[list[str]] = None,
        category: Optional[str] = None,
        country: Optional[str] = None,
        language: str = "en",
        page_size: int = 20,
        page: int = 1,
    ) -> ScraperResponse[SearchResponse]:
        """
        Fetch top headlines from NewsAPI.

        Parameters
        ----------
        query:
            Keywords to filter headlines (optional).
        sources:
            List of NewsAPI source IDs.  Cannot be combined with *country*/*category*.
        category:
            News category (e.g. ``"technology"``).
        country:
            Two-letter country code (e.g. ``"us"``).
        language:
            ISO 639-1 language code.
        page_size:
            Number of results per page (max 100).
        page:
            Page number (1-based).

        Returns
        -------
        ScraperResponse[SearchResponse]
        """
        params: dict = {
            "language": language,
            "pageSize": min(page_size, _MAX_PAGE_SIZE),
            "page": page,
        }
        if query:
            params["q"] = query
        if sources:
            params["sources"] = ",".join(sources)
        elif category:
            params["category"] = category
            if country:
                params["country"] = country
        elif country:
            params["country"] = country

        logger.info("Fetching top headlines | params=%s", params)
        return self._fetch("top-headlines", params, query or "top-headlines")

    # ------------------------------------------------------------------
    # Keyword search (everything endpoint)
    # ------------------------------------------------------------------

    def search_articles(
        self,
        query: str,
        *,
        sources: Optional[list[str]] = None,
        language: str = "en",
        from_date: Optional[datetime | str] = None,
        to_date: Optional[datetime | str] = None,
        sort_by: str = "publishedAt",
        page_size: int = 20,
        page: int = 1,
    ) -> ScraperResponse[SearchResponse]:
        """
        Search for articles matching a keyword via the /everything endpoint.

        Parameters
        ----------
        query:
            Keywords / phrases to search.
        sources:
            Comma-separated list of NewsAPI source IDs to filter by.
        language:
            ISO 639-1 language code.
        from_date:
            Earliest article publish date (inclusive).
        to_date:
            Latest article publish date (inclusive).
        sort_by:
            One of ``"relevancy"``, ``"popularity"``, ``"publishedAt"``.
        page_size:
            Number of results per page (max 100).
        page:
            Page number.

        Returns
        -------
        ScraperResponse[SearchResponse]
        """
        if not query.strip():
            return ScraperResponse.fail("Query string cannot be empty.")

        params: dict = {
            "q": query.strip(),
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, _MAX_PAGE_SIZE),
            "page": page,
        }
        if sources:
            params["sources"] = ",".join(sources)
        if from_date:
            dt = parse_date(from_date) if isinstance(from_date, str) else from_date
            if dt:
                params["from"] = format_iso(dt)
        if to_date:
            dt = parse_date(to_date) if isinstance(to_date, str) else to_date
            if dt:
                params["to"] = format_iso(dt)

        logger.info("Searching NewsAPI | query=%r | params=%s", query, params)
        return self._fetch("everything", params, query)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch(
        self, endpoint: str, params: dict, query: str
    ) -> ScraperResponse[SearchResponse]:
        with Timer() as timer:
            try:
                data = self._client.get(endpoint, params)
            except NewsAPIError as exc:
                logger.error("NewsAPI error: %s", exc)
                return ScraperResponse.fail(str(exc), query=query)

        articles_raw: list[dict] = data.get("articles", [])
        total_results: int = data.get("totalResults", 0)

        results: list[NewsAPIArticle] = []
        for raw in articles_raw:
            try:
                results.append(
                    NewsAPIArticle(
                        title=raw.get("title") or "",
                        url=raw.get("url") or "",
                        description=raw.get("description"),
                        author=raw.get("author"),
                        published_at=parse_date(raw.get("publishedAt")),
                        source_name=(raw.get("source") or {}).get("name"),
                        url_to_image=raw.get("urlToImage"),
                        content=raw.get("content"),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping malformed article: %s", exc)
                continue

        logger.info(
            "NewsAPI %r | returned=%d / total=%d | %.0fms",
            endpoint,
            len(results),
            total_results,
            timer.elapsed_ms,
        )

        search_resp = SearchResponse(
            query=query,
            results=results,
            total_found=total_results,
            page=params.get("page", 1),
            elapsed_ms=timer.elapsed_ms,
            source=ArticleSource.NEWSAPI,
        )
        return ScraperResponse.ok(search_resp, total_results=total_results)
