"""
src/crawler/duplicate_checker.py
==================================
In-memory and file-backed duplicate detection for article URLs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.utils.hash_utils import url_hash
from src.utils.logger import get_logger

logger = get_logger("crawler.dedup")


class DuplicateChecker:
    """
    Tracks seen article URLs using their SHA-256 hash.

    Supports optional persistence to a JSON file so that deduplication
    survives across pipeline runs.

    Parameters
    ----------
    persist_path:
        Path to a JSON file for storing seen hashes.
        If ``None``, state is kept only in-memory.
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._seen: set[str] = set()
        self._persist_path = persist_path
        if persist_path and persist_path.exists():
            self._load(persist_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, url: str) -> bool:
        """Return ``True`` if this URL has already been seen."""
        return url_hash(url) in self._seen

    def mark_seen(self, url: str) -> None:
        """Record *url* as seen."""
        h = url_hash(url)
        self._seen.add(h)
        logger.debug("Marked URL as seen | hash=%s", h[:12])

    def check_and_mark(self, url: str) -> bool:
        """
        Atomically check and mark a URL.

        Returns
        -------
        bool
            ``True`` if the URL was already seen (duplicate), ``False`` if it is new.
        """
        if self.is_duplicate(url):
            return True
        self.mark_seen(url)
        return False

    def save(self) -> None:
        """Persist the seen-hash set to disk (if a path was configured)."""
        if not self._persist_path:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persist_path, "w", encoding="utf-8") as fh:
            json.dump(list(self._seen), fh)
        logger.debug("Saved %d hashes to %s", len(self._seen), self._persist_path)

    @property
    def count(self) -> int:
        """Total number of unique URLs tracked."""
        return len(self._seen)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self, path: Path) -> None:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self._seen = set(data)
            logger.info("Loaded %d seen hashes from %s", len(self._seen), path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load dedup state from %s: %s", path, exc)
