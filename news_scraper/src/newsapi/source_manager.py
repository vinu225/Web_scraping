"""
src/newsapi/source_manager.py
==============================
Helper for querying and caching NewsAPI source metadata.
"""

from __future__ import annotations

from typing import Optional

from src.newsapi.newsapi_client import NewsAPIClient
from src.utils.logger import get_logger

logger = get_logger("newsapi.source_manager")


class SourceManager:
    """
    Fetches and caches the list of NewsAPI sources.

    Parameters
    ----------
    client:
        Pre-configured ``NewsAPIClient`` instance.
    """

    def __init__(self, client: NewsAPIClient) -> None:
        self._client = client
        self._cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sources(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
    ) -> list[dict]:
        """
        Return all available NewsAPI sources matching the given filters.

        Parameters
        ----------
        category:
            E.g. ``"business"``, ``"technology"``, ``"science"``.
        language:
            ISO 639-1 language code, e.g. ``"en"``.
        country:
            ISO 3166-1 alpha-2 country code, e.g. ``"us"``.

        Returns
        -------
        list[dict]
            List of source objects with ``id``, ``name``, ``url``, etc.
        """
        params: dict[str, str] = {}
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        if country:
            params["country"] = country

        logger.debug("Fetching sources | params=%s", params)
        data = self._client.get("sources", params)
        sources: list[dict] = data.get("sources", [])
        logger.info("Fetched %d sources", len(sources))
        return sources

    def source_ids_by_category(self, category: str) -> list[str]:
        """Return a list of source IDs for the given category."""
        sources = self.get_sources(category=category, language="en")
        return [s["id"] for s in sources if s.get("id")]

    def validate_source_ids(self, source_ids: list[str]) -> list[str]:
        """
        Filter *source_ids* to only those that exist in the NewsAPI catalogue.

        Parameters
        ----------
        source_ids:
            Candidate source ID strings.

        Returns
        -------
        list[str]
            Valid source IDs (unknown IDs are logged and dropped).
        """
        all_sources = self.get_sources()
        known_ids = {s["id"] for s in all_sources}
        valid = [sid for sid in source_ids if sid in known_ids]
        unknown = set(source_ids) - set(valid)
        if unknown:
            logger.warning("Unknown source IDs ignored: %s", unknown)
        return valid
