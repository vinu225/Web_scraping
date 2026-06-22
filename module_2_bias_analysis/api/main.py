"""
FastAPI application entrypoint for Module 2: Semantic Bias Analysis.

Lifecycle
---------
- On startup the pipeline singleton is *not* yet instantiated; the first
  POST request triggers lazy model loading so the server accepts health
  checks immediately even before the RoBERTa weights are downloaded.
- On shutdown any cached tokenizer/model state is released cleanly.

Running locally
---------------
    uvicorn module_2_bias_analysis.api.main:app --reload --port 8002

Environment variables (see config/settings.py for the full list)
-----------------------------------------------------------------
    BIAS_MODEL_NAME   : HuggingFace model id or local path (default: roberta-base)
    BIAS_MODEL_PATH   : Fine-tuned checkpoint path (optional)
    BIAS_DEVICE       : auto | cpu | cuda  (default: auto)
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from module_2_bias_analysis.api.routes import router
from module_2_bias_analysis.utils.exceptions import BiasAnalysisError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fake News Detection — Semantic Bias Analysis",
    description=(
        "Module 2 of the Fake News Detection Platform. "
        "Analyzes news articles and returns a bias score (0–1) "
        "powered by a RoBERTa transformer and linguistic feature engineering."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — open in dev; tighten `allow_origins` in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Global exception handler — converts domain errors into consistent JSON.
# ---------------------------------------------------------------------------

@app.exception_handler(BiasAnalysisError)
async def bias_analysis_error_handler(request: Request, exc: BiasAnalysisError) -> JSONResponse:
    logger.error("BiasAnalysisError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred.", "error_type": type(exc).__name__},
    )

# ---------------------------------------------------------------------------
# Request timing middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time-Seconds"] = f"{elapsed:.4f}"
    return response

# ---------------------------------------------------------------------------
# Startup / shutdown events
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Bias Analysis API starting up...")
    logger.info("Access interactive docs at /docs")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Bias Analysis API shutting down.")


__all__ = ["app"]
