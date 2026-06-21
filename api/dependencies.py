"""
api/dependencies.py
====================
FastAPI dependency injection providers.

Provides cached singleton instances of Orchestrator and InputProcessor
so they are created once at startup and reused across requests.
"""

from __future__ import annotations

import functools
from typing import Optional

from fastapi import HTTPException, status

from config.settings import settings
from src.pipeline.orchestrator import Orchestrator
from src.utils.logger import get_logger

logger = get_logger("api.dependencies")


# ---------------------------------------------------------------------------
# Orchestrator singleton
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _get_orchestrator_instance(max_workers: int, min_body_length: int) -> Orchestrator:
    """Create and cache a single Orchestrator instance."""
    logger.info("Creating Orchestrator singleton (workers=%d)", max_workers)
    return Orchestrator(max_workers=max_workers, min_body_length=min_body_length)


def get_orchestrator(max_workers: int = 5, min_body_length: int = 200) -> Orchestrator:
    """FastAPI dependency: return the shared Orchestrator."""
    return _get_orchestrator_instance(max_workers=max_workers, min_body_length=min_body_length)


# ---------------------------------------------------------------------------
# InputProcessor singleton (optional — only works if GEMINI_API_KEY is set)
# ---------------------------------------------------------------------------

_input_processor_instance: Optional[object] = None
_input_processor_error: Optional[str] = None


def _init_input_processor() -> None:
    """Try to initialise the InputProcessor at startup. Fails gracefully."""
    global _input_processor_instance, _input_processor_error

    api_key = settings.gemini_api_key
    if not api_key or api_key.startswith("your_"):
        _input_processor_error = (
            "GEMINI_API_KEY is not configured. "
            "Set it in .env to enable image and text analysis."
        )
        logger.warning(_input_processor_error)
        return

    try:
        from src.input.processor import InputProcessor
        _input_processor_instance = InputProcessor(api_key=api_key)
        logger.info("InputProcessor initialised successfully.")
    except Exception as exc:
        _input_processor_error = f"InputProcessor failed to initialise: {exc}"
        logger.error(_input_processor_error)


def get_input_processor():
    """
    FastAPI dependency: return the shared InputProcessor.
    Raises HTTP 503 if GEMINI_API_KEY is not configured or initialisation failed.
    """
    if _input_processor_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_input_processor_error or "InputProcessor is not available.",
        )
    return _input_processor_instance


def is_gemini_ready() -> bool:
    """Return True if InputProcessor initialised successfully."""
    return _input_processor_instance is not None


def is_newsapi_ready() -> bool:
    """Return True if a valid NewsAPI key is configured."""
    key = settings.newsapi_key
    return bool(key and not key.startswith("your_"))
