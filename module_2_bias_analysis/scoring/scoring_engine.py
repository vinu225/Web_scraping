"""
Combines RoBERTa predictions with engineered features into the final bias
score, confidence score, and classification label.

Kept as pure functions operating on plain floats/dataclasses (no pydantic,
no torch) so the scoring logic — arguably the most "opinionated" part of
the whole module — is the easiest piece to unit test and to tune.
"""

from __future__ import annotations

from dataclasses import dataclass

from module_2_bias_analysis.features.feature_engineering import FeatureVector

# Within the engineered-feature composite, these three are direct bias
# signals; lexical diversity and linguistic complexity are reported as
# diagnostics but are not used to push the bias score itself, since
# "complex" or "diverse" writing is not inherently more or less biased.
_FEATURE_COMPOSITE_WEIGHTS = {
    "subjectivity_score": 0.45,
    "emotional_intensity": 0.30,
    "sensational_language_score": 0.25,
}


@dataclass
class ScoringResult:
    bias_score: float
    confidence_score: float
    classification: str
    feature_composite: float


def compute_feature_composite(features: FeatureVector) -> float:
    """Weighted blend of the three bias-correlated engineered features."""
    return (
        features.subjectivity_score * _FEATURE_COMPOSITE_WEIGHTS["subjectivity_score"]
        + features.emotional_intensity * _FEATURE_COMPOSITE_WEIGHTS["emotional_intensity"]
        + features.sensational_language_score * _FEATURE_COMPOSITE_WEIGHTS["sensational_language_score"]
    )


def classify_bias_score(
    bias_score: float,
    low_bias_max: float = 0.25,
    moderate_bias_max: float = 0.50,
    high_bias_max: float = 0.75,
) -> str:
    """Map a 0-1 bias score to a classification label per the spec's bands."""
    if bias_score <= low_bias_max:
        return "Low Bias"
    if bias_score <= moderate_bias_max:
        return "Moderate Bias"
    if bias_score <= high_bias_max:
        return "High Bias"
    return "Extreme Bias"


def combine_scores(
    model_bias_score: float,
    model_confidence: float,
    features: FeatureVector,
    model_weight: float = 0.7,
    feature_weight: float = 0.3,
    low_bias_max: float = 0.25,
    moderate_bias_max: float = 0.50,
    high_bias_max: float = 0.75,
) -> ScoringResult:
    """
    Produce the final bias score, confidence score, and classification.

    - `bias_score` = weighted blend of the RoBERTa prediction and the
      engineered-feature composite (`model_weight` + `feature_weight`
      should sum to 1.0; the function normalizes them defensively if not).
    - `confidence_score` = the model's own chunk-aggregation confidence,
      moderated by how much the model and the feature-based signal agree.
      Large disagreement between the two independent signals should make
      the platform less, not more, confident in the final call.
    """
    total_weight = model_weight + feature_weight
    if total_weight <= 0:
        model_weight, feature_weight = 0.7, 0.3
    else:
        model_weight, feature_weight = model_weight / total_weight, feature_weight / total_weight

    feature_composite = compute_feature_composite(features)
    bias_score = (model_weight * model_bias_score) + (feature_weight * feature_composite)
    bias_score = max(0.0, min(1.0, bias_score))

    agreement = 1 - abs(model_bias_score - feature_composite)
    confidence_score = max(0.0, min(1.0, model_confidence * (0.5 + 0.5 * agreement)))

    classification = classify_bias_score(bias_score, low_bias_max, moderate_bias_max, high_bias_max)

    return ScoringResult(
        bias_score=round(bias_score, 4),
        confidence_score=round(confidence_score, 4),
        classification=classification,
        feature_composite=round(feature_composite, 4),
    )


__all__ = ["ScoringResult", "compute_feature_composite", "classify_bias_score", "combine_scores"]
