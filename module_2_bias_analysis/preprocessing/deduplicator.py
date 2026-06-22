"""
Removes duplicate paragraphs prior to inference.

Two layers of dedup are applied:
1. Exact-match dedup on a normalized key (lowercased, punctuation-light)
   — catches verbatim repeats (common when scrapers duplicate a lede
   paragraph or a CMS repeats a caption in the body).
2. Near-duplicate dedup via sequence similarity — catches boilerplate
   paragraphs that differ only by a timestamp or a tracking parameter.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List

_NORMALIZE_KEY = re.compile(r"[^a-z0-9\s]")
_NEAR_DUPLICATE_THRESHOLD = 0.92
_MIN_PARAGRAPH_LEN_FOR_SIMILARITY_CHECK = 40


def _normalize_key(paragraph: str) -> str:
    key = paragraph.lower().strip()
    key = _NORMALIZE_KEY.sub("", key)
    return re.sub(r"\s+", " ", key)


def remove_duplicate_paragraphs(text: str, near_duplicate_threshold: float = _NEAR_DUPLICATE_THRESHOLD) -> str:
    """
    Split `text` into paragraphs (blank-line separated), drop exact and
    near-duplicate paragraphs, and rejoin in original order.
    """
    if not text:
        return ""

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text.strip()

    kept: List[str] = []
    seen_keys: set = set()

    for paragraph in paragraphs:
        key = _normalize_key(paragraph)
        if not key:
            continue
        if key in seen_keys:
            continue

        is_near_duplicate = False
        if len(paragraph) >= _MIN_PARAGRAPH_LEN_FOR_SIMILARITY_CHECK:
            for kept_paragraph in kept:
                similarity = SequenceMatcher(None, key, _normalize_key(kept_paragraph)).ratio()
                if similarity >= near_duplicate_threshold:
                    is_near_duplicate = True
                    break

        if is_near_duplicate:
            continue

        seen_keys.add(key)
        kept.append(paragraph)

    return "\n\n".join(kept)


def deduplicate_articles(articles: List[dict], key: str = "content") -> List[dict]:
    """
    Drop exact-duplicate articles from a batch, keyed on a normalized
    version of `key` (default: article content). First occurrence wins.
    """
    seen_keys: set = set()
    unique: List[dict] = []
    for article in articles:
        normalized = _normalize_key(str(article.get(key, "")))[:500]
        if normalized and normalized not in seen_keys:
            seen_keys.add(normalized)
            unique.append(article)
    return unique


__all__ = ["remove_duplicate_paragraphs", "deduplicate_articles"]
