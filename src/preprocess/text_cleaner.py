"""
src/preprocess/text_cleaner.py
================================
Text-level cleaning applied after HTML extraction:
whitespace normalisation, duplicate-paragraph removal,
tracking-parameter stripping, and general article text polish.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from src.preprocess.unicode_normalizer import normalize
from src.utils.hash_utils import normalize_url
from src.utils.logger import get_logger

logger = get_logger("preprocess.text_cleaner")

# Repeated punctuation / whitespace
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")

# Very short lines that are likely navigation / UI labels (< 4 words, no sentence-ending punctuation)
_SHORT_LINE = re.compile(r"^(?:\S+\s?){1,3}$")

# Boilerplate phrases that appear in scraped content
_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^(share|tweet|email|print|save|copy link|bookmark)(\s+this)?(\s+article)?$",
        r"^advertisement$",
        r"^continue reading (below|this article)",
        r"^sponsored content$",
        r"^follow us on",
        r"^click here to",
        r"^read more[:.]?$",
        r"sign up for (our|the) newsletter",
        r"^subscribe (to|for)",
        r"^you might also like",
        r"^also read[:.]?$",
    )
]


def clean_text(text: str) -> str:
    """
    Apply the full text-cleaning pipeline to article body text.

    Steps:
    1. Unicode normalisation.
    2. Collapse horizontal whitespace.
    3. Remove boilerplate lines.
    4. Remove duplicate paragraphs (preserves order).
    5. Collapse excessive blank lines.
    6. Strip leading/trailing whitespace.

    Parameters
    ----------
    text:
        Raw extracted article text.

    Returns
    -------
    str
        Cleaned text ready for storage.
    """
    if not text:
        return ""

    text = normalize(text)
    text = _MULTI_SPACE.sub(" ", text)

    paragraphs = [p.strip() for p in text.split("\n")]
    paragraphs = _remove_boilerplate(paragraphs)
    paragraphs = _dedup_paragraphs(paragraphs)

    text = "\n".join(paragraphs)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def clean_title(title: str) -> str:
    """
    Normalise and trim an article title.

    * Removes site-name suffixes (e.g. ``" | BBC News"``, ``" - Reuters"``).
    * Strips surrounding whitespace.

    Parameters
    ----------
    title:
        Raw title string.

    Returns
    -------
    str
        Cleaned title.
    """
    title = normalize(title).strip()
    # Remove common " | Site Name" / " - Site Name" suffixes
    title = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{3,50}$", "", title).strip()
    return title


def clean_snippet(snippet: str) -> str:
    """Normalise and truncate a search snippet or article description."""
    snippet = normalize(snippet).strip()
    if len(snippet) > 1000:
        snippet = snippet[:1000].rsplit(" ", 1)[0] + "…"
    return snippet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _remove_boilerplate(paragraphs: list[str]) -> list[str]:
    cleaned: list[str] = []
    for para in paragraphs:
        if not para:
            cleaned.append(para)
            continue
        # Only strip short lines that don't look like real sentences
        # (real sentences end with . ! ? or are longer than 30 chars)
        if _SHORT_LINE.match(para) and len(para) < 30 and not para.rstrip().endswith((".", "!", "?")):
            continue
        if any(p.search(para) for p in _BOILERPLATE_PATTERNS):
            continue
        cleaned.append(para)
    return cleaned


def _dedup_paragraphs(paragraphs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for para in paragraphs:
        key = re.sub(r"\s+", " ", para.lower().strip())
        if not key:
            out.append(para)
            continue
        if key not in seen:
            seen.add(key)
            out.append(para)
    return out
