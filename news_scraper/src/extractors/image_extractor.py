"""
src/extractors/image_extractor.py
====================================
Extracts images from a BeautifulSoup document, prioritising the
Open Graph / JSON-LD hero image and filtering out icons/ads.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from src.schemas.article_schema import ImageMeta
from src.utils.logger import get_logger

logger = get_logger("extractor.images")

_MIN_WIDTH = 100   # pixels; ignore tiny images
_MIN_HEIGHT = 100

# Patterns indicating tracking pixels, icons, or ad images
_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (r"pixel", r"tracker", r"beacon", r"logo", r"icon",
              r"avatar", r"favicon", r"spinner", r"loading", r"ad[s_\-]")
]


def extract_images(
    soup: BeautifulSoup,
    base_url: str = "",
    *,
    max_images: int = 10,
) -> list[ImageMeta]:
    """
    Extract relevant images from the parsed document.

    Parameters
    ----------
    soup:
        Parsed BeautifulSoup document.
    base_url:
        Page URL used to resolve relative ``src`` attributes.
    max_images:
        Maximum images to return (top ``max_images`` by estimated size).

    Returns
    -------
    list[ImageMeta]
        Filtered, deduplicated image metadata.
    """
    seen_urls: set[str] = set()
    images: list[ImageMeta] = []

    for img in soup.find_all("img"):
        src = _resolve_src(img, base_url)
        if not src or src in seen_urls:
            continue
        if _is_noise_image(img, src):
            continue

        seen_urls.add(src)
        images.append(
            ImageMeta(
                url=src,
                alt=img.get("alt", "").strip() or None,
                width=_parse_dim(img.get("width")),
                height=_parse_dim(img.get("height")),
            )
        )
        if len(images) >= max_images:
            break

    logger.debug("Extracted %d images from %s", len(images), base_url)
    return images


def extract_thumbnail(soup: BeautifulSoup, base_url: str = "") -> Optional[str]:
    """
    Return the single most prominent image URL for the article.

    Precedence: og:image → JSON-LD image → first extracted image.

    Parameters
    ----------
    soup:
        Parsed BeautifulSoup document.
    base_url:
        Page URL for relative URL resolution.

    Returns
    -------
    Optional[str]
        Absolute image URL, or ``None``.
    """
    # Open Graph
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return _resolve(str(og["content"]), base_url)

    # Twitter card
    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        return _resolve(str(twitter["content"]), base_url)

    # First extracted image
    images = extract_images(soup, base_url, max_images=1)
    return images[0].url if images else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_src(img: Tag, base_url: str) -> Optional[str]:
    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
    src = str(src).strip()
    if not src or src.startswith("data:"):
        return None
    return _resolve(src, base_url)


def _resolve(url: str, base: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http"):
        url = urljoin(base, url)
    return url


def _is_noise_image(img: Tag, src: str) -> bool:
    combined = f"{src} {img.get('class', '')} {img.get('alt', '')}".lower()
    return any(p.search(combined) for p in _NOISE_PATTERNS)


def _parse_dim(val: Optional[str | int]) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(str(val).replace("px", "").strip())
    except (ValueError, TypeError):
        return None
