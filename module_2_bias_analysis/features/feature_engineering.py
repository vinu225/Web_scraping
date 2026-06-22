"""
Computes subjectivity, emotional intensity, sensational-language, lexical
diversity, and linguistic complexity scores.

Deliberately implemented with only the standard library (`re`,
`collections`, `statistics`) plus small built-in lexicons rather than a
heavyweight NLP dependency: it keeps this module dependency-free,
fast, fully unit-testable in isolation, and transparent (every score is a
documented, inspectable formula rather than a black box).

All scores are normalized to [0.0, 1.0].
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import List

# ---------------------------------------------------------------------------
# Lexicons. Small, curated, and intentionally domain-general — good enough
# to produce directionally meaningful signals without external downloads.
# ---------------------------------------------------------------------------

_SUBJECTIVE_MARKERS = {
    "i think", "i believe", "i feel", "in my opinion", "arguably", "clearly",
    "obviously", "undoubtedly", "surely", "allegedly", "apparently", "claims",
    "claimed", "should", "must", "ought", "supposedly", "presumably",
    "frankly", "honestly", "shockingly", "unbelievably", "disgracefully",
    "needless to say", "everyone knows", "it is obvious",
}

_EMOTION_WORDS = {
    # fear / alarm
    "terrifying", "horrific", "alarming", "dangerous", "threat", "panic",
    "fear", "afraid", "dread", "catastrophic", "disaster",
    # anger
    "outrageous", "furious", "enraged", "disgraceful", "betrayal", "hatred",
    "slammed", "blasted", "fury", "rage",
    # sadness
    "heartbreaking", "devastating", "tragic", "tragedy", "grief", "sorrow",
    # joy / positivity (extreme)
    "amazing", "incredible", "miraculous", "triumphant", "thrilled",
    "ecstatic", "wonderful",
}

_SENSATIONAL_PHRASES = {
    "you won't believe", "shocking truth", "what happened next", "exposed",
    "secret", "miracle", "destroyed", "slams", "blasts", "epic fail",
    "goes viral", "breaks the internet", "the real reason", "mind-blowing",
    "jaw-dropping", "this changes everything", "never seen before",
}

_SUPERLATIVES = {
    "best", "worst", "biggest", "smallest", "greatest", "most", "least",
    "ultimate", "unprecedented", "unmatched",
}

_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_VOWEL_GROUPS_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


@dataclass
class FeatureVector:
    """Engineered linguistic features for a single document, all in [0, 1]."""

    subjectivity_score: float
    emotional_intensity: float
    sensational_language_score: float
    lexical_diversity: float
    linguistic_complexity: float


def _tokenize_words(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _split_sentences(text: str) -> List[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def _count_syllables(word: str) -> int:
    groups = _VOWEL_GROUPS_RE.findall(word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def compute_subjectivity(text: str, words: List[str]) -> float:
    """
    Ratio of subjective-language markers (opinion verbs, hedges, intensity
    adverbs) to total word count, scaled so a moderately opinionated
    article (roughly 1 marker per 40 words) lands near the middle of the
    range rather than near zero.
    """
    if not words:
        return 0.0
    lower_text = text.lower()
    marker_count = sum(lower_text.count(marker) for marker in _SUBJECTIVE_MARKERS)
    density = marker_count / max(len(words), 1)
    # Scale factor chosen so ~1 marker per 40 words -> ~0.5 score.
    return _clamp(density * 20.0)


def compute_emotional_intensity(text: str, words: List[str]) -> float:
    """
    Combines emotionally-charged vocabulary density, exclamation-mark
    frequency, and ALL-CAPS word frequency (a common emphasis device) into
    a single 0-1 intensity score.
    """
    if not words:
        return 0.0

    emotion_hits = sum(1 for w in words if w in _EMOTION_WORDS)
    emotion_density = emotion_hits / max(len(words), 1)

    exclamations = text.count("!")
    exclamation_density = exclamations / max(len(_split_sentences(text)), 1)

    raw_tokens = text.split()
    caps_words = [t for t in raw_tokens if len(t) > 2 and t.isupper() and t.isalpha()]
    caps_density = len(caps_words) / max(len(raw_tokens), 1)

    score = (
        _clamp(emotion_density * 15.0) * 0.5
        + _clamp(exclamation_density) * 0.3
        + _clamp(caps_density * 10.0) * 0.2
    )
    return _clamp(score)


def compute_sensational_language(text: str, words: List[str]) -> float:
    """
    Detects clickbait/sensational phrasing: stock sensational phrases,
    superlatives, and excessive punctuation (multi "!!!" / "???" runs).
    """
    if not words:
        return 0.0
    lower_text = text.lower()

    phrase_hits = sum(1 for phrase in _SENSATIONAL_PHRASES if phrase in lower_text)
    superlative_hits = sum(1 for w in words if w in _SUPERLATIVES)
    punctuation_runs = len(re.findall(r"[!?]{2,}", text))

    sentence_count = max(len(_split_sentences(text)), 1)
    score = (
        _clamp(phrase_hits / 3.0) * 0.5
        + _clamp(superlative_hits / max(len(words), 1) * 25.0) * 0.3
        + _clamp(punctuation_runs / sentence_count * 5.0) * 0.2
    )
    return _clamp(score)


def compute_lexical_diversity(words: List[str], window: int = 50) -> float:
    """
    Moving-Average Type-Token Ratio (MATTR): average type-token ratio
    computed over a sliding window of `window` words, then averaged across
    all windows. More robust than a raw type/token ratio, which is
    artificially deflated by document length.
    """
    if not words:
        return 0.0
    if len(words) <= window:
        unique = len(set(words))
        return _clamp(unique / len(words))

    ratios = []
    for start in range(0, len(words) - window + 1):
        win = words[start : start + window]
        ratios.append(len(set(win)) / window)
    return _clamp(statistics.mean(ratios))


def compute_linguistic_complexity(text: str, words: List[str]) -> float:
    """
    Approximate Flesch-Kincaid Grade Level, normalized to [0, 1] by
    clipping to a 0-20 grade-level range. Higher = more complex prose
    (longer sentences, more syllables per word).
    """
    sentences = _split_sentences(text)
    if not words or not sentences:
        return 0.0

    total_syllables = sum(_count_syllables(w) for w in words)
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = total_syllables / len(words)

    grade_level = (0.39 * words_per_sentence) + (11.8 * syllables_per_word) - 15.59
    grade_level = max(0.0, grade_level)
    return _clamp(grade_level / 20.0)


def compute_all(text: str) -> FeatureVector:
    """Compute the full feature vector for a document in one pass."""
    words = _tokenize_words(text)
    return FeatureVector(
        subjectivity_score=round(compute_subjectivity(text, words), 4),
        emotional_intensity=round(compute_emotional_intensity(text, words), 4),
        sensational_language_score=round(compute_sensational_language(text, words), 4),
        lexical_diversity=round(compute_lexical_diversity(words), 4),
        linguistic_complexity=round(compute_linguistic_complexity(text, words), 4),
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if math.isnan(value):
        return low
    return max(low, min(high, value))


__all__ = ["FeatureVector", "compute_all"]
