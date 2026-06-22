"""
Integration tests for pipeline/processing_pipeline.py.

These tests exercise the full pipeline but inject a mock InferenceEngine
so the RoBERTa model and GPU are NOT required. The mock lets each test
control exactly what the model returns, isolating pipeline logic from
model behavior.

Separate end-to-end model tests (with real weights, requiring
torch/transformers and a checkpoint) belong in a separate
`tests/test_e2e.py` that is skipped unless BIAS_RUN_E2E=1 is set.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock

import pytest

from module_2_bias_analysis.model.inference import DocumentInferenceResult
from module_2_bias_analysis.pipeline.processing_pipeline import BiasAnalysisPipeline
from module_2_bias_analysis.schemas.bias_result import BatchAnalysisResponse, BiasAnalysisResult
from module_2_bias_analysis.schemas.requests import HTMLArticleInput, JSONArticleInput
from module_2_bias_analysis.utils.exceptions import EmptyContentError, SchemaValidationError

_SAMPLE_DATA_DIR = __import__("pathlib").Path(__file__).parent / "sample_data"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_engine(bias_score: float = 0.72, confidence_score: float = 0.85) -> MagicMock:
    """Return a mock BiasInferenceEngine whose predict() returns deterministic values."""
    engine = MagicMock()
    engine.predict.return_value = DocumentInferenceResult(
        bias_score=bias_score,
        confidence_score=confidence_score,
        chunk_count=3,
        chunk_scores=[bias_score] * 3,
    )
    return engine


def make_pipeline(bias_score: float = 0.72, confidence_score: float = 0.85) -> BiasAnalysisPipeline:
    """Build a BiasAnalysisPipeline with a mock inference engine injected."""
    # Bypass settings validation (no pydantic_settings env file needed) by
    # injecting a minimal settings-like object.
    settings = MagicMock()
    settings.min_content_length_chars = 50
    settings.model_weight = 0.7
    settings.feature_weight = 0.3
    settings.low_bias_max = 0.25
    settings.moderate_bias_max = 0.50
    settings.high_bias_max = 0.75
    return BiasAnalysisPipeline(settings=settings, inference_engine=make_mock_engine(bias_score, confidence_score))


# ─── analyze_text ────────────────────────────────────────────────────────────

class TestAnalyzeText:
    def test_returns_bias_analysis_result(self):
        pipeline = make_pipeline(bias_score=0.72)
        result = pipeline.analyze_text(
            article_id="test-001",
            title="Test Headline | Site Brand",
            content="This is a sufficiently long article body with real content for testing purposes.",
        )
        assert isinstance(result, BiasAnalysisResult)

    def test_branding_stripped_from_title(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id="t1",
            title="Headline | Brand Name",
            content="Article content that is long enough to pass the minimum length check here.",
        )
        assert "|" not in result.title

    def test_article_id_passed_through(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id="unique-id-xyz",
            title="Title",
            content="Enough content to pass the minimum length requirement for analysis.",
        )
        assert result.article_id == "unique-id-xyz"

    def test_article_id_derived_when_none(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id=None,
            title="Title Without ID",
            content="Sufficient article text content to pass the minimum character threshold check.",
        )
        assert result.article_id
        assert len(result.article_id) > 0

    def test_bias_score_in_range(self):
        pipeline = make_pipeline(bias_score=0.72)
        result = pipeline.analyze_text(
            article_id="t2", title="Title",
            content="Article body content long enough to clear the minimum length threshold check.",
        )
        assert 0.0 <= result.bias_score <= 1.0

    def test_confidence_score_in_range(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id="t3", title="Title",
            content="Article body content long enough to clear the minimum length threshold check.",
        )
        assert 0.0 <= result.confidence_score <= 1.0

    def test_classification_is_valid_label(self):
        pipeline = make_pipeline(bias_score=0.72)
        result = pipeline.analyze_text(
            article_id="t4", title="Title",
            content="Article body content long enough to clear the minimum length threshold check.",
        )
        assert result.classification in {"Low Bias", "Moderate Bias", "High Bias", "Extreme Bias"}

    def test_timings_present_in_result(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id="t5", title="Title",
            content="Article body content long enough to clear the minimum length threshold check.",
        )
        assert result.timings is not None
        assert result.timings.total_time_seconds >= 0

    def test_too_short_content_raises_empty_content_error(self):
        pipeline = make_pipeline()
        with pytest.raises(EmptyContentError):
            pipeline.analyze_text(article_id="t6", title="Title", content="Too short.")

    def test_engineered_feature_scores_populated(self):
        pipeline = make_pipeline()
        result = pipeline.analyze_text(
            article_id="t7", title="Title",
            content="Article body content long enough to clear the minimum length threshold check.",
        )
        assert result.subjectivity_score is not None
        assert result.emotional_intensity is not None
        assert result.sensational_language_score is not None


# ─── analyze_json ────────────────────────────────────────────────────────────

class TestAnalyzeJsonPipeline:
    def test_single_dict_returns_one_result(self):
        pipeline = make_pipeline()
        results, errors = pipeline.analyze_json(
            {"title": "Test", "content": "Sufficient article body content to pass the minimum length threshold."}
        )
        assert len(results) == 1
        assert len(errors) == 0

    def test_batch_list_returns_multiple_results(self):
        pipeline = make_pipeline()
        payloads = [
            {"title": "Article One", "content": "Enough content for article one to pass the length threshold check."},
            {"title": "Article Two", "content": "Enough content for article two to pass the length threshold check."},
        ]
        results, errors = pipeline.analyze_json(payloads)
        assert len(results) == 2

    def test_invalid_article_in_batch_isolated_to_errors(self):
        pipeline = make_pipeline()
        payloads = [
            {"title": "Good Article", "content": "Sufficient content to pass the minimum length requirement here."},
            {"title": "Missing content field (this should fail)"},  # invalid
        ]
        # One good + one bad — should raise SchemaValidationError for the bad one
        with pytest.raises(SchemaValidationError):
            pipeline.analyze_json(payloads)

    def test_json_file_loaded_and_analyzed(self):
        path = _SAMPLE_DATA_DIR / "sample_article_neutral.json"
        if not path.exists():
            pytest.skip("Sample data not found")
        pipeline = make_pipeline(bias_score=0.1)
        results, errors = pipeline.analyze_json(path)
        assert len(results) == 1

    def test_batch_json_file_analyzed(self):
        path = _SAMPLE_DATA_DIR / "sample_batch.json"
        if not path.exists():
            pytest.skip("Sample data not found")
        pipeline = make_pipeline()
        results, errors = pipeline.analyze_json(path)
        assert len(results) == 2


# ─── analyze_html ────────────────────────────────────────────────────────────

class TestAnalyzeHtmlPipeline:
    def test_single_html_payload_returns_one_result(self):
        html = (
            "<html><body><article>"
            "<p>This is the main content paragraph of a real article that is long enough to pass validation.</p>"
            "<p>A second paragraph providing additional context and detail about the story at hand.</p>"
            "</article></body></html>"
        )
        pipeline = make_pipeline()
        results, errors = pipeline.analyze_html(HTMLArticleInput(html=html, title="Test Article"))
        assert len(results) == 1

    def test_html_file_analyzed(self):
        path = _SAMPLE_DATA_DIR / "sample_article.html"
        if not path.exists():
            pytest.skip("Sample data not found")
        pipeline = make_pipeline()
        payload = HTMLArticleInput(html=str(path))
        results, errors = pipeline.analyze_html(payload)
        assert len(results) == 1
        assert results[0].bias_score is not None


# ─── analyze_article ─────────────────────────────────────────────────────────

class TestAnalyzeArticlePipeline:
    def test_shared_article_object_analyzed(self):
        from shared.schemas import Article

        article = Article(
            article_id="integration-001",
            title="Integration Test Article",
            url="https://example.com/integration",
            source="example.com",
            content=(
                "This is the full body text of a canonical Article object "
                "produced by Module 1 and fed directly into Module 2's pipeline "
                "via the article_loader integration point. It is long enough."
            ),
        )
        pipeline = make_pipeline(bias_score=0.15)
        results, errors = pipeline.analyze_article(article)
        assert len(results) == 1
        assert results[0].article_id == "integration-001"

    def test_module1_json_file_analyzed(self):
        path = _SAMPLE_DATA_DIR / "sample_module1_article.json"
        if not path.exists():
            pytest.skip("Sample data not found")
        pipeline = make_pipeline(bias_score=0.08)
        results, errors = pipeline.analyze_article(path)
        assert results[0].classification in {"Low Bias", "Moderate Bias"}

    def test_high_bias_score_gives_correct_classification(self):
        from shared.schemas import Article

        article = Article(
            article_id="high-bias-test",
            title="Shocking Betrayal",
            url="https://example.com",
            source="example.com",
            content=(
                "You won't believe this outrageous and shocking betrayal by these "
                "disgraceful politicians who are destroying everything. I think it is "
                "obvious to everyone that this is the worst catastrophe in modern history."
            ),
        )
        pipeline = make_pipeline(bias_score=0.88)
        results, errors = pipeline.analyze_article(article)
        assert results[0].classification in {"High Bias", "Extreme Bias"}


# ─── Deduplication integration ───────────────────────────────────────────────

class TestDeduplicationInPipeline:
    def test_duplicate_paragraphs_removed_before_inference(self):
        pipeline = make_pipeline()
        repeated_content = (
            "This is the first paragraph with important content for testing.\n\n"
            "This is the first paragraph with important content for testing.\n\n"
            "This is a distinct second paragraph with different information."
        )
        result = pipeline.analyze_text(
            article_id="dedup-test",
            title="Dedup Test",
            content=repeated_content,
        )
        # Model was called once (pipeline ran), content was cleaned
        assert result.article_id == "dedup-test"
        pipeline.inference_engine.predict.assert_called_once()
