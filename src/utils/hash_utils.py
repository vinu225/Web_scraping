"""
src/utils/hash_utils.py
========================
Deterministic hashing helpers used to generate stable article IDs
and for deduplication across scraping sessions.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------

# Tracking / UTM parameters to strip before hashing
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "fbclid", "gclid", "msclkid", "yclid", "ref", "source",
        "_ga", "mc_cid", "mc_eid", "si",
    }
)


def normalize_url(url: str) -> str:
    """
    Canonicalize a URL for consistent hashing / deduplication.

    Steps:
    1. Strip whitespace and force lowercase scheme + netloc.
    2. Remove fragment identifiers (``#...``).
    3. Remove known tracking query parameters.
    4. Sort remaining query parameters alphabetically.

    Parameters
    ----------
    url:
        Raw URL string to normalize.

    Returns
    -------
    str
        Normalized URL string, or the original value if parsing fails.
    """
    try:
        parsed: ParseResult = urlparse(url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower().rstrip("/")
        path = parsed.path.rstrip("/") or "/"

        qs = parse_qs(parsed.query, keep_blank_values=False)
        filtered_qs = {k: v for k, v in qs.items() if k not in _TRACKING_PARAMS}
        sorted_query = urlencode(sorted(filtered_qs.items()), doseq=True)

        normalized = urlunparse((scheme, netloc, path, "", sorted_query, ""))
        return normalized
    except Exception:
        return url


def url_hash(url: str) -> str:
    """
    Return the SHA-256 hex digest of the normalized URL.

    This is used as the ``article_id`` throughout the system so that
    the same article encountered via multiple sources gets the same ID.

    Parameters
    ----------
    url:
        Article URL (will be normalized before hashing).

    Returns
    -------
    str
        64-character lowercase hex string.
    """
    canonical = normalize_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    """
    Return the MD5 hex digest of article body text (for near-duplicate detection).

    MD5 is used here only for speed; security is not a concern.

    Parameters
    ----------
    text:
        Cleaned article body text.

    Returns
    -------
    str
        32-character lowercase hex string.
    """
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()
