"""
src/extractors/bs4_extractor.py
=================================
Top-level article extractor: downloads a URL, parses HTML with BeautifulSoup,
and orchestrates metadata, content, and image sub-extractors.
"""

from __future__ import annotations

from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests import Session

from config.settings import settings
from src.extractors.content_extractor import extract_body
from src.extractors.image_extractor import extract_images, extract_thumbnail
from src.extractors.metadata_extractor import (
    extract_author,
    extract_metadata,
    extract_published_date,
)
from src.preprocess.html_cleaner import clean_html
from src.schemas.article_schema import Article, ArticleSource, ArticleStatus
from src.schemas.response_schema import ExtractionResponse
from src.utils.hash_utils import url_hash
from src.utils.helpers import Timer, count_words, estimate_reading_time
from src.utils.logger import get_logger

logger = get_logger("extractor.bs4")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class BS4Extractor:
    """
    Downloads and extracts article data from a given URL.

    Parameters
    ----------
    session:
        Optional shared ``requests.Session`` for connection pooling.
    timeout:
        HTTP request timeout in seconds.
    max_retries:
        Number of retries on transient network errors.
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._session = session or self._make_session()
        self._timeout = timeout or settings.request_timeout
        self._max_retries = max_retries or settings.max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        url: str,
        *,
        source: ArticleSource = ArticleSource.DIRECT,
        search_query: Optional[str] = None,
        snippet: Optional[str] = None,
    ) -> ExtractionResponse:
        """
        Download and fully extract an article from *url*.

        Parameters
        ----------
        url:
            Article URL to scrape.
        source:
            Where the URL was discovered.
        search_query:
            Original search term that led to this URL (for provenance).
        snippet:
            Pre-existing summary (e.g. from search results).

        Returns
        -------
        ExtractionResponse
        """
        logger.info("Extracting | url=%s", url)
        with Timer() as timer:
            html, final_url, error = self._download(url)

        if error or not html:
            logger.warning("Download failed | url=%s | error=%s", url, error)
            return ExtractionResponse(
                url=url,
                success=False,
                error=error or "No HTML received",
                elapsed_ms=timer.elapsed_ms,
            )

        try:
            article = self._parse(
                html=html,
                url=final_url or url,
                source_url=url,
                source=source,
                search_query=search_query,
                snippet=snippet,
                elapsed_ms=timer.elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Parse error | url=%s", url)
            return ExtractionResponse(
                url=url,
                success=False,
                error=f"Parse error: {exc}",
                elapsed_ms=timer.elapsed_ms,
            )

        logger.info(
            "Extracted | url=%s | title=%r | words=%s | %.0fms",
            url,
            (article.title or "")[:60],
            article.metadata.word_count,
            timer.elapsed_ms,
        )
        return ExtractionResponse(
            url=url,
            success=True,
            article=article,
            elapsed_ms=timer.elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _download(
        self, url: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Fetch the HTML content of *url*.

        Returns
        -------
        tuple[html | None, final_url | None, error | None]
        """
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.get(url, timeout=self._timeout, allow_redirects=True)
                resp.raise_for_status()
                encoding = resp.encoding or resp.apparent_encoding or "utf-8"
                return resp.content.decode(encoding, errors="replace"), resp.url, None
            except requests.exceptions.Timeout:
                logger.warning("Timeout attempt %d/%d | url=%s", attempt, self._max_retries, url)
            except requests.exceptions.TooManyRedirects:
                return None, None, "Too many redirects"
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if code in (403, 404, 410, 451):
                    return None, None, f"HTTP {code}"
                logger.warning("HTTP %d attempt %d/%d | url=%s", code, attempt, self._max_retries, url)
            except requests.exceptions.RequestException as exc:
                logger.warning("Request error attempt %d/%d | %s", attempt, self._max_retries, exc)

        return None, None, "Max retries exceeded"

    def _parse(
        self,
        html: str,
        url: str,
        source_url: str,
        source: ArticleSource,
        search_query: Optional[str],
        snippet: Optional[str],
        elapsed_ms: float,
    ) -> Article:
        soup = BeautifulSoup(html, "lxml")
        clean_soup = clean_html(soup)

        meta = extract_metadata(clean_soup, url)
        author = extract_author(clean_soup)
        published_at = extract_published_date(clean_soup)
        body = extract_body(clean_soup)
        images = extract_images(clean_soup, url)
        thumbnail = extract_thumbnail(clean_soup, url)

        # Extract title with multiple fallbacks to ensure we satisfy Pydantic's min_length=3 constraint
        title = meta.og_title or ""
        
        # Try original soup (in case clean_soup stripped it, e.g. if it was inside a noscript block)
        if not title.strip() or len(title.strip()) < 3:
            orig_title_tag = soup.find("title")
            if orig_title_tag:
                title = orig_title_tag.get_text(strip=True)
                
        # Try clean soup title
        if not title.strip() or len(title.strip()) < 3:
            clean_title_tag = clean_soup.find("title")
            if clean_title_tag:
                title = clean_title_tag.get_text(strip=True)

        # Try first h1 in clean soup
        if not title.strip() or len(title.strip()) < 3:
            h1_tag = clean_soup.find("h1")
            if h1_tag:
                title = h1_tag.get_text(strip=True)

        # Build fallback from URL path/domain if title is still missing or too short
        title = title.strip()
        if not title or len(title) < 3:
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(url)
                path_segments = [s for s in parsed_url.path.split("/") if s]
                if path_segments:
                    last_segment = path_segments[-1].replace("-", " ").replace("_", " ").title()
                    if len(last_segment) >= 3:
                        title = last_segment
                if not title or len(title) < 3:
                    title = parsed_url.netloc or "Untitled Article"
            except Exception:
                title = "Untitled Article"

        word_count = count_words(body) if body else 0
        meta.word_count = word_count
        meta.reading_time_minutes = estimate_reading_time(word_count) if word_count else None

        return Article(
            article_id=url_hash(url),
            url=url,
            source_url=source_url if source_url != url else None,
            source=source,
            search_query=search_query,
            title=title,
            author=author,
            published_at=published_at,
            body=body,
            snippet=snippet or meta.og_description,
            images=images,
            thumbnail_url=thumbnail,
            metadata=meta,
            status=ArticleStatus.RAW,
            processing_time_ms=elapsed_ms,
        )

    @staticmethod
    def _make_session() -> Session:
        session = requests.Session()
        session.headers.update(_HEADERS)
        adapter = requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=0,  # handled manually
                allowed_methods=["GET"],
                status_forcelist=[500, 502, 503, 504],
            )
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "BS4Extractor":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
