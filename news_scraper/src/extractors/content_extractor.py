"""
src/extractors/content_extractor.py
=====================================
Extracts the main article body from a BeautifulSoup document by scoring
and selecting candidate content containers.

Strategy (heuristic):
1. Look for semantic HTML5 elements (``<article>``, ``<main>``).
2. Score ``<div>`` and ``<section>`` blocks by paragraph density.
3. Fall back to the highest-density block on the page.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from src.utils.logger import get_logger

logger = get_logger("extractor.content")

# Tags whose text content is always noise
_NOISE_TAGS: frozenset[str] = frozenset(
    {"script", "style", "noscript", "iframe", "nav", "header",
     "footer", "aside", "form", "button", "select", "textarea",
     "figcaption"}
)

# CSS class / id fragments that indicate non-article blocks
_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"comment", r"sidebar", r"widget", r"social", r"share",
        r"related", r"recommend", r"ad[s\-_]", r"advert",
        r"cookie", r"banner", r"popup", r"newsletter", r"subscribe",
        r"nav(igation)?", r"menu", r"footer", r"header", r"breadcrumb",
    )
]


def extract_body(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract the main readable article body from the parsed document.

    Parameters
    ----------
    soup:
        Parsed BeautifulSoup document (should already have noisy tags removed
        by ``html_cleaner``).

    Returns
    -------
    Optional[str]
        Extracted body text, or ``None`` if no suitable content was found.
    """
    # 1. Try semantic article element
    for selector in ("article", "main", '[role="main"]', ".article-body",
                     ".post-content", ".entry-content", ".story-body",
                     ".article__body", ".content-body"):
        candidate = soup.select_one(selector)
        if candidate and _score_tag(candidate) > 100:
            text = _extract_text(candidate)
            if len(text) > 200:
                logger.debug("Content via selector %r | len=%d", selector, len(text))
                return text

    # 2. Score all block-level containers
    best_tag: Optional[Tag] = None
    best_score: float = 0.0

    for tag in soup.find_all(["div", "section", "article"]):
        if _is_noisy(tag):
            continue
        score = _score_tag(tag)
        if score > best_score:
            best_score = score
            best_tag = tag

    if best_tag and best_score > 50:
        text = _extract_text(best_tag)
        if len(text) > 200:
            logger.debug("Content via scoring | score=%.1f | len=%d", best_score, len(text))
            return text

    # 3. Full page fallback
    body = soup.find("body")
    if body:
        text = _extract_text(body)
        if len(text) > 100:
            logger.debug("Content via body fallback | len=%d", len(text))
            return text

    logger.warning("Could not extract body content")
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _score_tag(tag: Tag) -> float:
    """
    Assign a content score to a tag based on paragraph count and text density.
    """
    paragraphs = tag.find_all("p")
    if not paragraphs:
        return 0.0

    total_text = sum(len(p.get_text(strip=True)) for p in paragraphs)
    score = len(paragraphs) * 10 + total_text / 5

    # Penalty for link-heavy blocks (likely navigation)
    links = tag.find_all("a")
    link_text = sum(len(a.get_text(strip=True)) for a in links)
    if total_text > 0:
        link_density = link_text / total_text
        score *= max(0.0, 1.0 - link_density)

    return score


def _is_noisy(tag: Tag) -> bool:
    """Return ``True`` if the tag looks like a non-article block."""
    if tag.name in _NOISE_TAGS:
        return True
    class_str = " ".join(tag.get("class") or []).lower()
    id_str = (tag.get("id") or "").lower()
    combined = f"{class_str} {id_str}"
    return any(p.search(combined) for p in _NOISE_PATTERNS)


def _extract_text(tag: Tag) -> str:
    """Recursively extract clean text from a tag, skipping noise sub-tags."""
    parts: list[str] = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            if node.parent and node.parent.name in _NOISE_TAGS:
                continue
            text = str(node).strip()
            if text:
                parts.append(text)
    return " ".join(parts)
