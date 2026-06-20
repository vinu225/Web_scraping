"""
src/crawler/url_collector.py
=============================
Collects, validates, and deduplicates URLs from multiple sources before
they enter the extraction pipeline.
"""

from __future__ import annotations

from typing import Iterable, Optional

from src.crawler.duplicate_checker import DuplicateChecker
from src.crawler.url_validator import validate_url
from src.utils.helpers import is_valid_url
from src.utils.logger import get_logger

logger = get_logger("crawler.collector")


class URLCollector:
    """
    Aggregates URLs from DuckDuckGo results, NewsAPI articles, and direct
    inputs, runs validation, and deduplicates before returning a clean queue.

    Parameters
    ----------
    dedup_checker:
        Optional shared ``DuplicateChecker``; a fresh instance is created
        if not supplied.
    """

    def __init__(self, dedup_checker: Optional[DuplicateChecker] = None) -> None:
        self._dedup = dedup_checker or DuplicateChecker()
        self._queue: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, url: str) -> bool:
        """
        Validate and enqueue a single URL.

        Returns
        -------
        bool
            ``True`` if the URL was accepted (valid, non-duplicate).
        """
        url = url.strip()
        valid, reason = validate_url(url)
        if not valid:
            logger.debug("Rejected URL | reason=%s | url=%s", reason, url)
            return False

        if self._dedup.check_and_mark(url):
            logger.debug("Duplicate URL skipped: %s", url)
            return False

        self._queue.append(url)
        return True

    def add_many(self, urls: Iterable[str]) -> int:
        """
        Add multiple URLs; returns count of accepted URLs.

        Parameters
        ----------
        urls:
            Iterable of URL strings.

        Returns
        -------
        int
            Number of URLs successfully enqueued.
        """
        accepted = sum(self.add(u) for u in urls)
        logger.info("add_many | accepted=%d", accepted)
        return accepted

    def drain(self) -> list[str]:
        """Return the current queue and reset it."""
        queue = list(self._queue)
        self._queue.clear()
        return queue

    @property
    def pending(self) -> int:
        """Number of URLs currently waiting in the queue."""
        return len(self._queue)
