"""
tests/test_extractor.py
=========================
Unit tests for HTML extraction, metadata parsing, and text cleaning.
"""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.extractors.content_extractor import extract_body
from src.extractors.image_extractor import extract_images, extract_thumbnail
from src.extractors.metadata_extractor import (
    extract_author,
    extract_metadata,
    extract_published_date,
)
from src.preprocess.html_cleaner import clean_html
from src.preprocess.text_cleaner import clean_snippet, clean_text, clean_title
from src.preprocess.unicode_normalizer import normalize
from src.utils.hash_utils import content_hash, normalize_url, url_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Test Article | Example News</title>
  <meta property="og:title" content="Test Article" />
  <meta property="og:description" content="A great test article about AI." />
  <meta property="og:image" content="https://example.com/img/hero.jpg" />
  <meta name="author" content="Jane Smith" />
  <meta property="article:published_time" content="2024-03-15T10:00:00Z" />
  <link rel="canonical" href="https://example.com/articles/test" />
  <script type="application/ld+json">
  {
    "headline": "Test Article LD",
    "author": {"name": "Jane Smith"},
    "datePublished": "2024-03-15T10:00:00Z"
  }
  </script>
</head>
<body>
  <nav id="main-nav"><ul><li>Home</li></ul></nav>
  <header class="site-header">Header content</header>
  <article>
    <h1>Test Article</h1>
    <p>This is the first paragraph of the article, containing meaningful content.</p>
    <p>Second paragraph with additional details about the topic at hand.</p>
    <p>Third paragraph expanding on the subject matter for the reader.</p>
    <p>Fourth paragraph rounding out the body of the article content.</p>
  </article>
  <aside class="sidebar">Sidebar content</aside>
  <footer class="site-footer">Footer content</footer>
  <img src="https://example.com/img/hero.jpg" alt="Hero image" width="800" height="400" />
  <img src="https://example.com/img/small.png" alt="small" width="20" height="20" />
  <script>console.log("tracked");</script>
