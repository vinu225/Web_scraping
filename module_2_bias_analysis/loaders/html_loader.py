"""
Loads local HTML files or raw HTML strings (including cleaned HTML from
Module 1's scraper) and extracts a title + plain-text content suitable
for the preprocessing/inference stages.

This is intentionally lightweight compared to Module 1's
`extraction/article_extractor.py` — it assumes the HTML it receives is
either already article-focused (Module 1's cleaned output) or a generic
page where a best-effort "main content" heuristic is good enough, since
Module 2's job is bias *analysis*, not full-fidelity scraping.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from bs4 import BeautifulSoup

from module_2_bias_analysis.schemas.requests import HTMLArticleInput, JSONArticleInput
from module_2_bias_analysis.utils.exceptions import EmptyContentError, SchemaValidationError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)

# Tags whose content is never part of the article body.
_NON_CONTENT_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]

# Heuristic ordering of likely "main content" containers, most specific first.
_CONTENT_SELECTORS = [
    "article",
    "main",
    "[class*='article-body']",
    "[class*='post-content']",
    "[class*='entry-content']",
    "[class*='story-body']",
    "[itemprop='articleBody']",
]


def _resolve_html(source: Union[str, Path]) -> str:
    if isinstance(source, Path) or (isinstance(source, str) and source.strip().lower().endswith((".html", ".htm")) and Path(source).exists()):
        path = Path(source)
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise SchemaValidationError(f"Could not read HTML file '{path}': {exc}") from exc
    if isinstance(source, str):
        return source
    raise SchemaValidationError(f"Unsupported HTML source type: {type(source).__name__}")


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return None


def _extract_main_content(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(_NON_CONTENT_TAGS):
        tag.decompose()

    for selector in _CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            text = container.get_text(separator="\n\n", strip=True)
            if len(text) > 100:
                return text

    # Fallback: whole-page text, paragraph-separated.
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    if paragraphs:
        return "\n\n".join(paragraphs)

    return soup.get_text(separator="\n\n", strip=True)


def load_html(payload: HTMLArticleInput) -> JSONArticleInput:
    """Parse a single `HTMLArticleInput` into a normalized `JSONArticleInput`."""
    html = _resolve_html(payload.html)
    soup = BeautifulSoup(html, "lxml") if html.strip() else BeautifulSoup("", "lxml")

    title = payload.title or _extract_title(soup) or "Untitled Article"
    content = _extract_main_content(soup)

    if not content or not content.strip():
        raise EmptyContentError("No extractable text content found in the provided HTML.")

    logger.info("html_loader: extracted %d chars of content (title='%s')", len(content), title[:60])

    return JSONArticleInput(
        article_id=payload.article_id,
        title=title,
        content=content,
        url=payload.url,
        source=payload.source,
    )


def load_html_batch(payloads: List[HTMLArticleInput]) -> List[JSONArticleInput]:
    return [load_html(p) for p in payloads]


__all__ = ["load_html", "load_html_batch"]
