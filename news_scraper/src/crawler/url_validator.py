"""
src/crawler/url_validator.py
==============================
URL validation and normalisation before crawling.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import tldextract

from src.utils.helpers import is_valid_url
from src.utils.logger import get_logger

logger = get_logger("crawler.validator")

# File extensions that are never article pages
_NON_ARTICLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".mp4", ".mp3", ".avi", ".zip", ".tar", ".gz", ".exe",
        ".css", ".js", ".xml", ".json", ".rss",
    }
)


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate a URL for crawlability.

    Returns
    -------
    tuple[bool, Optional[str]]
        ``(True, None)`` if valid; ``(False, reason)`` if invalid.
    """
    url = url.strip()

    if not url:
        return False, "Empty URL"

    if not is_valid_url(url):
        return False, f"Invalid scheme or missing netloc: {url!r}"

    parsed = urlparse(url)
    path_lower = parsed.path.lower()

    for ext in _NON_ARTICLE_EXTENSIONS:
        if path_lower.endswith(ext):
            return False, f"Non-article file type ({ext})"

    extracted = tldextract.extract(url)
    if not extracted.domain:
        return False, "Could not extract domain"

    return True, None


def resolve_relative_url(base: str, href: str) -> Optional[str]:
    """
    Resolve a potentially relative URL against a base URL.

    Parameters
    ----------
    base:
        The page URL that contained the link.
    href:
        Raw href attribute value.

    Returns
    -------
    Optional[str]
        Absolute URL or ``None`` if resolution fails.
    """
    try:
        resolved = urljoin(base, href.strip())
        valid, _ = validate_url(resolved)
        return resolved if valid else None
    except Exception:
        return None
