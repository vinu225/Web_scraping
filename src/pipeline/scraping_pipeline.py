"""
src/pipeline/scraping_pipeline.py
====================================
Core scraping pipeline: validates, extracts, cleans, and stores a batch of URLs.

This module is responsible for one scraping "pass" — given a list of URLs,
it extracts articles, applies cleaning, validates schema, and routes to
the appropriate storage sinks.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, Optional

from config.settings import settings
from src.extractors.bs4_extractor import BS4Extractor
from src.preprocess.language_detector import detect_language
from src.preprocess.text_cleaner import clean_snippet, clean_text, clean_title
from src.schemas.article_schema import Article, ArticleSource, ArticleStatus
from src.schemas.response_schema import ExtractionResponse, PipelineStats
from src.storage.csv_writer import CSVWriter
from src.storage.json_writer import JSONWriter
from src.utils.helpers import Timer
from src.utils.logger import get_logger

logger = get_logger("pipeline.scraper")


class ScrapingPipeline:
    """
    Orchestrates end-to-end article scraping for a list of URLs.

    Parameters
    ----------
    raw_dir:
        Directory for raw (unprocessed) article JSON files.
    cleaned_dir:
        Directory for cleaned article JSON files.
    failed_dir:
        Directory to store failed-extraction records.
    exports_dir:
        Directory for CSV / JSONL exports.
    max_workers:
        Thread pool size for concurrent extraction.
    language_filter:
        If set (e.g. ``"en"``), articles in other languages are skipped.
    min_body_length:
        Minimum body character count to accept an article as valid.
    """

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        cleaned_dir: Optional[Path] = None,
        failed_dir: Optional[Path] = None,
        exports_dir: Optional[Path] = None,
        max_workers: Optional[int] = None,
        language_filter: Optional[str] = None,
        min_body_length: int = 200,
    ) -> None:
        self._raw_dir = raw_dir or settings.raw_data_dir
        self._cleaned_dir = cleaned_dir or settings.cleaned_data_dir
        self._failed_dir = failed_dir or settings.failed_data_dir
        self._exports_dir = exports_dir or settings.exports_dir
        self._max_workers = max_workers or settings.max_workers
        self._language_filter = language_filter
        self._min_body_length = min_body_length

        self._raw_writer = JSONWriter(self._raw_dir)
        self._cleaned_writer = JSONWriter(self._cleaned_dir)
        self._failed_writer = JSONWriter(self._failed_dir)
        self._csv_writer = CSVWriter(self._exports_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        urls: list[str],
        source: ArticleSource = ArticleSource.DIRECT,
        search_query: Optional[str] = None,
        on_article: Optional[Callable[[Article], None]] = None,
    ) -> PipelineStats:
        """
        Process a list of URLs through the full extraction pipeline.

        Parameters
        ----------
        urls:
            List of article URLs to scrape.
        source:
            Where the URLs were discovered.
        search_query:
            Search term that yielded these URLs (for provenance tracking).
        on_article:
            Optional callback invoked after each successfully cleaned article.

        Returns
        -------
        PipelineStats
            Aggregate statistics for this run.
        """
        stats = PipelineStats(total_urls=len(urls))
        cleaned_articles: list[Article] = []

        logger.info(
            "Pipeline starting | urls=%d | workers=%d | query=%r",
            len(urls),
            self._max_workers,
            search_query,
        )

        with Timer() as total_timer:
            with BS4Extractor() as extractor, \
                 ThreadPoolExecutor(max_workers=self._max_workers) as pool:

                futures = {
                    pool.submit(
                        self._process_url,
                        extractor,
                        url,
                        source,
                        search_query,
                    ): url
                    for url in urls
                }

                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Unexpected error processing %s", url)
                        stats.failed += 1
                        stats.errors.append(f"{url}: {exc}")
                        continue

                    if result is None:
                        stats.failed += 1
                        continue

                    cleaned_articles.append(result)
                    stats.successful += 1
                    if on_article:
                        try:
                            on_article(result)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("on_article callback error: %s", exc)

        # Batch export
        if cleaned_articles:
            self._csv_writer.export(
                cleaned_articles,
                filename=f"articles_{_ts()}.csv",
            )
            self._cleaned_writer.export_jsonl(
                cleaned_articles,
                self._exports_dir / f"articles_{_ts()}.jsonl",
            )

        stats.articles_saved = len(cleaned_articles)
        stats.elapsed_seconds = total_timer.elapsed_ms / 1000

        logger.info(
            "Pipeline complete | ok=%d | failed=%d | saved=%d | %.1fs",
            stats.successful,
            stats.failed,
            stats.articles_saved,
            stats.elapsed_seconds,
        )
        return stats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_url(
        self,
        extractor: BS4Extractor,
        url: str,
        source: ArticleSource,
        search_query: Optional[str],
    ) -> Optional[Article]:
        """
        Full per-URL processing: extract → validate → clean → store.

        Returns the cleaned Article, or ``None`` on failure.
        """
        resp: ExtractionResponse = extractor.extract(
            url, source=source, search_query=search_query
        )

        if not resp.success or resp.article is None:
            self._store_failed(url, resp.error or "Unknown error")
            return None

        article: Article = resp.article

        # Persist raw copy
        try:
            self._raw_writer.write(article)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Raw write failed for %s: %s", url, exc)

        # Validate minimum content
        if not self._is_valid(article):
            logger.info("Rejected article (insufficient content): %s", url)
            self._store_failed(url, "Insufficient content")
            return None

        # Clean
        article = self._clean(article)

        # Language filter
        if self._language_filter:
            text_sample = f"{article.title} {article.body or article.snippet or ''}"
            lang = detect_language(text_sample)
            article.metadata.language = lang
            if lang and lang != self._language_filter:
                logger.debug("Language filter drop | lang=%s | url=%s", lang, url)
                return None

        article.status = ArticleStatus.CLEANED

        # Persist cleaned copy
        try:
            self._cleaned_writer.write(article)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cleaned write failed for %s: %s", url, exc)

        return article

    def _is_valid(self, article: Article) -> bool:
        body_len = len(article.body or "")
        return bool(article.title) and (body_len >= self._min_body_length or bool(article.snippet))

    def _clean(self, article: Article) -> Article:
        if article.title:
            article.title = clean_title(article.title)
        if article.body:
            article.body = clean_text(article.body)
        if article.snippet:
            article.snippet = clean_snippet(article.snippet)
        return article

    def _store_failed(self, url: str, reason: str) -> None:
        from src.utils.hash_utils import url_hash
        try:
            failed = Article(
                article_id=url_hash(url),
                url=url,
                title="[FAILED]",
                snippet=reason,
                status=ArticleStatus.FAILED,
                error_message=reason,
            )
            self._failed_writer.write(failed)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not store failed record: %s", exc)


def _ts() -> str:
    """Return a compact timestamp string for file naming."""
    return time.strftime("%Y%m%d_%H%M%S")
