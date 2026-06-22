"""
Pytest configuration and shared fixtures for Module 2 tests.

Fixtures here are available to all test modules without explicit import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

from module_2_bias_analysis.features.feature_engineering import FeatureVector
from module_2_bias_analysis.model.inference import DocumentInferenceResult

# ─── Paths ───────────────────────────────────────────────────────────────────

SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


# ─── Text fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def biased_text() -> str:
    return (
        "You won't believe the absolutely HORRIFYING truth! I think it is obvious that these "
        "disgraceful politicians have committed the worst, most catastrophic betrayal ever. "
        "Furious citizens are slamming their outrageous incompetence. Clearly this shocking "
        "disaster is unprecedented and everyone knows it is getting worse. This changes everything!!!"
    )


@pytest.fixture(scope="session")
def neutral_text() -> str:
    return (
        "The city council voted seven to two on Tuesday to approve the proposed budget for "
        "the upcoming fiscal year. The plan allocates funding for road maintenance, public transit "
        "upgrades, and expansion of the downtown library. A follow-up report is scheduled for the "
        "end of the fiscal year. Officials said implementation will begin in September."
    )


# ─── Feature vector fixtures ─────────────────────────────────────────────────

@pytest.fixture
def extreme_bias_features() -> FeatureVector:
    return FeatureVector(
        subjectivity_score=0.95,
        emotional_intensity=0.90,
        sensational_language_score=0.88,
        lexical_diversity=0.75,
        linguistic_complexity=0.30,
    )


@pytest.fixture
def low_bias_features() -> FeatureVector:
    return FeatureVector(
        subjectivity_score=0.04,
        emotional_intensity=0.02,
        sensational_language_score=0.01,
        lexical_diversity=0.83,
        linguistic_complexity=0.58,
    )


# ─── Mock inference engine ───────────────────────────────────────────────────

@pytest.fixture
def mock_inference_engine() -> MagicMock:
    """An inference engine that always returns a deterministic medium-bias result."""
    engine = MagicMock()
    engine.predict.return_value = DocumentInferenceResult(
        bias_score=0.60,
        confidence_score=0.80,
        chunk_count=2,
        chunk_scores=[0.58, 0.62],
    )
    return engine


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.min_content_length_chars = 50
    settings.model_weight = 0.7
    settings.feature_weight = 0.3
    settings.low_bias_max = 0.25
    settings.moderate_bias_max = 0.50
    settings.high_bias_max = 0.75
    return settings
