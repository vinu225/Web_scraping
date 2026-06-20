"""
tests/test_duckduckgo.py
==========================
Unit tests for the DuckDuckGo search module.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.schemas.article_schema import DuckDuckGoResult
from src.schemas.response_schema import SearchResponse
from src.search.duckduckgo_search import DuckDuckGoSearcher
from src.search.query_builder import build_query, sanitize_keyword
from src.search.result_filter import filter_results


# ---------------------------------------------------------------------------
# query_builder
# ---------------------------------------------------------------------------


class TestQueryBuilder:
    def test_simple_keyword(self):
        assert build_query("climate change") == "climate change"

    def test_exact_phrase(self):
        result = build_query("climate change", exact_phrase=True)
        assert result == '"climate change"'

    def test_site_restriction(self):
        result = build_query("AI", site="bbc.com")
        assert "site:bbc.com" in result

    def test_exclude_terms(self):
        result = build_query("news", exclude_terms=["sports", "ads"])
        assert "-sports" in result
        assert "-ads" in result

    def test_sanitize_keyword_removes_special_chars(self):
        assert sanitize_keyword("hello; DROP TABLE--") == "hello DROP TABLE"

    def test_sanitize_keyword_collapses_whitespace(self):
        assert sanitize_keyword("AI   news") == "AI news"


# ---------------------------------------------------------------------------
# result_filter
# ---------------------------------------------------------------------------


class TestResultFilter:
    def _make_result(self, url: str, snippet: str = "A" * 50) -> DuckDuckGoResult:
        return DuckDuckGoResult(title="Test", url=url, snippet=snippet)

    def test_removes_invalid_url(self):
        results = [self._make_result("not-a-url")]
        assert filter_results(results) == []

    def test_removes_blocked_domain(self):
        results = [self._make_result("https://reddit.com/r/news")]
        assert filter_results(results) == []

    def test_removes_short_snippet(self):
        results = [self._make_result("https://example.com/article", snippet="Short")]
        assert filter_results(results) == []

    def test_deduplicates_urls(self):
        url = "https://example.com/article"
        results = [self._make_result(url), self._make_result(url)]
        filtered = filter_results(results)
        assert len(filtered) == 1

    def test_passes_good_result(self):
        results = [self._make_result("https://bbc.com/news/article", snippet="A" * 50)]
        filtered = filter_results(results)
        assert len(filtered) == 1

    def test_custom_blocked_domain(self):
        results = [self._make_result("https://custom-block.com/art", snippet="A" * 50)]
        filtered = filter_results(results, blocked_domains=["custom-block.com"])
        assert filtered == []


# ---------------------------------------------------------------------------
# DuckDuckGoSearcher
# ---------------------------------------------------------------------------


class TestDuckDuckGoSearcher:
    @patch("src.search.duckduckgo_search.DDGS")
    def test_search_returns_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {"href": "https://bbc.com/news/1", "title": "Article 1", "body": "A" * 60},
            {"href": "https://cnn.com/news/2", "title": "Article 2", "body": "B" * 60},
        ]

        searcher = DuckDuckGoSearcher(max_results=10)
        response = searcher.search("AI safety", apply_filters=False)

        assert response.success
        assert response.data is not None
        assert isinstance(response.data, SearchResponse)
        assert len(response.data.results) == 2

    @patch("src.search.duckduckgo_search.DDGS")
    def test_search_deduplicates_urls(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        dup_url = "https://bbc.com/news/1"
        mock_ddgs.text.return_value = [
            {"href": dup_url, "title": "Art", "body": "A" * 60},
            {"href": dup_url, "title": "Art", "body": "A" * 60},
        ]

        searcher = DuckDuckGoSearcher(max_results=10)
        response = searcher.search("test", apply_filters=False)

        assert len(response.data.results) == 1

    @patch("src.search.duckduckgo_search.DDGS")
    def test_search_handles_exception(self, mock_ddgs_cls):
        from duckduckgo_search.exceptions import DuckDuckGoSearchException
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        mock_ddgs.text.side_effect = DuckDuckGoSearchException("rate limited")

        searcher = DuckDuckGoSearcher()
        response = searcher.search("test")

        assert not response.success
        assert "rate limited" in response.error.lower()

    def test_search_empty_keyword_fails(self):
        searcher = DuckDuckGoSearcher()
        response = searcher.search("   ")
        assert not response.success
