"""
Canonical Article / ArticleImage schema shared by Module 1 and Module 2
(the integration contract).

Both modules import this schema so that the JSON produced by the scraper
(Module 1) can be fed directly into the bias analysis pipeline (Module 2)
without any translation layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ArticleImage(BaseModel):
    """A single image associated with an article."""

    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    source: str = Field(
        default="body",
        description="Where the image was found: 'og', 'twitter', 'json_ld', or 'body'.",
    )


class Article(BaseModel):
    """
    Canonical article record — the exact object persisted by Module 1's
    storage layer and the exact object Module 2's `article_loader.py`
    expects to receive.
    """

    article_id: str = Field(..., description="Stable unique identifier (e.g. SHA-256 of the URL).")
    title: str
    url: str
    source: str
    author: Optional[str] = None
    published_at: Optional[str] = None
    content: str
    images: List[ArticleImage] = Field(default_factory=list)
    language: Optional[str] = "en"
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @field_validator("title", "content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field must not be blank")
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "article_id": "1a2b3c4d5e6f",
                "title": "Sample Headline About Current Events",
                "url": "https://example.com/news/sample-article",
                "source": "example.com",
                "author": "Jane Doe",
                "published_at": "2026-06-20T10:00:00",
                "content": "Full cleaned article body text...",
                "images": [],
                "language": "en",
                "scraped_at": "2026-06-21T08:30:00",
            }
        }


__all__ = ["Article", "ArticleImage"]
