"""
src/schemas/article_schema.py
==============================
Pydantic v2 data models that define the canonical shape of a scraped article
and the intermediate search/fetch results flowing through the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from src.utils.date_utils import utcnow


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ArticleStatus(str, Enum):
    """Lifecycle state of an article as it moves through the pipeline."""

    RAW = "raw"
    CLEANED = "cleaned"
    VALIDATED = "validated"
    FAILED = "failed"


class ArticleSource(str, Enum):
    """Where the article URL was originally discovered."""

    DUCKDUCKGO = "duckduckgo"
    NEWSAPI = "newsapi"
    DIRECT = "direct"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ImageMeta(BaseModel):
    """Metadata for a single image found inside an article."""

    url: str
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ArticleMetadata(BaseModel):
    """Optional rich metadata that may or may not be present on a page."""

    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    canonical_url: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    language: Optional[str] = None
    word_count: Optional[int] = None
    reading_time_minutes: Optional[float] = None


# ---------------------------------------------------------------------------
# Core article model
# ---------------------------------------------------------------------------


class Article(BaseModel):
    """
    The canonical article document persisted to storage.

    All fields that might be absent use ``Optional`` with a ``None`` default;
    mandatory fields (``url``, ``title``) must be present for validation to pass.
    """

    # Identity
    article_id: str = Field(..., description="SHA-256 hash of the canonical URL")
    url: str = Field(..., description="Canonical article URL")
    source_url: Optional[str] = Field(None, description="Original URL before redirects")

    # Discovery
    source: ArticleSource = Field(default=ArticleSource.UNKNOWN)
    search_query: Optional[str] = None

    # Content
    title: str = Field(..., min_length=3)
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    body: Optional[str] = Field(None, description="Cleaned article body text")
    snippet: Optional[str] = Field(None, description="Short summary / search snippet")

    # Media
    images: list[ImageMeta] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None

    # Enrichment
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)
    tags: list[str] = Field(default_factory=list)

    # Provenance
    status: ArticleStatus = Field(default=ArticleStatus.RAW)
    scraped_at: datetime = Field(default_factory=utcnow)
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    # Validators
    @field_validator("url", "source_url", mode="before")
    @classmethod
    def strip_url(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def check_body_or_snippet(self) -> "Article":
        if not self.body and not self.snippet:
            raise ValueError("Article must have at least a body or snippet.")
        return self

    def is_complete(self) -> bool:
        """Return True when the article has all critical fields populated."""
        return bool(self.title and (self.body or self.snippet) and self.url)

    def domain(self) -> str:
        """Extract the netloc from the article URL."""
        try:
            return urlparse(self.url).netloc
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Search result intermediate models
# ---------------------------------------------------------------------------


class DuckDuckGoResult(BaseModel):
    """A single result returned by the DuckDuckGo search module."""

    title: str
    url: str
    snippet: Optional[str] = None
    source: str = ArticleSource.DUCKDUCKGO
    rank: Optional[int] = None


class NewsAPIArticle(BaseModel):
    """Raw article object returned by the NewsAPI client before enrichment."""

    title: str
    url: str
    description: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    source_name: Optional[str] = None
    url_to_image: Optional[str] = None
    content: Optional[str] = None
