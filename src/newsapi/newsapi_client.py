"""
src/newsapi/newsapi_client.py
==============================
Low-level NewsAPI HTTP client with retry, timeout, and error handling.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests import Response, Session

from config.settings import settings
from src.utils.helpers import Timer, retry
from src.utils.logger import get_logger

logger = get_logger("newsapi.client")

_BASE_URL = "https://newsapi.org/v2/"


class NewsAPIError(Exception):
    """Raised when NewsAPI returns a non-200 status or an error payload."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message


class NewsAPIRateLimitError(NewsAPIError):
    """Raised specifically when the API rate-limit is hit (HTTP 429)."""


class NewsAPIClient:
    """
    Thin authenticated HTTP client for the NewsAPI v2 REST API.

    Handles authentication, retries, and structured error responses.

    Parameters
    ----------
    api_key:
        NewsAPI key.  Falls back to ``settings.newsapi_key`` if omitted.
    timeout:
        Request timeout in seconds.
    max_retries:
        Number of retry attempts on transient failures.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.newsapi_key
        if not self._api_key or not self._api_key.strip():
            raise ValueError(
                "NewsAPI key is required. Set NEWSAPI_KEY in your .env file."
            )
        self._timeout = timeout or settings.request_timeout
        self._max_retries = max_retries or settings.max_retries
        self._session: Session = self._build_session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> Session:
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "NewsScraper/1.0 (python-requests)",
                "Accept": "application/json",
            }
        )
        return session

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a GET request to ``endpoint`` with ``params``, returning the JSON body."""
        url = urljoin(_BASE_URL, endpoint)
        logger.debug("GET %s | params=%s", url, params)

        with Timer() as t:
            try:
                resp: Response = self._session.get(
                    url, params=params, timeout=self._timeout
                )
            except requests.exceptions.Timeout as exc:
                raise NewsAPIError(0, f"Request timed out: {exc}") from exc
            except requests.exceptions.ConnectionError as exc:
                raise NewsAPIError(0, f"Connection error: {exc}") from exc

        logger.debug("Response %d | %.0fms", resp.status_code, t.elapsed_ms)

        if resp.status_code == 429:
            raise NewsAPIRateLimitError(429, "Rate limit exceeded.")
        if resp.status_code == 401:
            raise NewsAPIError(401, "Invalid API key.")
        if not resp.ok:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            raise NewsAPIError(resp.status_code, msg)

        data: dict[str, Any] = resp.json()
        if data.get("status") != "ok":
            raise NewsAPIError(resp.status_code, data.get("message", "Unknown error"))

        return data

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET with exponential-backoff retry on transient errors."""

        @retry(
            max_attempts=self._max_retries,
            backoff=settings.retry_backoff,
            exceptions=(NewsAPIError, requests.RequestException),
        )
        def _inner() -> dict[str, Any]:
            return self._get(endpoint, params)

        return _inner()

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "NewsAPIClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
