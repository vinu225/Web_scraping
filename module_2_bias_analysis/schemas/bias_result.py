"""
Pydantic schema for the BiasAnalysisResult output object.

The seven top-level fields (`article_id`, `title`, `bias_score`,
`subjectivity_score`, `emotional_intensity`, `confidence_score`,
`classification`) are exactly the contract specified for Module 2. The
remaining fields are optional diagnostics (extra feature scores + stage
timings) that production clients can ignore but that are useful for
debugging and for downstream modules (e.g. an explainability dashboard).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class FeatureScores(BaseModel):
    """Engineered linguistic features computed independently of the model."""

    subjectivity_score: float = Field(..., ge=0.0, le=1.0)
    emotional_intensity: float = Field(..., ge=0.0, le=1.0)
    sensational_language_score: float = Field(..., ge=0.0, le=1.0)
    lexical_diversity: float = Field(..., ge=0.0, le=1.0)
    linguistic_complexity: float = Field(..., ge=0.0, le=1.0)


class ProcessingTimings(BaseModel):
    """Per-stage execution time, in seconds, for a single analysis run."""

    loading_time_seconds: float = 0.0
    preprocessing_time_seconds: float = 0.0
    inference_time_seconds: float = 0.0
    scoring_time_seconds: float = 0.0
    total_time_seconds: float = 0.0


class BiasAnalysisResult(BaseModel):
    """Final output of the bias analysis pipeline for a single article."""

    # --- Required contract fields -----------------------------------------
    article_id: str
    title: str
    bias_score: float = Field(..., ge=0.0, le=1.0)
    subjectivity_score: float = Field(..., ge=0.0, le=1.0)
    emotional_intensity: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    classification: str

    # --- Extended diagnostics (optional) ------------------------------------
    sensational_language_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    lexical_diversity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    linguistic_complexity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    model_bias_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Raw RoBERTa prediction before feature blending."
    )
    chunk_count: Optional[int] = Field(default=None, ge=0)
    chunk_scores: Optional[List[float]] = None
    timings: Optional[ProcessingTimings] = None

    @field_validator("classification")
    @classmethod
    def _valid_classification(cls, value: str) -> str:
        allowed = {"Low Bias", "Moderate Bias", "High Bias", "Extreme Bias"}
        if value not in allowed:
            raise ValueError(f"classification must be one of {allowed}, got '{value}'")
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "article_id": "1a2b3c4d5e6f",
                "title": "Sample Headline About Current Events",
                "bias_score": 0.42,
                "subjectivity_score": 0.55,
                "emotional_intensity": 0.38,
                "confidence_score": 0.81,
                "classification": "Moderate Bias",
            }
        }


class BatchAnalysisResponse(BaseModel):
    """Envelope returned by all API endpoints, single article or batch alike."""

    count: int
    results: List[BiasAnalysisResult]
    errors: List[dict] = Field(default_factory=list)


__all__ = ["FeatureScores", "ProcessingTimings", "BiasAnalysisResult", "BatchAnalysisResponse"]
