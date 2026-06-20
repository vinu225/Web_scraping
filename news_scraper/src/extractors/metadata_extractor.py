"""
src/extractors/metadata_extractor.py
======================================
Extracts structured metadata from a BeautifulSoup document:
Open Graph tags, JSON-LD, canonical URLs, keywords, and publication dates.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from src.schemas.article_schema import ArticleMetadata
from src.utils.date_utils import parse_date
from src.utils.logger import get_logger

logger = get_logger("extractor.metadata")


def extract_metadata(soup: BeautifulSoup, base_url: str = "") -> ArticleMetadata:
    """
    Extract rich metadata from the parsed HTML document.

    Priority order for each field:
    1. JSON-LD (``application/ld+json`` script blocks)
    2. Open Graph meta tags (``og:*``)
    3. Standard HTML meta tags
    4. HTML5 time elements / itemprop attributes

    Parameters
    ----------
    soup:
        Parsed BeautifulSoup document.
    base_url:
        The page URL (used for relative canonical resolution).

    Returns
    -------
    ArticleMetadata
    """
    ld = _extract_jsonld(soup)
    og = _extract_opengraph(soup)
    standard = _extract_standard_meta(soup)

    og_title = og.get("og:title") or ld.get("headline") or standard.get("title")
    og_description = og.get("og:description") or ld.get("description") or standard.get("description")
    og_image = og.get("og:image") or ld.get("image")
    canonical = og.get("og:url") or standard.get("canonical") or base_url
    keywords_raw = standard.get("keywords", "")
    keywords = [k.strip() for k in re.split(r"[,;]", keywords_raw) if k.strip()] if keywords_raw else []

    return ArticleMetadata(
        og_title=og_title,
        og_description=og_description,
        og_image=og_image if isinstance(og_image, str) else None,
        canonical_url=canonical,
        keywords=keywords,
    )


def extract_author(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract author name from common meta / itemprop patterns.

    Returns the first non-empty author string found, or ``None``.
    """
    # JSON-LD
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                author = item.get("author")
                if isinstance(author, dict):
                    name = author.get("name", "")
                elif isinstance(author, list):
                    name = author[0].get("name", "") if author else ""
                else:
                    name = str(author) if author else ""
                if name.strip():
                    return name.strip()
        except Exception:
            continue

    # Meta tags
    for attr, val in [
        ("name", "author"),
        ("name", "article:author"),
        ("property", "article:author"),
    ]:
        tag = soup.find("meta", attrs={attr: val})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()

    # itemprop="author"
    tag = soup.find(attrs={"itemprop": "author"})
    if tag:
        name_tag = tag.find(attrs={"itemprop": "name"})
        text = (name_tag or tag).get_text(strip=True)
        if text:
            return text

    return None


def extract_published_date(soup: BeautifulSoup) -> Optional[Any]:
    """
    Extract the article publication date from HTML.

    Tries JSON-LD, meta tags, and ``<time>`` elements in order.

    Returns
    -------
    Optional[datetime]
        UTC-aware datetime, or ``None``.
    """
    # JSON-LD
    ld = _extract_jsonld(soup)
    raw = ld.get("datePublished") or ld.get("dateModified")
    if raw:
        return parse_date(raw)

    # Meta tags
    for attr, val in [
        ("property", "article:published_time"),
        ("name", "published_time"),
        ("name", "date"),
        ("itemprop", "datePublished"),
    ]:
        tag = soup.find("meta", attrs={attr: val})
        if tag and tag.get("content"):
            dt = parse_date(str(tag["content"]))
            if dt:
                return dt

    # <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return parse_date(str(time_tag.get("datetime", "")))

    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_jsonld(soup: BeautifulSoup) -> dict[str, Any]:
    """Merge all JSON-LD script blocks into a flat dict."""
    merged: dict[str, Any] = {}
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    merged.update(item)
        except Exception:
            continue
    return merged


def _extract_opengraph(soup: BeautifulSoup) -> dict[str, str]:
    """Return a dict of all ``og:*`` and ``twitter:*`` meta properties."""
    tags: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name") or ""
        content = tag.get("content") or ""
        if prop and content:
            tags[prop] = content
    return tags


def _extract_standard_meta(soup: BeautifulSoup) -> dict[str, str]:
    """Return standard meta fields: title, description, canonical, keywords."""
    result: dict[str, str] = {}

    title_tag = soup.find("title")
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)

    for name in ("description", "keywords"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            result[name] = str(tag["content"]).strip()

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag and canonical_tag.get("href"):
        result["canonical"] = str(canonical_tag["href"]).strip()

    return result
