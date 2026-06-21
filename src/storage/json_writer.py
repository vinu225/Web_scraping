"""
src/storage/json_writer.py
============================
Saves Article objects as pretty-printed JSON files (one per article)
and supports batch export as a JSON Lines (.jsonl) file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.schemas.article_schema import Article
from src.utils.logger import get_logger

logger = get_logger("storage.json")


def _article_to_dict(article: Article) -> dict:
    """Serialise an Article to a JSON-safe dict."""
    return json.loads(article.model_dump_json())


class JSONWriter:
    """
    Writes articles to disk as individual JSON files and/or JSONL exports.

    Parameters
    ----------
    output_dir:
        Directory where individual article JSON files are written.
    """

    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Per-article write
    # ------------------------------------------------------------------

    def write(self, article: Article) -> Path:
        """
        Save a single article to ``<output_dir>/<article_id>.json``.

        Parameters
        ----------
        article:
            The article to persist.

        Returns
        -------
        Path
            Path to the written file.
        """
        path = self._dir / f"{article.article_id}.json"
        data = _article_to_dict(article)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
        logger.debug("Wrote JSON | %s", path.name)
        return path

    # ------------------------------------------------------------------
    # Batch / export
    # ------------------------------------------------------------------

    def write_many(self, articles: Iterable[Article]) -> list[Path]:
        """Write multiple articles; returns list of written paths."""
        paths: list[Path] = []
        for article in articles:
            try:
                paths.append(self.write(article))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to write article %s: %s", article.article_id, exc)
        logger.info("Wrote %d JSON files to %s", len(paths), self._dir)
        return paths

    def export_jsonl(self, articles: Iterable[Article], export_path: Path) -> Path:
        """
        Export articles as JSON Lines (one JSON object per line).

        Parameters
        ----------
        articles:
            Articles to export.
        export_path:
            Path to the output ``.jsonl`` file.

        Returns
        -------
        Path
            Path to the written file.
        """
        export_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(export_path, "w", encoding="utf-8") as fh:
            for article in articles:
                line = article.model_dump_json()
                fh.write(line + "\n")
                count += 1
        logger.info("Exported %d articles to JSONL | %s", count, export_path)
        return export_path

    def export_json_array(self, articles: list[Article], export_path: Path) -> Path:
        """
        Export a list of articles as a JSON array.

        Parameters
        ----------
        articles:
            Articles to export.
        export_path:
            Target file path.

        Returns
        -------
        Path
        """
        export_path.parent.mkdir(parents=True, exist_ok=True)
        data = [_article_to_dict(a) for a in articles]
        with open(export_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
        logger.info("Exported %d articles to JSON array | %s", len(data), export_path)
        return export_path