</body>
</html>
"""


@pytest.fixture
def soup():
    return BeautifulSoup(SAMPLE_HTML, "lxml")


@pytest.fixture
def clean_soup(soup):
    return clean_html(soup)


# ---------------------------------------------------------------------------
# html_cleaner
# ---------------------------------------------------------------------------


class TestHTMLCleaner:
    def test_removes_script_tags(self, clean_soup):
        assert clean_soup.find("script") is None

    def test_removes_nav(self, clean_soup):
        assert clean_soup.find("nav") is None

    def test_removes_footer(self, clean_soup):
        assert clean_soup.find("footer") is None

    def test_removes_header(self, clean_soup):
        assert clean_soup.find("header") is None

    def test_preserves_article(self, clean_soup):
        assert clean_soup.find("article") is not None

    def test_preserves_paragraphs(self, clean_soup):
        assert len(clean_soup.find_all("p")) >= 3


# ---------------------------------------------------------------------------
# metadata_extractor
# ---------------------------------------------------------------------------


class TestMetadataExtractor:
    def test_extracts_og_title(self, clean_soup):
        meta = extract_metadata(clean_soup, "https://example.com")
        assert meta.og_title == "Test Article"

    def test_extracts_og_description(self, clean_soup):
        meta = extract_metadata(clean_soup, "https://example.com")
        assert "AI" in (meta.og_description or "")

    def test_extracts_canonical_url(self, clean_soup):
        meta = extract_metadata(clean_soup, "https://example.com")
        assert meta.canonical_url == "https://example.com/articles/test"

    def test_extracts_author(self, clean_soup):
        author = extract_author(clean_soup)
        assert author == "Jane Smith"

    def test_extracts_published_date(self, clean_soup):
        dt = extract_published_date(clean_soup)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 3
        assert dt.day == 15
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# content_extractor
# ---------------------------------------------------------------------------


class TestContentExtractor:
    def test_extracts_article_body(self, clean_soup):
        body = extract_body(clean_soup)
        assert body is not None
        assert len(body) > 50
        assert "paragraph" in body.lower()

    def test_returns_none_for_empty_soup(self):
        empty_soup = BeautifulSoup("<html><body></body></html>", "lxml")
        body = extract_body(empty_soup)
        assert body is None or len(body) < 100


# ---------------------------------------------------------------------------
# image_extractor
# ---------------------------------------------------------------------------


class TestImageExtractor:
    def test_extracts_images(self, soup):
        images = extract_images(soup, "https://example.com")
        assert len(images) >= 1
        assert any("hero.jpg" in img.url for img in images)

    def test_thumbnail_prefers_og_image(self, soup):
        thumbnail = extract_thumbnail(soup, "https://example.com")
        assert thumbnail == "https://example.com/img/hero.jpg"

    def test_resolves_relative_urls(self):
        html = '<html><body><img src="/images/photo.jpg" alt="photo"></body></html>'
        s = BeautifulSoup(html, "lxml")
        images = extract_images(s, "https://example.com")
        if images:
            assert images[0].url.startswith("https://example.com")


# ---------------------------------------------------------------------------
# text_cleaner
# ---------------------------------------------------------------------------


class TestTextCleaner:
    def test_removes_duplicate_paragraphs(self):
        text = "First paragraph.\nFirst paragraph.\nSecond paragraph."
        cleaned = clean_text(text)
        assert cleaned.count("First paragraph.") == 1

    def test_collapses_whitespace(self):
        text = "Hello    world  \t  test"
        cleaned = clean_text(text)
        assert "  " not in cleaned

    def test_strips_boilerplate(self):
        text = "Real content.\nShare this article\nMore content."
        cleaned = clean_text(text)
        assert "Share this article" not in cleaned

    def test_clean_title_removes_site_suffix(self):
        title = "Breaking News Story | BBC News"
        cleaned = clean_title(title)
        assert "BBC News" not in cleaned
        assert "Breaking News Story" in cleaned

    def test_clean_snippet_truncates(self):
        long_snippet = "word " * 300
        cleaned = clean_snippet(long_snippet)
        assert len(cleaned) <= 1005  # 1000 chars + ellipsis


# ---------------------------------------------------------------------------
# unicode_normalizer
# ---------------------------------------------------------------------------


class TestUnicodeNormalizer:
    def test_replaces_smart_quotes(self):
        text = "\u201cHello\u201d and \u2018world\u2019"
        normalized = normalize(text)
        assert '"Hello"' in normalized
        assert "'world'" in normalized

    def test_replaces_em_dash(self):
        text = "word\u2014word"
        normalized = normalize(text)
        assert "--" in normalized

    def test_strips_zero_width_spaces(self):
        text = "hel\u200blo"
        normalized = normalize(text)
        assert "\u200b" not in normalized

    def test_nfc_normalisation(self):
        # é as e + combining accent vs precomposed é
        decomposed = "e\u0301"  # NFD
        import unicodedata
        result = normalize(decomposed)
        assert unicodedata.is_normalized("NFC", result)


# ---------------------------------------------------------------------------
# hash_utils
# ---------------------------------------------------------------------------


class TestHashUtils:
    def test_url_hash_deterministic(self):
        url = "https://example.com/article"
        assert url_hash(url) == url_hash(url)

    def test_url_hash_strips_tracking(self):
        clean = "https://example.com/article"
        tracked = "https://example.com/article?utm_source=twitter&utm_campaign=test"
        assert url_hash(clean) == url_hash(tracked)

    def test_normalize_url_lowercases_domain(self):
        assert normalize_url("HTTPS://Example.COM/path") == normalize_url("https://example.com/path")

    def test_content_hash_ignores_whitespace(self):
        a = "Hello   World"
        b = "Hello World"
        assert content_hash(a) == content_hash(b)

    def test_content_hash_case_insensitive(self):
        assert content_hash("Hello World") == content_hash("hello world")
