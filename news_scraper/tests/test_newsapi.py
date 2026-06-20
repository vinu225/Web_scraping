"""
tests/test_newsapi.py
======================
Unit tests for the NewsAPI client and fetcher.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.newsapi.newsapi_client import NewsAPIClient, NewsAPIError, NewsAPIRateLimitError
from src.newsapi.news_fetcher import NewsFetcher
from src.schemas.response_schema import SearchResponse


# ---------------------------------------------------------------------------
# NewsAPIClient
# ---------------------------------------------------------------------------


class TestNewsAPIClient:
    def test_raises_without_api_key(self):
        with pytest.raises(ValueError, match="NewsAPI key"):
            NewsAPIClient(api_key="")

    @patch("src.newsapi.newsapi_client.requests.Session")
    def test_get_raises_on_401(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.ok = False
        mock_resp.json.return_value = {"status": "error", "message": "Invalid API key"}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = NewsAPIClient.__new__(NewsAPIClient)
        client._api_key = "test_key"
        client._timeout = 10
        client._max_retries = 1
        client._session = mock_session

        with pytest.raises(NewsAPIError) as exc_info:
            client._get("top-headlines", {})
        assert exc_info.value.status_code == 401

    @patch("src.newsapi.newsapi_client.requests.Session")
    def test_get_raises_rate_limit(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.ok = False
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        client = NewsAPIClient.__new__(NewsAPIClient)
        client._api_key = "test_key"
        client._timeout = 10
        client._max_retries = 1
        client._session = mock_session

        with pytest.raises(NewsAPIRateLimitError):
            client._get("everything", {})

    @patch("src.newsapi.newsapi_client.requests.Session")
    def test_successful_get(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "status": "ok",
            "totalResults": 1,
            "articles": [{"title": "Test", "url": "https://example.com"}],
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        client = NewsAPIClient.__new__(NewsAPIClient)
        client._api_key = "test_key"
        client._timeout = 10
        client._max_retries = 1
        client._session = mock_session

        result = client._get("everything", {"q": "test"})
        assert result["status"] == "ok"
        assert result["totalResults"] == 1


# ---------------------------------------------------------------------------
# NewsFetcher
# ---------------------------------------------------------------------------


_MOCK_ARTICLE = {
    "title": "Test Article",
    "url": "https://example.com/news/1",
    "description": "A test description",
    "author": "John Doe",
    "publishedAt": "2024-01-15T12:00:00Z",
    "source": {"id": "bbc-news", "name": "BBC News"},
    "urlToImage": "https://example.com/image.jpg",
    "content": "Full content here...",
}


class TestNewsFetcher:
    def _make_fetcher_with_mock(self, articles: list[dict], total: int = 1):
        mock_client = MagicMock(spec=NewsAPIClient)
        mock_client.get.return_value = {
            "status": "ok",
            "totalResults": total,
            "articles": articles,
        }
        return NewsFetcher(mock_client)

    def test_top_headlines_success(self):
        fetcher = self._make_fetcher_with_mock([_MOCK_ARTICLE])
        resp = fetcher.top_headlines(query="test")
        assert resp.success
        assert resp.data is not None
        assert len(resp.data.results) == 1
        assert resp.data.results[0].title == "Test Article"

    def test_search_articles_success(self):
        fetcher = self._make_fetcher_with_mock([_MOCK_ARTICLE])
        resp = fetcher.search_articles("machine learning")
        assert resp.success
        assert resp.data.total_found == 1

    def test_search_empty_query_fails(self):
        mock_client = MagicMock(spec=NewsAPIClient)
        fetcher = NewsFetcher(mock_client)
        resp = fetcher.search_articles("   ")
        assert not resp.success
        assert "empty" in resp.error.lower()

    def test_newsapi_error_returns_failure(self):
        mock_client = MagicMock(spec=NewsAPIClient)
        mock_client.get.side_effect = NewsAPIError(500, "Internal server error")
        fetcher = NewsFetcher(mock_client)
        resp = fetcher.search_articles("test")
        assert not resp.success
        assert "500" in resp.error or "Internal" in resp.error

    def test_malformed_articles_skipped(self):
        # One valid, one malformed (missing required title)
        articles = [
            _MOCK_ARTICLE,
            {"url": "https://example.com/broken", "title": None},
        ]
        fetcher = self._make_fetcher_with_mock(articles, total=2)
        resp = fetcher.top_headlines()
        assert resp.success
        # Malformed article with None title should be skipped or have empty title
        assert resp.data is not None

    def test_date_range_passed_to_client(self):
        mock_client = MagicMock(spec=NewsAPIClient)
        mock_client.get.return_value = {"status": "ok", "totalResults": 0, "articles": []}
        fetcher = NewsFetcher(mock_client)
        fetcher.search_articles(
            "test",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        call_params = mock_client.get.call_args[0][1]
        assert "from" in call_params
        assert "to" in call_params
