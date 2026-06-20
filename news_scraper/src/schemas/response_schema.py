"""
src/schemas/response_schema.py
================================
Standardised API/module response wrappers used throughout the pipeline.
Keeps all inter-module contracts explicit and type-safe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata attached to list responses."""

    page: int = 1
    page_size: int = 0
    total_results: int = 0
    has_next: bool = False


class ScraperResponse(BaseModel, Generic[T]):
    """
    Generic envelope for every module's return value.

    Attributes
    ----------
    success:
        ``True`` if the operation completed without a fatal error.
    data:
        The payload; ``None`` on failure.
    error:
        Human-readable error message when ``success=False``.
    meta:
        Arbitrary extra metadata (timing, pagination, etc.).
    timestamp:
        UTC time at response creation.
    """

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def ok(cls, data: T, **meta: Any) -> "ScraperResponse[T]":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(cls, error: str, **meta: Any) -> "ScraperResponse[T]":
        return cls(success=False, error=error, meta=meta)


class SearchResponse(BaseModel):
    """Structured response from DuckDuckGo or NewsAPI search calls."""

    query: str
    results: list[Any] = Field(default_factory=list)
    total_found: int = 0
    page: int = 1
    elapsed_ms: float = 0.0
    source: str = "unknown"


class ExtractionResponse(BaseModel):
    """Result of extracting a single article URL."""

    url: str
    success: bool
    article: Optional[Any] = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class PipelineStats(BaseModel):
    """Aggregate statistics emitted after a pipeline run completes."""

    total_urls: int = 0
    successful: int = 0
    failed: int = 0
    skipped_duplicates: int = 0
    elapsed_seconds: float = 0.0
    articles_saved: int = 0
    errors: list[str] = Field(default_factory=list)
