"""
Route handlers: POST /analyze-json, POST /analyze-html, POST /analyze-article.

Each endpoint accepts either a single object or a list (batch). For a
single-object request, a failure raises an HTTP error directly. For a
batch (list) request, per-article failures are isolated: the response
still returns 200 with whatever succeeded, plus an `errors` list
describing what didn't — so one malformed article never sinks an entire
batch submission.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from fastapi import APIRouter, HTTPException

from module_2_bias_analysis.config.settings import get_settings
from module_2_bias_analysis.pipeline.processing_pipeline import BiasAnalysisPipeline
from module_2_bias_analysis.schemas.bias_result import BatchAnalysisResponse
from module_2_bias_analysis.schemas.requests import (
    AnalyzeArticleRequest,
    AnalyzeHTMLRequest,
    AnalyzeJSONRequest,
    HTMLArticleInput,
    JSONArticleInput,
)
from module_2_bias_analysis.utils.exceptions import BiasAnalysisError
from module_2_bias_analysis.utils.logger import get_logger
from shared.schemas import Article

logger = get_logger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_pipeline() -> BiasAnalysisPipeline:
    """Process-wide singleton pipeline (and therefore singleton model load)."""
    return BiasAnalysisPipeline(settings=get_settings())


def _envelope(results, errors, was_batch: bool) -> BatchAnalysisResponse:
    if not was_batch and errors and not results:
        # Single-article request that failed outright -> surface as an HTTP error.
        raise HTTPException(status_code=422, detail=errors[0]["error"])
    return BatchAnalysisResponse(count=len(results), results=results, errors=errors)


@router.post("/analyze-json", response_model=BatchAnalysisResponse, tags=["analysis"])
def analyze_json(payload: AnalyzeJSONRequest) -> BatchAnalysisResponse:
    """Analyze one JSON article object or a JSON array of articles."""
    was_batch = isinstance(payload, list)
    pipeline = get_pipeline()
    try:
        results, errors = pipeline.analyze_json(payload)
    except BiasAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _envelope(results, errors, was_batch)


@router.post("/analyze-html", response_model=BatchAnalysisResponse, tags=["analysis"])
def analyze_html(payload: AnalyzeHTMLRequest) -> BatchAnalysisResponse:
    """Analyze one HTML article payload or a list of them."""
    was_batch = isinstance(payload, list)
    pipeline = get_pipeline()
    try:
        results, errors = pipeline.analyze_html(payload)
    except BiasAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _envelope(results, errors, was_batch)


@router.post("/analyze-article", response_model=BatchAnalysisResponse, tags=["analysis"])
def analyze_article(payload: AnalyzeArticleRequest) -> BatchAnalysisResponse:
    """
    Analyze one or more canonical `Article` objects — the direct
    integration point for Module 1's scraper output.
    """
    was_batch = isinstance(payload, list)
    pipeline = get_pipeline()
    try:
        results, errors = pipeline.analyze_article(payload)
    except BiasAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _envelope(results, errors, was_batch)


@router.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


__all__ = ["router", "get_pipeline"]
