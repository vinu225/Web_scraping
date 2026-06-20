"""
src/storage/csv_writer.py
===========================
Exports articles to CSV format (one row per article).
Handles nested Pydantic models by flattening to a safe column set.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.schemas.article_schema import Article
from src.utils.date_utils import format_iso
from src.utils.logger import get_logger

logger = get_logger("storage.csv")

# Ordered list of columns in the output CSV
_COLUMNS: list[str] = [
    "article_id",
    "url",
    "title",
    "author",
    "published_at",
    "source",
    "source_url",
    "search_query",
    "snippet",
    "body_preview",
    "word_count",
    "reading_time_minutes",
    "language",
    "thumbnail_url",
    "tags",
    "status",
    "scraped_at",
    "processing_time_ms",
    "error_message",
]


def _flatten(article: Article) -> dict[str, str]:
    """Flatten an Article into a dict of plain string values."""
    body = article.body or ""
    return {
        "article_id": article.article_id,
        "url": article.url,
        "title": article.title,
        "author": article.author or "",
        "published_at": format_iso(article.published_at) or "",
        "source": article.source.value,
        "source_url": article.source_url or "",
        "search_query": article.search_query or "",
        "snippet": (article.snippet or "")[:500],
        "body_preview": body[:300].replace("\n", " "),
        "word_count": str(article.metadata.word_count or ""),
        "reading_time_minutes": str(article.metadata.reading_time_minutes or ""),
        "language": article.metadata.language or "",
        "thumbnail_url": article.thumbnail_url or "",
        "tags": ", ".join(article.tags),
        "status": article.status.value,
        "scraped_at": format_iso(article.scraped_at) or "",
        "processing_time_ms": str(round(article.processing_time_ms or 0, 2)),
        "error_message": article.error_message or "",
    }


class CSVWriter:
    """
    Writes articles to a CSV file.

    Parameters
    ----------
    output_dir:
        Directory where CSV exports are written.
    """

    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def export(self, articles: Iterable[Article], filename: str = "articles.csv") -> Path:
        """
        Export articles to a CSV file.

        Parameters
        ----------
        articles:
            Iterable of ``Article`` objects.
        filename:
            Output file name (relative to ``output_dir``).

        Returns
        -------
        Path
            Path to the written CSV file.
        """
        path = self._dir / filename
        rows = [_flatten(a) for a in articles]

        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Exported %d rows to CSV | %s", len(rows), path)
        return path

    def append(self, article: Article, filename: str = "articles.csv") -> Path:
        """
        Append a single article row to an existing CSV (or create one).

        Parameters
        ----------
        article:
            Article to append.
        filename:
            Target CSV filename in ``output_dir``.

        Returns
        -------
        Path
        """
        path = self._dir / filename
        file_exists = path.exists()
        row = _flatten(article)

        with open(path, "a", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=_COLUMNS, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        logger.debug("Appended article %s to CSV", article.article_id[:12])
        return path
