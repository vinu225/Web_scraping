"""
Unit tests for features/feature_engineering.py.

Validates that:
- Each individual feature function returns values in [0, 1].
- Biased/sensational text scores higher than neutral text on the relevant
  feature — i.e. the *direction* of each signal is correct.
- Edge cases (empty text, one-word input, all-caps, no punctuation) don't
  raise and return a valid float.
"""

from __future__ import annotations

import pytest

from module_2_bias_analysis.features.feature_engineering import (
    FeatureVector,
    compute_all,
    compute_emotional_intensity,
    compute_lexical_diversity,
    compute_linguistic_complexity,
    compute_sensational_language,
    compute_subjectivity,
    _tokenize_words,
)
from module_2_bias_analysis.scoring.scoring_engine import compute_feature_composite


# ─── Fixtures ────────────────────────────────────────────────────────────────

BIASED_TEXT = (
    "You won't believe the absolutely horrifying truth! I think it is obvious that this is "
    "the worst, most catastrophic betrayal in history. Furious citizens are OUTRAGED. "
    "Clearly this disgraceful disaster is unprecedented and everyone knows it. "
    "The shocking secret is finally exposed!!! This changes everything!!!"
)

NEUTRAL_TEXT = (
    "The city council voted seven to two on Tuesday to approve the annual budget. "
    "The plan allocates funding for road maintenance and public transit upgrades. "
    "Officials said implementation will begin in September. "
    "A follow-up report is scheduled before the end of the fiscal year."
)

ONE_WORD = "Hello"
EMPTY = ""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def is_valid_score(value) -> bool:
    return isinstance(value, float) and 0.0 <= value <= 1.0


# ─── compute_subjectivity ────────────────────────────────────────────────────

class TestComputeSubjectivity:
    def test_returns_float_in_range(self):
        words = _tokenize_words(BIASED_TEXT)
        score = compute_subjectivity(BIASED_TEXT, words)
        assert is_valid_score(score)

    def test_biased_higher_than_neutral(self):
        biased_score = compute_subjectivity(BIASED_TEXT, _tokenize_words(BIASED_TEXT))
        neutral_score = compute_subjectivity(NEUTRAL_TEXT, _tokenize_words(NEUTRAL_TEXT))
        assert biased_score > neutral_score

    def test_empty_text_returns_zero(self):
        assert compute_subjectivity(EMPTY, []) == 0.0

    def test_single_word_returns_valid_float(self):
        words = _tokenize_words(ONE_WORD)
        score = compute_subjectivity(ONE_WORD, words)
        assert is_valid_score(score)


# ─── compute_emotional_intensity ─────────────────────────────────────────────

class TestComputeEmotionalIntensity:
    def test_returns_float_in_range(self):
        words = _tokenize_words(BIASED_TEXT)
        score = compute_emotional_intensity(BIASED_TEXT, words)
        assert is_valid_score(score)

    def test_biased_higher_than_neutral(self):
        b = compute_emotional_intensity(BIASED_TEXT, _tokenize_words(BIASED_TEXT))
        n = compute_emotional_intensity(NEUTRAL_TEXT, _tokenize_words(NEUTRAL_TEXT))
        assert b > n

    def test_all_caps_increases_score(self):
        base = "This is a normal sentence with no emotion."
        caps = "THIS IS A NORMAL SENTENCE WITH NO EMOTION."
        wb = _tokenize_words(base)
        wc = _tokenize_words(caps)
        score_base = compute_emotional_intensity(base, wb)
        score_caps = compute_emotional_intensity(caps, wc)
        assert score_caps >= score_base

    def test_exclamation_marks_increase_score(self):
        no_excl = "Something happened and it was important."
        with_excl = "Something happened and it was important!!!"
        w1 = _tokenize_words(no_excl)
        w2 = _tokenize_words(with_excl)
        assert compute_emotional_intensity(with_excl, w2) >= compute_emotional_intensity(no_excl, w1)

    def test_empty_returns_zero(self):
        assert compute_emotional_intensity(EMPTY, []) == 0.0


# ─── compute_sensational_language ────────────────────────────────────────────

