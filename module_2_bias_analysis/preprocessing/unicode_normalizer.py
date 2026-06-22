"""
Unicode normalization and whitespace collapsing.

Pure-stdlib, framework-agnostic so it can be unit tested without any
heavy dependencies and reused by both Module 1 and Module 2 if needed.
"""

from __future__ import annotations

import re
import unicodedata

# Common "smart" punctuation that NFKC alone does not normalize to ASCII
# but which should read identically for downstream NLP (tokenization,
# lexicon matching, etc.).
_PUNCT_MAP = {
    "\u2018": "'", "\u2019": "'",   # smart single quotes
    "\u201c": '"', "\u201d": '"',  # smart double quotes
    "\u2013": "-", "\u2014": "-",  # en/em dash
    "\u2026": "...",               # ellipsis
    "\u00a0": " ",                 # non-breaking space
}

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_MULTI_SPACES = re.compile(r"[ \t]{2,}")
_TRAILING_SPACE_BEFORE_NEWLINE = re.compile(r"[ \t]+\n")


def normalize_unicode(text: str) -> str:
    """
    Apply NFKC normalization and map common smart-punctuation characters
    to their ASCII equivalents, without altering semantic content.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    for smart_char, ascii_char in _PUNCT_MAP.items():
        normalized = normalized.replace(smart_char, ascii_char)
    # Drop non-printable control characters but keep newlines/tabs.
    normalized = "".join(
        ch for ch in normalized if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    return normalized


def collapse_whitespace(text: str) -> str:
    """
    Collapse runs of horizontal whitespace and excessive blank lines while
    preserving paragraph breaks (a single blank line between paragraphs).
    """
    if not text:
        return ""
    text = _TRAILING_SPACE_BEFORE_NEWLINE.sub("\n", text)
    text = _MULTI_SPACES.sub(" ", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)
    return text.strip()


__all__ = ["normalize_unicode", "collapse_whitespace"]
