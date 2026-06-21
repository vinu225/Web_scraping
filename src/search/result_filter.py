"""
src/search/result_filter.py
============================
Post-processing filters applied to raw DuckDuckGo / search results
before they are handed off to the crawl queue.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from src.schemas.article_schema import DuckDuckGoResult
from src.utils.helpers import is_valid_url

_SOCIAL_DOMAINS: frozenset[str] = frozenset(
    {
        "reddit.com", "twitter.com", "x.com", "facebook.com",
        "instagram.com", "linkedin.com",
    }
)

# Domains that are typically aggregators / trackers and not original articles
_BLOCKLIST: frozenset[str] = frozenset(
    {
        "google.com", "google.co.uk", "bing.com", "yahoo.com",
        "duckduckgo.com", "youtube.com", "t.co", "bit.ly",
    }
) | _SOCIAL_DOMAINS


def filter_results(
    results: list[DuckDuckGoResult],
    *,
    min_snippet_length: int = 20,
    allowed_domains: Optional[list[str]] = None,
    blocked_domains: Optional[list[str]] = None,
    allow_social: bool = False,
) -> list[DuckDuckGoResult]:
    """
    Apply quality and domain filters to a list of search results.

    Parameters
    ----------
    results:
        Raw search results from DuckDuckGo.
    min_snippet_length:
        Discard results whose snippet is shorter than this threshold.
    allowed_domains:
        If provided, only keep results from these domains.
    blocked_domains:
        Additional domains to block beyond the built-in blocklist.
    allow_social:
        If True, allow social media domains (Reddit, Twitter, etc.).

    Returns
    -------
    list[DuckDuckGoResult]
        Filtered list, preserving original ranking order.
    """
    extra_blocked = frozenset(d.lower() for d in (blocked_domains or []))
    blocklist = set(_BLOCKLIST)
    if allow_social:
        blocklist = blocklist - _SOCIAL_DOMAINS
    combined_blocklist = frozenset(blocklist) | extra_blocked
    allowed = frozenset(d.lower() for d in (allowed_domains or []))

    seen_urls: set[str] = set()
    out: list[DuckDuckGoResult] = []

    for r in results:
        url = r.url.strip()

        if not is_valid_url(url):
            continue

        netloc = urlparse(url).netloc.lower().lstrip("www.")

        if netloc in combined_blocklist:
            continue

        if allowed and netloc not in allowed:
            continue

        snippet = (r.snippet or "").strip()
        if len(snippet) < min_snippet_length:
            continue

        # Deduplicate by URL
        if url in seen_urls:
            continue
        seen_urls.add(url)

        out.append(r)

    return out
