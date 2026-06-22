"""
Unit tests for text_cleaner.py and unicode_normalizer.py.

All tests are dependency-free (stdlib only) and fast — no model loading,
no network calls.
"""

from __future__ import annotations

import pytest

from module_2_bias_analysis.preprocessing.text_cleaner import (
    clean_text,
    clean_title,
    clean_urls,
    remove_boilerplate,
    remove_html_artifacts,
)
from module_2_bias_analysis.preprocessing.unicode_normalizer import (
    collapse_whitespace,
    normalize_unicode,
)


# ─── unicode_normalizer ─────────────────────────────────────────────────────

class TestNormalizeUnicode:
    def test_smart_single_quotes_replaced(self):
        assert normalize_unicode("\u2018hello\u2019") == "'hello'"

    def test_smart_double_quotes_replaced(self):
        assert normalize_unicode("\u201cworld\u201d") == '"world"'

    def test_em_dash_replaced(self):
        assert normalize_unicode("before\u2014after") == "before-after"

    def test_en_dash_replaced(self):
        assert normalize_unicode("before\u2013after") == "before-after"

    def test_non_breaking_space_replaced(self):
        assert normalize_unicode("a\u00a0b") == "a b"

    def test_ellipsis_replaced(self):
        assert normalize_unicode("wait\u2026ok") == "wait...ok"

    def test_empty_string(self):
        assert normalize_unicode("") == ""

    def test_nfkc_normalization_applied(self):
        # NFKC turns full-width digit to ASCII digit
        assert normalize_unicode("\uff10") == "0"

    def test_control_characters_stripped(self):
        result = normalize_unicode("hello\x00world")
        assert "\x00" not in result

    def test_newlines_preserved(self):
        text = "line one\nline two"
        assert "\n" in normalize_unicode(text)


class TestCollapseWhitespace:
    def test_multiple_spaces_collapsed(self):
        assert collapse_whitespace("a   b") == "a b"

    def test_trailing_spaces_before_newline_removed(self):
        assert collapse_whitespace("hello   \nworld") == "hello\nworld"

    def test_excessive_blank_lines_collapsed(self):
        result = collapse_whitespace("para1\n\n\n\n\npara2")
        assert result == "para1\n\npara2"

    def test_empty_string(self):
        assert collapse_whitespace("") == ""

    def test_single_blank_line_preserved(self):
        result = collapse_whitespace("para1\n\npara2")
        assert result == "para1\n\npara2"

    def test_strip_leading_trailing_whitespace(self):
        assert collapse_whitespace("  hello  ") == "hello"


# ─── text_cleaner ───────────────────────────────────────────────────────────

class TestRemoveHtmlArtifacts:
    def test_html_tags_removed(self):
        assert "<p>" not in remove_html_artifacts("<p>Hello world</p>")

    def test_html_entity_decoded(self):
        result = remove_html_artifacts("Tom &amp; Jerry")
        assert "&amp;" not in result
        assert "Tom" in result

    def test_leftover_entity_removed(self):
        result = remove_html_artifacts("price &nbsp; now")
        assert "&nbsp;" not in result

    def test_empty_string(self):
        assert remove_html_artifacts("") == ""

    def test_plain_text_unchanged(self):
        text = "No tags here."
        assert remove_html_artifacts(text) == text


class TestCleanUrls:
    def test_http_url_removed(self):
        result = clean_urls("Read more at https://example.com/article for details.")
        assert "https://" not in result

    def test_www_url_removed(self):
        result = clean_urls("Visit www.example.com now.")
        assert "www." not in result

    def test_empty_string(self):
        assert clean_urls("") == ""

    def test_text_without_urls_unchanged(self):
        text = "No URLs in this sentence."
        assert clean_urls(text) == text


class TestRemoveBoilerplate:
    @pytest.mark.parametrize("boilerplate", [
        "Subscribe to our newsletter for daily updates!",
        "Sign up for our newsletter and get the latest news.",
        "Share this article with your friends on social media.",
        "Follow us on Twitter for more breaking news.",
        "Click here to read the full story.",
        "Related articles: Top 10 stories of the week.",
    ])
    def test_boilerplate_phrases_removed(self, boilerplate: str):
        text = f"Real editorial content. {boilerplate} More real content."
        result = remove_boilerplate(text)
        # The boilerplate trigger phrase should no longer appear.
        trigger = boilerplate.split()[0].lower()
        assert trigger not in result.lower()

    def test_non_boilerplate_content_preserved(self):
        real = "The city council voted to approve the infrastructure bill."
        result = remove_boilerplate(real)
        assert "city council" in result.lower()

    def test_advertisement_line_removed(self):
        text = "Real content.\nAdvertisement\nMore content."
        result = remove_boilerplate(text)
        assert "advertisement" not in result.lower()


class TestCleanTitle:
    def test_pipe_branding_removed(self):
        assert clean_title("Headline Here | The Daily Herald") == "Headline Here"

    def test_double_colon_branding_removed(self):
        assert clean_title("Big Story :: Reuters") == "Big Story"

    def test_short_dash_suffix_removed(self):
        # "CNN" is 1 word → strip
        assert clean_title("Senate Passes Bill - CNN") == "Senate Passes Bill"

    def test_long_dash_clause_preserved(self):
        # "What They Actually Show This Week" is >3 words → keep
        result = clean_title("Pre-Election Polls - What They Actually Show This Week")
        assert "What They Actually Show" in result

    def test_empty_title(self):
        assert clean_title("") == ""

    def test_no_branding(self):
        title = "A Perfectly Normal Headline"
        assert clean_title(title) == title


class TestCleanText:
    def test_full_pipeline_removes_html_and_boilerplate(self):
        raw = "<p>Real journalism.</p> Subscribe to our newsletter! Follow us on Twitter. Visit https://example.com."
        result = clean_text(raw)
        assert "<p>" not in result
        assert "https://" not in result
        assert "Real journalism" in result

    def test_unicode_normalized(self):
        result = clean_text("He said \u201cyes.\u201d")
        assert '"' in result or "yes" in result

    def test_empty_string(self):
        assert clean_text("") == ""
