"""
src/search/query_builder.py
============================
Helpers for constructing well-formed search query strings.
"""

from __future__ import annotations

import re
from typing import Optional


def build_query(
    keyword: str,
    *,
    site: Optional[str] = None,
    exclude_terms: Optional[list[str]] = None,
    exact_phrase: bool = False,
    date_range: Optional[tuple[str, str]] = None,
) -> str:
    """
    Build a structured search query string.

    Parameters
    ----------
    keyword:
        Core search term.
    site:
        Restrict results to a specific domain (e.g. ``"bbc.com"``).
    exclude_terms:
        List of terms to exclude from results (prepended with ``-``).
    exact_phrase:
        If ``True``, wraps *keyword* in double quotes.
    date_range:
        Tuple of ``(start_date, end_date)`` strings in ``YYYY-MM-DD`` format
        (currently informational; DuckDuckGo does not support inline date ops).

    Returns
    -------
    str
        Formatted query string.
    """
    parts: list[str] = []

    term = keyword.strip()
    if exact_phrase and " " in term:
        term = f'"{term}"'
    parts.append(term)

    if site:
        parts.append(f"site:{site.strip()}")

    for ex in (exclude_terms or []):
        clean = ex.strip().lstrip("-")
        if clean:
            parts.append(f"-{clean}")

    return " ".join(parts)


def sanitize_keyword(keyword: str) -> str:
    """
    Strip characters that could break a search query or cause injection.

    Parameters
    ----------
    keyword:
        Raw user-supplied keyword.

    Returns
    -------
    str
        Sanitised string safe for use in a search query.
    """
    # Allow letters, numbers, spaces, hyphens (only mid-word), apostrophes
    sanitized = re.sub(r"[^\w\s\-']", "", keyword, flags=re.UNICODE)
    # Strip leading/trailing hyphens from each token
    tokens = [t.strip("-") for t in sanitized.split()]
    return " ".join(t for t in tokens if t)  # collapse whitespace
