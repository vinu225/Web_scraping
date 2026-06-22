"""
End-to-end pipeline orchestrator: load -> preprocess -> chunk ->
RoBERTa inference -> feature engineering -> score aggregation -> result
generation.

`BiasAnalysisPipeline` is the single object the API layer (and any other
caller) talks to. It is intentionally agnostic to *how* an article
arrived (JSON / HTML / Module 1 Article) — `analyze_text` is the shared
core, and the three `analyze_*` entry points each just normalize their
input down to (article_id, title, content) before calling it.

The RoBERTa inference engine is lazily instantiated (only on first use,
or injected explicitly) so that importing/using this module for testing
other stages does not require `torch`/`transformers` to be installed.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import List, Optional, Tuple, Union

from module_2_bias_analysis.config.settings import Settings, get_settings
from module_2_bias_analysis.features.feature_engineering import compute_all as compute_features
from module_2_bias_analysis.loaders.article_loader import load_article
from module_2_bias_analysis.loaders.html_loader import load_html, load_html_batch
from module_2_bias_analysis.loaders.json_loader import load_json
from module_2_bias_analysis.model.inference import BiasInferenceEngine, DocumentInferenceResult
from module_2_bias_analysis.preprocessing.deduplicator import remove_duplicate_paragraphs
from module_2_bias_analysis.preprocessing.text_cleaner import clean_text, clean_title
from module_2_bias_analysis.schemas.bias_result import BiasAnalysisResult, ProcessingTimings
from module_2_bias_analysis.schemas.requests import HTMLArticleInput, JSONArticleInput
from module_2_bias_analysis.scoring.scoring_engine import combine_scores
from module_2_bias_analysis.utils.exceptions import EmptyContentError
from module_2_bias_analysis.utils.logger import PipelineTimings, StageTimer, get_logger
from shared.schemas import Article

logger = get_logger(__name__)


class BiasAnalysisPipeline:
    """
    Orchestrates the full bias-analysis workflow for single articles and
    batches, across all three supported input sources.
    """

    def __init__(self, settings: Optional[Settings] = None, inference_engine: Optional[BiasInferenceEngine] = None):
        self.settings = settings or get_settings()
        # Lazy: `inference_engine` can be injected (e.g. a mock in tests),
        # or built on first real use via `self._engine`.
        self._inference_engine = inference_engine

    @property
    def inference_engine(self) -> BiasInferenceEngine:
        if self._inference_engine is None:
            logger.info("Lazily initializing BiasInferenceEngine...")
            self._inference_engine = BiasInferenceEngine(self.settings)
        return self._inference_engine

    # ------------------------------------------------------------------ #
    # Core: shared by all three input sources
    # ------------------------------------------------------------------ #
    def analyze_text(self, article_id: Optional[str], title: str, content: str) -> BiasAnalysisResult:
        """Run the full pipeline on already-loaded (article_id, title, content)."""
        timings = PipelineTimings()
        logger_ctx = logger

        with StageTimer("total", logger_ctx, timings):
            # --- Preprocessing ---------------------------------------------------
            with StageTimer("preprocessing", logger_ctx, timings):
                cleaned_title = clean_title(title) if title else "Untitled Article"
                cleaned_content = clean_text(content)
                cleaned_content = remove_duplicate_paragraphs(cleaned_content)

                if len(cleaned_content.strip()) < self.settings.min_content_length_chars:
                    raise EmptyContentError(
                        f"Article content too short after cleaning "
                        f"({len(cleaned_content.strip())} chars, minimum "
                        f"{self.settings.min_content_length_chars})."
                    )

            resolved_id = article_id or _derive_article_id(cleaned_title, cleaned_content)

            # --- RoBERTa inference (chunking happens inside the engine) -----------
            with StageTimer("inference", logger_ctx, timings):
                inference_result: DocumentInferenceResult = self.inference_engine.predict(cleaned_content)

            # --- Feature engineering + scoring -------------------------------------
            with StageTimer("scoring", logger_ctx, timings):
                features = compute_features(cleaned_content)
                scoring = combine_scores(
                    model_bias_score=inference_result.bias_score,
                    model_confidence=inference_result.confidence_score,
                    features=features,
                    model_weight=self.settings.model_weight,
                    feature_weight=self.settings.feature_weight,
                    low_bias_max=self.settings.low_bias_max,
                    moderate_bias_max=self.settings.moderate_bias_max,
                    high_bias_max=self.settings.high_bias_max,
                )

        result = BiasAnalysisResult(
            article_id=resolved_id,
            title=cleaned_title,
            bias_score=scoring.bias_score,
            subjectivity_score=features.subjectivity_score,
            emotional_intensity=features.emotional_intensity,
            confidence_score=scoring.confidence_score,
            classification=scoring.classification,
            sensational_language_score=features.sensational_language_score,
            lexical_diversity=features.lexical_diversity,
            linguistic_complexity=features.linguistic_complexity,
            model_bias_score=inference_result.bias_score,
            chunk_count=inference_result.chunk_count,
            chunk_scores=inference_result.chunk_scores,
            timings=ProcessingTimings(**timings.as_dict()),
        )

        logger.info(
            "Analysis complete: article_id=%s bias_score=%.4f classification=%s total_time=%.3fs",
            result.article_id, result.bias_score, result.classification, timings.total_time_seconds,
        )
        return result

    # ------------------------------------------------------------------ #
    # Entry points per input source
    #
    # Each returns (results, errors): `errors` collects per-article
    # failures (e.g. one malformed article in a 50-article batch) as
    # {"identifier": ..., "error": ...} dicts so a single bad article
    # never aborts the rest of the batch.
    # ------------------------------------------------------------------ #
    def analyze_json(
        self, payload: Union[JSONArticleInput, List[JSONArticleInput], dict, list]
    ) -> Tuple[List[BiasAnalysisResult], List[dict]]:
        with StageTimer("loading", logger):
            if isinstance(payload, JSONArticleInput):
                records = [payload]
            elif isinstance(payload, list) and payload and isinstance(payload[0], JSONArticleInput):
                records = payload
            else:
                records = load_json(payload)

        return _run_each(records, lambda r: self.analyze_text(r.article_id, r.title, r.content))

    def analyze_html(
        self, payload: Union[HTMLArticleInput, List[HTMLArticleInput]]
    ) -> Tuple[List[BiasAnalysisResult], List[dict]]:
        with StageTimer("loading", logger):
            if isinstance(payload, HTMLArticleInput):
                records = [load_html(payload)]
            else:
                records = load_html_batch(list(payload))

        return _run_each(records, lambda r: self.analyze_text(r.article_id, r.title, r.content))

    def analyze_article(
        self, payload: Union[Article, List[Article], dict, list, str]
    ) -> Tuple[List[BiasAnalysisResult], List[dict]]:
        with StageTimer("loading", logger):
            articles = load_article(payload)

        return _run_each(articles, lambda a: self.analyze_text(a.article_id, a.title, a.content))


def _run_each(records: List, analyze_fn) -> Tuple[List[BiasAnalysisResult], List[dict]]:
    """
    Run `analyze_fn` over every record, isolating failures: a single bad
    article is recorded in `errors` and skipped, rather than aborting the
    whole batch.
    """
    results: List[BiasAnalysisResult] = []
    errors: List[dict] = []
    for record in records:
        identifier = getattr(record, "article_id", None) or getattr(record, "title", "unknown")
        try:
            results.append(analyze_fn(record))
        except Exception as exc:  # noqa: BLE001 - intentionally broad: batch isolation
            logger.error("Failed to analyze article '%s': %s", identifier, exc)
            errors.append({"identifier": str(identifier), "error": str(exc)})
    return results, errors


def _derive_article_id(title: str, content: str) -> str:
    """Deterministic fallback id when the caller didn't supply one."""
    digest_input = f"{title}::{content[:200]}".encode("utf-8", errors="ignore")
    return hashlib.sha256(digest_input).hexdigest()[:16]


__all__ = ["BiasAnalysisPipeline"]
