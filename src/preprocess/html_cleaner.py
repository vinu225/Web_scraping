"""
src/preprocess/html_cleaner.py
================================
Removes noise tags from a BeautifulSoup document in-place:
scripts, styles, ads, navigation, cookie banners, footers, etc.
Returns a cleaned copy of the soup object.
"""

from __future__ import annotations

import copy
import re

from bs4 import BeautifulSoup, Comment, Tag

from src.utils.logger import get_logger

logger = get_logger("preprocess.html_cleaner")

# Tags to remove unconditionally
_REMOVE_TAGS: frozenset[str] = frozenset(
    {
        "script", "style", "noscript", "iframe", "object", "embed",
        "applet", "canvas", "video", "audio", "track", "source",
        "svg", "math", "form", "input", "button", "select", "textarea",
        "label", "fieldset", "legend",
    }
)

# CSS class / id fragments that mark noise blocks
_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bad(s|vert(is(ement)?)?)?[-_ ]",
        r"\bcookie[-_ ]",
        r"\bbanner[-_ ]",
        r"\bpopup[-_ ]",
        r"\bmodal\b",
        r"\boverlay\b",
        r"\bnewsletter\b",
        r"\bsubscribe\b",
        r"\bsocial[-_ ](share|media|button)",
        r"\bshare[-_ ]",
        r"\brelated[-_ ](article|post|story)",
        r"\brecommend",
        r"\bcomment[-_ ]",
        r"\bsidebar\b",
        r"\bwidget\b",
        r"\bmenu\b",
        r"\bnav(igation)?\b",
        r"\bheader\b",
        r"\bfooter\b",
        r"\bbreatcrumb\b",
        r"\bpagination\b",
        r"\btag[-_]cloud\b",
        r"\bcategory[-_]list\b",
    )
]

# Semantic tags that are always noise
_NOISE_SEMANTIC_TAGS: frozenset[str] = frozenset(
    {"nav", "header", "footer", "aside", "figure"}
)


def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Return a deep-cleaned copy of *soup* with noise elements removed.

    Operations performed:
    * Remove all tags in ``_REMOVE_TAGS``.
    * Remove HTML comments.
    * Remove semantic noise tags (``<nav>``, ``<header>``, ``<footer>``, etc.).
    * Remove ``<div>``/``<section>``/``<span>`` elements whose class/id
      matches a noise pattern.
    * Strip excessive blank lines from remaining text nodes.

    Parameters
    ----------
    soup:
        The parsed BeautifulSoup document to clean.

    Returns
    -------
    BeautifulSoup
        A new (modified copy) soup object.
    """
    soup = copy.copy(soup)

    # 1. Remove hard-blocked tags
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # 2. Remove HTML comments
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # 3. Remove semantic noise elements
    for tag in soup.find_all(_NOISE_SEMANTIC_TAGS):
        tag.decompose()

    # 4. Remove div/section/span/ul/li by class/id noise patterns
    for tag in soup.find_all(["div", "section", "span", "ul", "li", "p"]):
        if _matches_noise(tag):
            tag.decompose()

    logger.debug("HTML cleaning complete")
    return soup


def _matches_noise(tag: Tag) -> bool:
    """Return True if the tag's class or id looks like a noise block."""
    if not isinstance(tag, Tag) or tag.attrs is None:
        return False
    class_attr = tag.get("class") or []
    if isinstance(class_attr, str):
        class_str = class_attr.lower()
    else:
        class_str = " ".join(class_attr).lower()
    id_str = (tag.get("id") or "").lower()
    role = (tag.get("role") or "").lower()
    combined = f"{class_str} {id_str} {role}"
    return any(p.search(combined) for p in _NOISE_PATTERNS)
