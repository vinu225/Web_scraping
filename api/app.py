"""
api/app.py
===========
FastAPI application for the News Scraper pipeline.

Endpoints
─────────
POST /api/v1/process        Full pipeline: image/text/url → InputProcessor → Orchestrator
POST /api/v1/process/json   Same as above but accepts JSON body (no file upload)
POST /api/v1/scrape         Direct scrape: keywords/URLs → Orchestrator (no Gemini)
GET  /api/v1/health         Health check — lists which services are configured
GET  /docs                  Auto-generated Swagger UI (FastAPI default)
GET  /redoc                 ReDoc UI

Usage
─────
    # Start the server:
    python api_server.py

    # Or from code:
    import uvicorn
    from api.app import create_app
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
"""

from __future__ import annotations

import asyncio
import base64
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.dependencies import (
    _init_input_processor,
    get_orchestrator,
    is_gemini_ready,
    is_newsapi_ready,
)
from src.schemas.api_schema import (
    ArticleSummary,
    HealthResponse,
    InputResultResponse,
    PipelineResponse,
    ProcessResponse,
    ProcessTextRequest,
    ScrapeRequest,
)
from src.utils.logger import get_logger

logger = get_logger("api.app")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise expensive singletons (InputProcessor)."""
    logger.info("API server starting up...")
    _init_input_processor()
    yield
    logger.info("API server shutting down.")


def create_app() -> FastAPI:
    """Factory — returns a configured FastAPI application."""
    app = FastAPI(
        title="News Scraper API",
        description=(
            "Production-ready news scraping pipeline with Gemini-powered input processing. "
            "Submit images, text claims, or URLs and receive verified article content."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow all origins for local dev. Tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routes(app)
    return app


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def _register_routes(app: FastAPI) -> None:

    # ── Health ──────────────────────────────────────────────────────────────

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health check",
    )
    async def health():
        """
        Returns the operational status of the API and its key dependencies.
        - `gemini_ready`: True if GEMINI_API_KEY is configured and InputProcessor loaded
        - `newsapi_ready`: True if NEWSAPI_KEY is configured
        """
        return HealthResponse(
            status="ok",
            gemini_ready=is_gemini_ready(),
            newsapi_ready=is_newsapi_ready(),
        )

    # ── Full process endpoint (multipart file upload) ────────────────────────

    @app.post(
        "/api/v1/process",
        response_model=ProcessResponse,
        tags=["Pipeline"],
        summary="Process image/text/URL through full pipeline",
    )
    async def process_multipart(
        image: Optional[UploadFile] = File(None, description="News image to analyse"),
        text: Optional[str] = Form(None, description="Plain text news claim"),
        url: Optional[str] = Form(None, description="Direct article URL"),
        use_duckduckgo: bool = Form(True),
        use_newsapi: bool = Form(False),
        lang: str = Form("en"),
        max_results: int = Form(5),
        max_workers: int = Form(5),
        min_body_length: int = Form(200),
    ):
        """
        **Full pipeline endpoint** — accepts multipart/form-data.

        Priority order:
        1. `image` file → Gemini reverse image search → keywords/URL
        2. `text` → Gemini keyword extraction (skips image search)
        3. `url` → Direct scrape, no Gemini needed

        Returns matched articles from the downstream scraping pipeline.
        """
        if not image and not text and not url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least one of: image file, text, or url.",
            )

        t0 = time.perf_counter()
        input_result_data = None
        keywords: list[str] = []
        direct_urls: list[str] = []

        # ── Determine input mode ──────────────────────────────────────────────
        if image:
            # Image mode — needs Gemini
            processor = _get_processor_or_raise()
            image_bytes = await image.read()
            mime_type = image.content_type or "image/jpeg"

            ir = await asyncio.get_event_loop().run_in_executor(
                None, lambda: processor.process(image_bytes=image_bytes, mime_type=mime_type)
            )
            input_result_data = _to_input_result_response(ir)

            if ir.path == "fast" and ir.url:
                direct_urls = [ir.url]
            else:
                keywords = ir.keywords or []

        elif text:
            # Text mode — needs Gemini
            processor = _get_processor_or_raise()
            ir = await asyncio.get_event_loop().run_in_executor(
                None, lambda: processor.process_text(text)
            )
            input_result_data = _to_input_result_response(ir)
            keywords = ir.keywords or []

        elif url:
            # Direct URL mode — no Gemini needed
            from src.input.processor import InputProcessor as IP
            ir = IP.process_url(url)
            input_result_data = _to_input_result_response(ir)
            direct_urls = [url]

        # ── Run the scraping pipeline ─────────────────────────────────────────
        pipeline_response = await _run_pipeline(
            keywords=keywords,
            direct_urls=direct_urls,
            use_duckduckgo=use_duckduckgo,
            use_newsapi=use_newsapi,
            lang=lang,
            max_results=max_results,
            max_workers=max_workers,
            min_body_length=min_body_length,
        )

        return ProcessResponse(
            input_result=input_result_data,
            pipeline=pipeline_response,
            elapsed_seconds=time.perf_counter() - t0,
        )

    # ── Full process endpoint (JSON body) ────────────────────────────────────

    @app.post(
        "/api/v1/process/json",
        response_model=ProcessResponse,
        tags=["Pipeline"],
        summary="Process image (base64) / text / URL — JSON body variant",
    )
    async def process_json(body: ProcessTextRequest):
        """
        **Full pipeline endpoint** — accepts `application/json`.

        Use this instead of `/process` when sending base64-encoded images or
        plain text from non-browser clients.

        Priority order:
        1. `image_base64` → Gemini reverse image search → keywords/URL
        2. `text` → Gemini keyword extraction (skips image search)
        3. `url` → Direct scrape, no Gemini needed
        """
        if not body.image_base64 and not body.text and not body.url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least one of: image_base64, text, or url.",
            )

        t0 = time.perf_counter()
        input_result_data = None
        keywords: list[str] = []
        direct_urls: list[str] = []

        if body.image_base64:
            processor = _get_processor_or_raise()
            try:
                image_bytes = base64.b64decode(body.image_base64)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid base64 image data.",
                )
            ir = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: processor.process(image_bytes=image_bytes, mime_type=body.mime_type),
            )
            input_result_data = _to_input_result_response(ir)
            if ir.path == "fast" and ir.url:
                direct_urls = [ir.url]
            else:
                keywords = ir.keywords or []

        elif body.text:
            processor = _get_processor_or_raise()
            ir = await asyncio.get_event_loop().run_in_executor(
                None, lambda: processor.process_text(body.text)
            )
            input_result_data = _to_input_result_response(ir)
            keywords = ir.keywords or []

        elif body.url:
            from src.input.processor import InputProcessor as IP
            ir = IP.process_url(body.url)
            input_result_data = _to_input_result_response(ir)
            direct_urls = [body.url]

        pipeline_response = await _run_pipeline(
            keywords=keywords,
            direct_urls=direct_urls,
            use_duckduckgo=body.use_duckduckgo,
            use_newsapi=body.use_newsapi,
            lang=body.lang,
            max_results=body.max_results,
            max_workers=body.max_workers,
            min_body_length=body.min_body_length,
        )

        return ProcessResponse(
            input_result=input_result_data,
            pipeline=pipeline_response,
            elapsed_seconds=time.perf_counter() - t0,
        )

    # ── Direct scrape endpoint ───────────────────────────────────────────────

    @app.post(
        "/api/v1/scrape",
        response_model=ProcessResponse,
        tags=["Pipeline"],
        summary="Direct scrape — bypass InputProcessor",
    )
    async def scrape(body: ScrapeRequest):
        """
        **Direct scrape endpoint** — no Gemini required.

        Accepts explicit keywords and/or URLs and runs them straight through
        the DuckDuckGo / NewsAPI / BS4Extractor pipeline.

        Use this when you already have search keywords or article URLs.
        """
        if not body.keywords and not body.urls:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least one keyword or URL.",
            )

        t0 = time.perf_counter()
        pipeline_response = await _run_pipeline(
            keywords=body.keywords,
            direct_urls=body.urls,
            use_duckduckgo=body.use_duckduckgo,
            use_newsapi=body.use_newsapi,
            lang=body.lang,
            max_results=body.max_results,
            max_workers=body.max_workers,
            min_body_length=body.min_body_length,
        )

        return ProcessResponse(
            input_result=None,
            pipeline=pipeline_response,
            elapsed_seconds=time.perf_counter() - t0,
        )

    # ── Root redirect ────────────────────────────────────────────────────────

    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({"message": "News Scraper API — visit /docs for Swagger UI"})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _run_pipeline(
    *,
    keywords: list[str],
    direct_urls: list[str],
    use_duckduckgo: bool,
    use_newsapi: bool,
    lang: str,
    max_results: int,
    max_workers: int,
    min_body_length: int,
) -> PipelineResponse:
    """
    Run the Orchestrator in a thread-pool executor (non-blocking).
    Collects produced articles and wraps them in a PipelineResponse.
    """
    from src.schemas.article_schema import Article

    # Collect articles as they complete
    collected: list[Article] = []

    def on_article(article: Article) -> None:
        collected.append(article)

    def _run():
        orch = get_orchestrator(max_workers=max_workers, min_body_length=min_body_length)
        # Reset state for fresh run by creating a new orchestrator per request
        from src.pipeline.orchestrator import Orchestrator
        fresh_orch = Orchestrator(
            max_workers=max_workers,
            min_body_length=min_body_length,
            language_filter=lang if lang else None,
        )
        return fresh_orch.run(
            keywords=keywords,
            direct_urls=direct_urls,
            use_duckduckgo=use_duckduckgo,
            use_newsapi=use_newsapi,
            newsapi_language=lang,
            ddg_max_results=max_results,
            on_stats=False,
        )

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, _run)

    # Load saved articles to include in response
    articles = _load_recent_articles(stats.articles_saved)

    return PipelineResponse(
        total_urls=stats.total_urls,
        successful=stats.successful,
        failed=stats.failed,
        articles_saved=stats.articles_saved,
        elapsed_seconds=stats.elapsed_seconds,
        articles=articles,
        errors=stats.errors,
    )


def _load_recent_articles(count: int) -> list[ArticleSummary]:
    """Load the most recently cleaned articles from disk to include in API response."""
    if count == 0:
        return []

    try:
        import json
        from config.settings import settings

        cleaned_dir = settings.cleaned_data_dir
        files = sorted(cleaned_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        summaries = []

        for path in files[:count]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                body = data.get("body") or ""
                summaries.append(ArticleSummary(
                    article_id=data.get("article_id", ""),
                    title=data.get("title", "Untitled"),
                    url=data.get("url", ""),
                    body_preview=body[:300] if body else None,
                    source=data.get("source", "unknown"),
                    published_at=data.get("published_at"),
                    word_count=data.get("metadata", {}).get("word_count"),
                    author=data.get("author"),
                    thumbnail_url=data.get("thumbnail_url"),
                ))
            except Exception:
                continue

        return summaries
    except Exception as exc:
        logger.warning("Could not load recent articles: %s", exc)
        return []


def _get_processor_or_raise():
    """Return the InputProcessor or raise HTTP 503."""
    from api.dependencies import _input_processor_instance, _input_processor_error
    if _input_processor_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_input_processor_error or "InputProcessor (Gemini) is not available. Set GEMINI_API_KEY in .env.",
        )
    return _input_processor_instance


def _to_input_result_response(ir) -> InputResultResponse:
    """Convert an InputResult dataclass into a serialisable Pydantic model."""
    return InputResultResponse(
        path=ir.path,
        input_mode=ir.input_mode,
        url=ir.url,
        keywords=ir.keywords,
        claim=ir.claim,
        raw_ocr=ir.raw_ocr,
        confidence=ir.confidence,
        entities=ir.entities,
        error=ir.error,
    )
