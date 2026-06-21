"""
src/preprocess/language_detector.py
=====================================
Lightweight language detection wrapper around ``langdetect``.
"""

from __future__ import annotations

from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("preprocess.langdetect")

try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 42  # deterministic results
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False
    logger.warning("langdetect not installed — language detection disabled.")


def detect_language(text: str, min_length: int = 50) -> Optional[str]:
    """
    Detect the ISO 639-1 language code of *text*.

    Parameters
    ----------
    text:
        Text to inspect (article title + body recommended).
    min_length:
        Minimum number of characters needed to attempt detection.
        Returns ``None`` if the text is shorter than this threshold.

    Returns
    -------
    Optional[str]
        Two-letter ISO 639-1 language code (e.g. ``"en"``, ``"de"``),
        or ``None`` on failure / insufficient text.
    """
    if not _HAS_LANGDETECT:
        return None

    sample = text.strip()
    if len(sample) < min_length:
        return None

    try:
        lang = detect(sample)
        logger.debug("Detected language: %s", lang)
        return lang
    except Exception as exc:  # noqa: BLE001
        logger.debug("Language detection failed: %s", exc)
        return None


def is_english(text: str) -> bool:
    """Convenience wrapper returning ``True`` if *text* is English."""
    return detect_language(text) == "en"
