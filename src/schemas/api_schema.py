"""
src/schemas/api_schema.py
==========================
Pydantic v2 request/response models for the FastAPI layer.
These are the wire-format contracts for all /api/v1/* endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input / Request models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    """
    Body for POST /api/v1/scrape — bypass InputProcessor, go straight to
    the Orchestrator with explicit keywords or URLs.
    """
    keywords: list[str] = Field(default_factory=list, description="Search keywords to look up")
    urls: list[str] = Field(default_factory=list, description="Direct article URLs to scrape")
    use_duckduckgo: bool = Field(default=True, description="Enable DuckDuckGo search")
    use_newsapi: bool = Field(default=False, description="Enable NewsAPI search (requires NEWSAPI_KEY)")
    lang: str = Field(default="en", description="ISO 639-1 language filter")
    max_results: int = Field(default=5, ge=1, le=50, description="Max DDG results per keyword")
    max_workers: int = Field(default=5, ge=1, le=20, description="Concurrent extraction threads")
    min_body_length: int = Field(default=200, ge=0, description="Minimum article body char count")


class ProcessTextRequest(BaseModel):
    """
    Body for POST /api/v1/process (JSON variant) when sending plain text.
    Used when the client can't send multipart/form-data.
    """
    text: Optional[str] = Field(None, description="Plain text news claim / article excerpt")
    url: Optional[str] = Field(None, description="Direct article URL to scrape (skips Gemini)")
    image_base64: Optional[str] = Field(None, description="Base64-encoded image data")
    mime_type: str = Field(default="image/jpeg", description="MIME type for base64 image")
    use_duckduckgo: bool = Field(default=True)
    use_newsapi: bool = Field(default=False)
    lang: str = Field(default="en")
    max_results: int = Field(default=5, ge=1, le=50)
    max_workers: int = Field(default=5, ge=1, le=20)
    min_body_length: int = Field(default=200, ge=0)


# ---------------------------------------------------------------------------
# Structured article summary (used in pipeline response)
# ---------------------------------------------------------------------------

class ArticleSummary(BaseModel):
    """Compact article summary returned in API responses."""
    article_id: str
    title: str
    url: str
    body_preview: Optional[str] = Field(None, description="First 300 chars of cleaned body")
    source: str = "unknown"
    published_at: Optional[datetime] = None
    word_count: Optional[int] = None
    author: Optional[str] = None
    thumbnail_url: Optional[str] = None


# ---------------------------------------------------------------------------
# InputResult response model
# ---------------------------------------------------------------------------

class InputResultResponse(BaseModel):
    """
    Serialisable version of src.input.processor.InputResult.
    Returned as part of ProcessResponse.
    """
    path: Literal["fast", "slow"]
    input_mode: Literal["image", "text", "url"]
    url: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    claim: Optional[str] = None
    raw_ocr: Optional[str] = None
    confidence: Optional[str] = None
    entities: dict[str, list[str]] = Field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline response
# ---------------------------------------------------------------------------

class PipelineResponse(BaseModel):
    """Summary of what the scraping pipeline produced."""
    total_urls: int = 0
    successful: int = 0
    failed: int = 0
    articles_saved: int = 0
    elapsed_seconds: float = 0.0
    articles: list[ArticleSummary] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Combined response
# ---------------------------------------------------------------------------

class ProcessResponse(BaseModel):
    """
    Full response for POST /api/v1/process.
    Combines what InputProcessor decided + what the pipeline collected.
    """
    input_result: Optional[InputResultResponse] = None
    pipeline: PipelineResponse = Field(default_factory=PipelineResponse)
    elapsed_seconds: float = 0.0


class HealthResponse(BaseModel):
    """Response for GET /api/v1/health."""
    status: str = "ok"
    gemini_ready: bool = False
    newsapi_ready: bool = False
    version: str = "1.0.0"
