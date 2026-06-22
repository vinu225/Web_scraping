"""
Pydantic request schemas for /analyze-json, /analyze-html, /analyze-article.

Each endpoint accepts either a single object or a list, so one schema
(`Union[T, List[T]]`) backs both single-article inference and batch
processing, satisfying the "support both" requirement without duplicating
endpoints.
"""

from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field

from shared.schemas import Article


class JSONArticleInput(BaseModel):
    """
    Minimal article shape accepted by /analyze-json.

    Intentionally looser than `shared.schemas.Article` (e.g. `article_id`
    is optional and will be derived from the URL/title if omitted) since
    JSON submitted directly by a client may not have passed through
    Module 1's pipeline.
    """

    article_id: Optional[str] = None
    title: str
    content: str
    url: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None


class HTMLArticleInput(BaseModel):
    """Payload accepted by /analyze-html."""

    html: str
    article_id: Optional[str] = None
    title: Optional[str] = Field(
        default=None, description="Override title; if omitted it is parsed from the HTML <title>/<h1>."
    )
    url: Optional[str] = None
    source: Optional[str] = None


# --- Endpoint request bodies (single OR batch) ---------------------------------

AnalyzeJSONRequest = Union[JSONArticleInput, List[JSONArticleInput]]
AnalyzeHTMLRequest = Union[HTMLArticleInput, List[HTMLArticleInput]]
AnalyzeArticleRequest = Union[Article, List[Article]]


__all__ = [
    "JSONArticleInput",
    "HTMLArticleInput",
    "AnalyzeJSONRequest",
    "AnalyzeHTMLRequest",
    "AnalyzeArticleRequest",
]
