"""
Unit tests for loaders/json_loader.py, html_loader.py, and article_loader.py.

All tests are network-free and model-free. HTML tests use the sample HTML
file in tests/sample_data/.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from module_2_bias_analysis.loaders.html_loader import load_html, load_html_batch
from module_2_bias_analysis.loaders.json_loader import load_json
from module_2_bias_analysis.schemas.requests import HTMLArticleInput, JSONArticleInput
from module_2_bias_analysis.utils.exceptions import EmptyContentError, SchemaValidationError

_SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


# ─── json_loader ─────────────────────────────────────────────────────────────

class TestLoadJson:
    def test_single_dict_returns_one_article(self):
        payload = {"title": "Test", "content": "Some real content here."}
        results = load_json(payload)
        assert len(results) == 1
        assert isinstance(results[0], JSONArticleInput)

    def test_list_of_dicts_returns_multiple(self):
        payloads = [
            {"title": "Article One", "content": "Content for article one."},
            {"title": "Article Two", "content": "Content for article two."},
        ]
        results = load_json(payloads)
        assert len(results) == 2

    def test_json_string_object_parsed(self):
        payload = json.dumps({"title": "From JSON string", "content": "The content."})
        results = load_json(payload)
        assert len(results) == 1
        assert results[0].title == "From JSON string"

    def test_json_string_array_parsed(self):
        payloads = [
            {"title": "A", "content": "Content A."},
            {"title": "B", "content": "Content B."},
        ]
        results = load_json(json.dumps(payloads))
        assert len(results) == 2

    def test_json_file_path_loaded(self):
        path = _SAMPLE_DATA_DIR / "sample_article_neutral.json"
        if not path.exists():
            pytest.skip("Sample data file not found")
        results = load_json(path)
        assert len(results) == 1
        assert results[0].content

    def test_batch_json_file_loaded(self):
        path = _SAMPLE_DATA_DIR / "sample_batch.json"
        if not path.exists():
            pytest.skip("Sample data file not found")
        results = load_json(path)
        assert len(results) == 2

    def test_missing_title_raises_schema_error(self):
        with pytest.raises(SchemaValidationError, match="schema validation"):
            load_json({"content": "No title field at all."})

    def test_missing_content_raises_schema_error(self):
        with pytest.raises(SchemaValidationError, match="schema validation"):
            load_json({"title": "No content field at all."})

    def test_invalid_json_string_raises_schema_error(self):
        with pytest.raises(SchemaValidationError, match="not valid JSON"):
            load_json("{this is not json}")

    def test_empty_list_raises_schema_error(self):
        with pytest.raises(SchemaValidationError, match="empty"):
            load_json([])

    def test_unsupported_type_raises_schema_error(self):
        with pytest.raises(SchemaValidationError):
            load_json(42)

    def test_optional_fields_populated_when_present(self):
        payload = {
            "article_id": "abc123",
            "title": "Test Article",
            "content": "Real article body text here.",
            "url": "https://example.com",
            "author": "Test Author",
        }
        results = load_json(payload)
        assert results[0].article_id == "abc123"
        assert results[0].author == "Test Author"

    def test_optional_fields_none_when_absent(self):
        results = load_json({"title": "Minimal", "content": "Only required fields."})
        assert results[0].article_id is None
        assert results[0].author is None

    def test_json_file_written_and_loaded(self):
        article = {"title": "Temp file test", "content": "Content from a temporary JSON file."}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as fh:
            json.dump(article, fh)
            tmp_path = Path(fh.name)
        try:
            results = load_json(tmp_path)
            assert results[0].title == "Temp file test"
        finally:
            tmp_path.unlink(missing_ok=True)


# ─── html_loader ─────────────────────────────────────────────────────────────

class TestLoadHtml:
    def test_basic_html_extracts_content(self):
        html = "<html><body><article><p>This is the main story paragraph.</p></article></body></html>"
        payload = HTMLArticleInput(html=html)
        result = load_html(payload)
        assert "main story paragraph" in result.content.lower()

    def test_title_extracted_from_head(self):
        html = "<html><head><title>My Article Title | Site Name</title></head><body><article><p>Content.</p></article></body></html>"
        payload = HTMLArticleInput(html=html)
        result = load_html(payload)
        assert "My Article Title" in result.title

    def test_override_title_used_when_provided(self):
        html = "<html><head><title>Extracted Title</title></head><body><p>Content here.</p></body></html>"
        payload = HTMLArticleInput(html=html, title="My Override Title")
        result = load_html(payload)
        assert result.title == "My Override Title"

    def test_scripts_and_nav_stripped(self):
        html = (
            "<html><body>"
            "<nav>Navigation links here</nav>"
            "<article><p>Real content paragraph.</p></article>"
            "<script>trackUser();</script>"
            "</body></html>"
        )
        payload = HTMLArticleInput(html=html)
        result = load_html(payload)
        assert "trackUser" not in result.content
        assert "Navigation" not in result.content

    def test_empty_html_raises_empty_content_error(self):
        payload = HTMLArticleInput(html="<html><body></body></html>")
        with pytest.raises(EmptyContentError):
            load_html(payload)

    def test_html_file_path_loaded(self):
        path = _SAMPLE_DATA_DIR / "sample_article.html"
        if not path.exists():
            pytest.skip("Sample data file not found")
        payload = HTMLArticleInput(html=str(path))
        result = load_html(payload)
        assert result.content
        assert len(result.content) > 50

    def test_metadata_fields_passed_through(self):
        html = "<html><body><article><p>Article text goes here for testing.</p></article></body></html>"
        payload = HTMLArticleInput(
            html=html,
            article_id="html-001",
            url="https://example.com/article",
            source="example.com",
        )
        result = load_html(payload)
        assert result.article_id == "html-001"
        assert result.url == "https://example.com/article"

    def test_load_html_batch(self):
        html = "<html><body><article><p>Article content for batch item.</p></article></body></html>"
        payloads = [
            HTMLArticleInput(html=html, title="Batch Item One"),
            HTMLArticleInput(html=html, title="Batch Item Two"),
        ]
        results = load_html_batch(payloads)
        assert len(results) == 2


# ─── article_loader ──────────────────────────────────────────────────────────

class TestArticleLoader:
    def test_shared_article_object_accepted(self):
        from module_2_bias_analysis.loaders.article_loader import load_article
        from shared.schemas import Article

        article = Article(
            article_id="test-001",
            title="Test Article",
            url="https://example.com",
            source="example.com",
            content="Article body text for testing the loader integration path.",
        )
        results = load_article(article)
        assert len(results) == 1
        assert results[0].article_id == "test-001"

    def test_list_of_articles_accepted(self):
        from module_2_bias_analysis.loaders.article_loader import load_article
        from shared.schemas import Article

        articles = [
            Article(article_id=f"test-{i}", title=f"Article {i}", url="https://example.com",
                    source="example.com", content="Content text for testing.") for i in range(3)
        ]
        results = load_article(articles)
        assert len(results) == 3

    def test_dict_matching_schema_accepted(self):
        from module_2_bias_analysis.loaders.article_loader import load_article

        payload = {
            "article_id": "dict-001",
            "title": "Dict Article",
            "url": "https://example.com/dict",
            "source": "example.com",
            "content": "Content loaded from a plain dictionary.",
        }
        results = load_article(payload)
        assert results[0].article_id == "dict-001"

    def test_module1_sample_file_loaded(self):
        from module_2_bias_analysis.loaders.article_loader import load_article

        path = _SAMPLE_DATA_DIR / "sample_module1_article.json"
        if not path.exists():
            pytest.skip("Sample data file not found")
        results = load_article(path)
        assert results[0].article_id == "sha256-abc123def456"
        assert results[0].source == "metro-times.com"

    def test_dict_missing_required_fields_raises(self):
        from module_2_bias_analysis.loaders.article_loader import load_article

        with pytest.raises(SchemaValidationError):
            load_article({"title": "Missing content, url, source, article_id"})

    def test_empty_list_raises_schema_error(self):
        from module_2_bias_analysis.loaders.article_loader import load_article

        with pytest.raises(SchemaValidationError, match="empty"):
            load_article([])
