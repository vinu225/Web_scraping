"""
Unit tests for scoring/scoring_engine.py.

Covers: classification bands, feature composite calculation, score
combination logic, and confidence-modulation under model/feature
agreement vs. disagreement.
"""

from __future__ import annotations

import pytest

from module_2_bias_analysis.features.feature_engineering import FeatureVector
from module_2_bias_analysis.scoring.scoring_engine import (
    ScoringResult,
    classify_bias_score,
    combine_scores,
    compute_feature_composite,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def low_bias_features() -> FeatureVector:
    return FeatureVector(
        subjectivity_score=0.05,
        emotional_intensity=0.03,
        sensational_language_score=0.02,
        lexical_diversity=0.82,
        linguistic_complexity=0.55,
    )


@pytest.fixture
def extreme_bias_features() -> FeatureVector:
    return FeatureVector(
        subjectivity_score=0.95,
        emotional_intensity=0.90,
        sensational_language_score=0.88,
        lexical_diversity=0.75,
        linguistic_complexity=0.30,
    )


# ─── classify_bias_score ─────────────────────────────────────────────────────

class TestClassifyBiasScore:
    @pytest.mark.parametrize("score, expected_label", [
        (0.00, "Low Bias"),
        (0.25, "Low Bias"),
        (0.26, "Moderate Bias"),
        (0.50, "Moderate Bias"),
        (0.51, "High Bias"),
        (0.75, "High Bias"),
        (0.76, "Extreme Bias"),
        (1.00, "Extreme Bias"),
    ])
    def test_boundary_values(self, score: float, expected_label: str):
        assert classify_bias_score(score) == expected_label

    def test_custom_thresholds(self):
        assert classify_bias_score(0.30, low_bias_max=0.40) == "Low Bias"
        assert classify_bias_score(0.30, low_bias_max=0.20) == "Moderate Bias"


# ─── compute_feature_composite ───────────────────────────────────────────────

class TestComputeFeatureComposite:
    def test_returns_float_in_range(self, extreme_bias_features):
        score = compute_feature_composite(extreme_bias_features)
        assert 0.0 <= score <= 1.0

    def test_low_bias_features_give_low_composite(self, low_bias_features):
        score = compute_feature_composite(low_bias_features)
        assert score < 0.2

    def test_extreme_bias_features_give_high_composite(self, extreme_bias_features):
        score = compute_feature_composite(extreme_bias_features)
        assert score > 0.7

    def test_composite_uses_correct_features(self):
        # Only subjectivity, emotional_intensity, sensational_language_score
        # contribute; lexical_diversity and linguistic_complexity do not.
        features_a = FeatureVector(
            subjectivity_score=1.0,
            emotional_intensity=1.0,
            sensational_language_score=1.0,
            lexical_diversity=0.0,
            linguistic_complexity=0.0,
        )
        features_b = FeatureVector(
            subjectivity_score=1.0,
            emotional_intensity=1.0,
            sensational_language_score=1.0,
            lexical_diversity=1.0,  # changed
            linguistic_complexity=1.0,  # changed
        )
        assert compute_feature_composite(features_a) == pytest.approx(compute_feature_composite(features_b))


# ─── combine_scores ──────────────────────────────────────────────────────────

class TestCombineScores:
    def test_returns_scoring_result(self, low_bias_features):
        result = combine_scores(
            model_bias_score=0.1,
            model_confidence=0.9,
            features=low_bias_features,
        )
        assert isinstance(result, ScoringResult)

    def test_bias_score_in_range(self, extreme_bias_features):
        result = combine_scores(
            model_bias_score=0.9,
            model_confidence=0.8,
            features=extreme_bias_features,
        )
        assert 0.0 <= result.bias_score <= 1.0

    def test_confidence_score_in_range(self, low_bias_features):
        result = combine_scores(
            model_bias_score=0.1,
            model_confidence=0.85,
            features=low_bias_features,
        )
        assert 0.0 <= result.confidence_score <= 1.0

    def test_classification_matches_bias_score(self, extreme_bias_features):
        result = combine_scores(
            model_bias_score=0.95,
            model_confidence=0.9,
            features=extreme_bias_features,
        )
        expected = classify_bias_score(result.bias_score)
        assert result.classification == expected

    def test_model_feature_agreement_boosts_confidence(self, extreme_bias_features):
        """When model and features agree (both high), confidence should be higher
        than when they strongly disagree."""
        # Agree: model=high, features=high
        result_agree = combine_scores(
            model_bias_score=0.9,
            model_confidence=0.8,
            features=extreme_bias_features,
        )
        # Disagree: model=low, features=high
        low_feats = FeatureVector(
            subjectivity_score=0.95,
            emotional_intensity=0.90,
            sensational_language_score=0.88,
            lexical_diversity=0.75,
            linguistic_complexity=0.30,
        )
        result_disagree = combine_scores(
            model_bias_score=0.05,
            model_confidence=0.8,
            features=low_feats,
        )
        assert result_agree.confidence_score > result_disagree.confidence_score

    def test_weights_normalized_when_not_summing_to_one(self, low_bias_features):
        """Weights should be normalized; result should still be in [0, 1]."""
        result = combine_scores(
            model_bias_score=0.5,
            model_confidence=0.7,
            features=low_bias_features,
            model_weight=2.0,
            feature_weight=1.0,
        )
        assert 0.0 <= result.bias_score <= 1.0

    def test_zero_weights_falls_back_to_defaults(self, low_bias_features):
        result = combine_scores(
            model_bias_score=0.5,
            model_confidence=0.7,
            features=low_bias_features,
            model_weight=0.0,
            feature_weight=0.0,
        )
        assert 0.0 <= result.bias_score <= 1.0

    def test_low_model_confidence_reduces_final_confidence(self, extreme_bias_features):
        high_conf = combine_scores(0.9, 0.95, extreme_bias_features)
        low_conf = combine_scores(0.9, 0.10, extreme_bias_features)
        assert high_conf.confidence_score > low_conf.confidence_score