class TestComputeSensationalLanguage:
    def test_returns_float_in_range(self):
        words = _tokenize_words(BIASED_TEXT)
        score = compute_sensational_language(BIASED_TEXT, words)
        assert is_valid_score(score)

    def test_biased_higher_than_neutral(self):
        b = compute_sensational_language(BIASED_TEXT, _tokenize_words(BIASED_TEXT))
        n = compute_sensational_language(NEUTRAL_TEXT, _tokenize_words(NEUTRAL_TEXT))
        assert b > n

    @pytest.mark.parametrize("phrase", [
        "you won't believe",
        "shocking truth",
        "mind-blowing",
        "this changes everything",
    ])
    def test_known_clickbait_phrases_detected(self, phrase: str):
        text = f"A regular intro. {phrase.capitalize()} details follow."
        words = _tokenize_words(text)
        score = compute_sensational_language(text, words)
        assert score > 0.0

    def test_empty_returns_zero(self):
        assert compute_sensational_language(EMPTY, []) == 0.0


# ─── compute_lexical_diversity ───────────────────────────────────────────────

class TestComputeLexicalDiversity:
    def test_returns_float_in_range(self):
        words = _tokenize_words(BIASED_TEXT)
        score = compute_lexical_diversity(words)
        assert is_valid_score(score)

    def test_repetitive_text_lower_than_diverse(self):
        repetitive = " ".join(["the"] * 100)
        diverse = " ".join([f"word{chr(97 + i//26)}{chr(97 + i%26)}" for i in range(100)])
        score_rep = compute_lexical_diversity(_tokenize_words(repetitive))
        score_div = compute_lexical_diversity(_tokenize_words(diverse))
        assert score_div > score_rep

    def test_empty_returns_zero(self):
        assert compute_lexical_diversity([]) == 0.0

    def test_single_word_returns_one(self):
        assert compute_lexical_diversity(["hello"]) == 1.0

    def test_all_same_word_returns_low_value(self):
        words = ["repeat"] * 200
        score = compute_lexical_diversity(words)
        assert score < 0.2


# ─── compute_linguistic_complexity ───────────────────────────────────────────

class TestComputeLinguisticComplexity:
    def test_returns_float_in_range(self):
        words = _tokenize_words(BIASED_TEXT)
        score = compute_linguistic_complexity(BIASED_TEXT, words)
        assert is_valid_score(score)

    def test_complex_text_higher_than_simple(self):
        simple = "The dog ran. The cat sat. Birds flew. Fish swam. Kids played."
        complex_text = (
            "Anthropomorphic extrapolation of zoological behavioral characteristics "
            "necessitates comprehensive interdisciplinary methodological examination."
        )
        ws = _tokenize_words(simple)
        wc = _tokenize_words(complex_text)
        assert compute_linguistic_complexity(complex_text, wc) >= compute_linguistic_complexity(simple, ws)

    def test_empty_returns_zero(self):
        assert compute_linguistic_complexity(EMPTY, []) == 0.0


# ─── compute_all ─────────────────────────────────────────────────────────────

class TestComputeAll:
    def test_returns_feature_vector(self):
        result = compute_all(BIASED_TEXT)
        assert isinstance(result, FeatureVector)

    def test_all_scores_in_range(self):
        result = compute_all(BIASED_TEXT)
        for field_name in ("subjectivity_score", "emotional_intensity",
                           "sensational_language_score", "lexical_diversity",
                           "linguistic_complexity"):
            val = getattr(result, field_name)
            assert is_valid_score(val), f"{field_name}={val} out of [0,1]"

    def test_biased_features_directionally_higher(self):
        biased = compute_all(BIASED_TEXT)
        neutral = compute_all(NEUTRAL_TEXT)
        assert biased.subjectivity_score > neutral.subjectivity_score
        assert biased.emotional_intensity > neutral.emotional_intensity
        assert biased.sensational_language_score > neutral.sensational_language_score

    def test_empty_text_returns_zeros(self):
        result = compute_all(EMPTY)
        for field_name in ("subjectivity_score", "emotional_intensity",
                           "sensational_language_score"):
            assert getattr(result, field_name) == 0.0
