"""
Removes residual HTML artifacts and cleans URLs while preserving semantics.

This runs *after* `html_loader.py` has already stripped tags via
BeautifulSoup, so its job is to mop up what plain-text extraction leaves
behind: stray entities, bare URLs, and common boilerplate phrases
(newsletter prompts, social-share prompts) that survive even
Module 1's cleaning when articles arrive from JSON/HTML directly.
"""

from __future__ import annotations

import html
import re
from typing import List

from module_2_bias_analysis.preprocessing.unicode_normalizer import (
    collapse_whitespace,
    normalize_unicode,
)

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
_HTML_ENTITY_LEFTOVER = re.compile(r"&[a-zA-Z#0-9]+;")
_HTML_TAG_LEFTOVER = re.compile(r"<[^>]+>")

# Phrases that are boilerplate/noise rather than article content.
#
# Two families of pattern are needed because scraped/JSON text doesn't
# reliably preserve paragraph breaks:
#   1. Line-anchored: for boilerplate that is genuinely its own line/block
#      (e.g. a standalone "Advertisement" divider).
#   2. Sentence-bounded: for boilerplate phrases that may be glued inline
#      to surrounding prose (e.g. "...end of story. Subscribe to our
#      newsletter for updates! Next paragraph..."). These match from the
#      trigger phrase up to the next sentence terminator (.!?) or string
#      end, regardless of line position.
_LINE_ANCHORED_BOILERPLATE: List[re.Pattern] = [
    re.compile(r"(?im)^\s*advertisement\s*$"),
    re.compile(r"(?im)^\s*all rights reserved\.?\s*$"),
    re.compile(r"(?im)^\s*copyright \u00a9.*$"),
]

_SENTENCE_BOUNDED_BOILERPLATE: List[re.Pattern] = [
    re.compile(r"(?i)subscribe (to|for)[^.!?]*[.!?]?"),
    re.compile(r"(?i)sign up for our newsletter[^.!?]*[.!?]?"),
    re.compile(r"(?i)share this (article|story|post)[^.!?]*[.!?]?"),
    re.compile(r"(?i)(follow|like) us on (facebook|twitter|instagram|x)[^.!?]*[.!?]?"),
    re.compile(r"(?i)click here to[^.!?]*[.!?]?"),
    re.compile(r"(?i)related (articles?|stories?):?[^.!?]*[.!?]?"),
    re.compile(r"(?i)read (more|also):[^.!?]*[.!?]?"),
]

# Separators that virtually always indicate trailing site branding, e.g.
# "Headline | CNN" or "Headline :: Reuters" — safe to strip unconditionally.
_UNAMBIGUOUS_BRANDING_SEPARATORS = ["|", "::"]

# Separators that are ambiguous (a real headline may legitimately contain
# " - " or an em dash as a clause separator, e.g. "Polls - What They
# Show"). Only stripped when the trailing fragment is short, since brand
# names are almost always 1-3 words ("CNN", "The Verge", "BBC News").
_AMBIGUOUS_BRANDING_SEPARATORS = [" - ", " \u2014 "]
_MAX_BRAND_SUFFIX_WORDS = 3


def remove_html_artifacts(text: str) -> str:
    """Strip stray tags/entities that survived upstream HTML parsing."""
    if not text:
        return ""
    text = _HTML_TAG_LEFTOVER.sub(" ", text)
    text = html.unescape(text)
    text = _HTML_ENTITY_LEFTOVER.sub(" ", text)
    return text


def clean_urls(text: str) -> str:
    """
    Remove bare URLs from prose. URLs rarely carry semantic content for a
    bias classifier and frequently appear in boilerplate ("read more at
    http://...").
    """
    if not text:
        return ""
    return _URL_PATTERN.sub("", text)


def remove_boilerplate(text: str) -> str:
    """Strip common non-editorial boilerplate, whether it occupies its own
    line or is glued inline to surrounding prose."""
    if not text:
        return ""
    for pattern in _LINE_ANCHORED_BOILERPLATE:
        text = pattern.sub("", text)
    for pattern in _SENTENCE_BOUNDED_BOILERPLATE:
        text = pattern.sub("", text)
    return text


def clean_title(title: str) -> str:
    """
    Remove branding suffixes such as ' | CNN' or ' :: Reuters' from a
    headline, keeping the editorial part of the title.

    Unambiguous separators ("|", "::") are stripped whenever present.
    The ambiguous " - " / " — " separator is only stripped when the
    trailing fragment is short (<= 3 words), since brand names are almost
    always short while a real headline clause after a dash usually is not
    (e.g. "Pre-Election Polls - What They Actually Show" is left intact).
    """
    if not title:
        return ""
    cleaned = title.strip()

    for separator in _UNAMBIGUOUS_BRANDING_SEPARATORS:
        if separator in cleaned:
            candidate, _, _suffix = cleaned.rpartition(separator)
            if candidate.strip():
                cleaned = candidate.strip()

    for separator in _AMBIGUOUS_BRANDING_SEPARATORS:
        if separator in cleaned:
            candidate, _, suffix = cleaned.rpartition(separator)
            if candidate.strip() and len(suffix.split()) <= _MAX_BRAND_SUFFIX_WORDS:
                cleaned = candidate.strip()

    return cleaned.strip()


def clean_text(text: str) -> str:
    """
    Master cleaning function combining all of the above, in the order that
    minimizes accidental over-stripping: artifacts -> URLs -> boilerplate
    -> unicode normalize -> whitespace collapse.
    """
    text = remove_html_artifacts(text)
    text = clean_urls(text)
    text = remove_boilerplate(text)
    text = normalize_unicode(text)
    text = collapse_whitespace(text)
    return text


__all__ = [
    "remove_html_artifacts",
    "clean_urls",
    "remove_boilerplate",
    "clean_title",
    "clean_text",
]
