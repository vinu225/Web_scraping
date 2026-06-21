"""
tests/test_pipeline.py
========================
Integration-style unit tests for the scraping pipeline and orchestrator.
All HTTP calls are mocked to avoid network dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.crawler.duplicate_checker import DuplicateChecker
from src.crawler.url_collector import URLCollector
from src.crawler.url_validator import validate_url
from src.schemas.article_schema import Article, ArticleSource, ArticleStatus
from src.schemas.response_schema import ExtractionResponse, PipelineStats
from src.pipeline.scraping_pipeline import ScrapingPipeline


# ---------------------------------------------------------------------------
# URL Validator
# ---------------------------------------------------------------------------


class TestURLValidator:
    def test_valid_http_url(self):
        valid, reason = validate_url("https://example.com/article")
        assert valid
        assert reason is None

    def test_rejects_empty_string(self):
        valid, reason = validate_url("")
        assert not valid

    def test_rejects_non_http_scheme(self):
        valid, reason = validate_url("ftp://example.com/file")
        assert not valid

    def test_rejects_pdf(self):
        valid, reason = validate_url("https://example.com/doc.pdf")
        assert not valid
        assert "pdf" in (reason or "").lower()

    def test_rejects_image(self):
        valid, reason = validate_url("https://example.com/photo.jpg")
        assert not valid


# ---------------------------------------------------------------------------
# DuplicateChecker
# ---------------------------------------------------------------------------


class TestDuplicateChecker:
    def test_new_url_not_duplicate(self):
        checker = DuplicateChecker()
        assert not checker.is_duplicate("https://example.com/a")

    def test_seen_url_is_duplicate(self):
        checker = DuplicateChecker()
        checker.mark_seen("https://example.com/a")
        assert checker.is_duplicate("https://example.com/a")

    def test_check_and_mark_returns_false_first_time(self):
        checker = DuplicateChecker()
        assert not checker.check_and_mark("https://example.com/b")

    def test_check_and_mark_returns_true_second_time(self):
        checker = DuplicateChecker()
        checker.check_and_mark("https://example.com/c")
        assert checker.check_and_mark("https://example.com/c")

    def test_tracking_params_treated_as_same_url(self):
        checker = DuplicateChecker()
        checker.mark_seen("https://example.com/article")
        assert checker.is_duplicate("https://example.com/article?utm_source=fb")

    def test_count_increases(self):
        checker = DuplicateChecker()
        checker.mark_seen("https://a.com")
        checker.mark_seen("https://b.com")
        assert checker.count == 2

    def test_persist_and_load(self, tmp_path):
        path = tmp_path / "seen.json"
        checker = DuplicateChecker(persist_path=path)
        checker.mark_seen("https://example.com/persist")
        checker.save()

        checker2 = DuplicateChecker(persist_path=path)
        assert checker2.is_duplicate("https://example.com/persist")


# ---------------------------------------------------------------------------
# URLCollector
# ---------------------------------------------------------------------------


class TestURLCollector:
    def test_add_valid_url(self):
        collector = URLCollector()
        assert collector.add("https://example.com/article") is True

    def test_add_invalid_url_rejected(self):
        collector = URLCollector()
        assert collector.add("not-a-url") is False

    def test_add_duplicate_rejected(self):
        collector = URLCollector()
        collector.add("https://example.com/article")
        assert collector.add("https://example.com/article") is False

    def test_add_many_returns_count(self):
        collector = URLCollector()
        urls = [
            "https://a.com/1",
            "https://b.com/2",
            "invalid",
            "https://a.com/1",  # duplicate
        ]
        assert collector.add_many(urls) == 2

    def test_drain_clears_queue(self):
        collector = URLCollector()
        collector.add("https://example.com/one")
        q = collector.drain()
        assert len(q) == 1
        assert collector.pending == 0


# ---------------------------------------------------------------------------
# ScrapingPipeline (with mocked extractor)
# ---------------------------------------------------------------------------


def _make_article(url: str, title: str = "Test Article", body: str = "X" * 300) -> Article:
    from src.utils.hash_utils import url_hash
    return Article(
        article_id=url_hash(url),
        url=url,
        title=title,
        body=body,
        source=ArticleSource.DIRECT,
        status=ArticleStatus.RAW,
    )


class TestScrapingPipeline:
    @pytest.fixture
    def pipeline(self, tmp_path):
        return ScrapingPipeline(
            raw_dir=tmp_path / "raw",
            cleaned_dir=tmp_path / "cleaned",
            failed_dir=tmp_path / "failed",
            exports_dir=tmp_path / "exports",
            max_workers=2,
        )

    @patch("src.pipeline.scraping_pipeline.BS4Extractor")
    def test_successful_run(self, mock_extractor_cls, pipeline):
        url = "https://example.com/article"
        article = _make_article(url)

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ExtractionResponse(
            url=url, success=True, article=article, elapsed_ms=100.0
        )
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor_cls.return_value = mock_extractor

        stats = pipeline.run(urls=[url])

        assert stats.successful == 1
        assert stats.failed == 0

    @patch("src.pipeline.scraping_pipeline.BS4Extractor")
    def test_failed_extraction_tracked(self, mock_extractor_cls, pipeline):
        url = "https://example.com/broken"

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ExtractionResponse(
            url=url, success=False, error="HTTP 404", elapsed_ms=50.0
        )
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor_cls.return_value = mock_extractor

        stats = pipeline.run(urls=[url])

        assert stats.failed == 1
        assert stats.successful == 0

    @patch("src.pipeline.scraping_pipeline.BS4Extractor")
    def test_short_body_rejected(self, mock_extractor_cls, pipeline):
        url = "https://example.com/short"
        article = _make_article(url, body="Too short")

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ExtractionResponse(
            url=url, success=True, article=article, elapsed_ms=80.0
        )
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor_cls.return_value = mock_extractor

        stats = pipeline.run(urls=[url])
        assert stats.successful == 0
        assert stats.failed == 1

    @patch("src.pipeline.scraping_pipeline.BS4Extractor")
    def test_empty_url_list(self, mock_extractor_cls, pipeline):
        stats = pipeline.run(urls=[])
        assert stats.total_urls == 0
        assert stats.successful == 0

    @patch("src.pipeline.scraping_pipeline.BS4Extractor")
    def test_on_article_callback_called(self, mock_extractor_cls, pipeline):
        url = "https://example.com/article"
        article = _make_article(url)
        called_with = []

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ExtractionResponse(
            url=url, success=True, article=article, elapsed_ms=100.0
        )
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor_cls.return_value = mock_extractor

        pipeline.run(urls=[url], on_article=lambda a: called_with.append(a))
        assert len(called_with) == 1
        assert called_with[0].url == url
