"""
src/preprocess/unicode_normalizer.py
======================================
Unicode normalisation utilities: NFC normalisation, smart-quote replacement,
control-character stripping, and mojibake repair via ftfy.
"""

from __future__ import annotations

import re
import unicodedata

try:
    import ftfy
    _HAS_FTFY = True
except ImportError:
    _HAS_FTFY = False

from src.utils.logger import get_logger

logger = get_logger("preprocess.unicode")

# Mapping of common "fancy" punctuation to ASCII equivalents
_REPLACEMENTS: dict[str, str] = {
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
    "\u201c": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u2013": "-",   # EN DASH
    "\u2014": "--",  # EM DASH
    "\u2026": "...", # HORIZONTAL ELLIPSIS
    "\u00a0": " ",   # NON-BREAKING SPACE
    "\u200b": "",    # ZERO-WIDTH SPACE
    "\u200c": "",    # ZERO-WIDTH NON-JOINER
    "\u200d": "",    # ZERO-WIDTH JOINER
    "\ufeff": "",    # BOM
}

# Regex matching C0/C1 control characters (except newline, tab, carriage-return)
_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def normalize(text: str) -> str:
    """
    Full Unicode normalisation pipeline.

    Steps:
    1. Repair mojibake with ``ftfy`` (if available).
    2. NFC normalisation (canonical decomposition, then canonical composition).
    3. Replace smart quotes and typographic dashes with ASCII equivalents.
    4. Strip C0/C1 control characters.

    Parameters
    ----------
    text:
        Raw text extracted from HTML.

    Returns
    -------
    str
        Clean, NFC-normalised text.
    """
    if not text:
        return text

    # Repair encoding issues
    if _HAS_FTFY:
        text = ftfy.fix_text(text)

    # NFC normalisation
    text = unicodedata.normalize("NFC", text)

    # Replace typographic characters
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)

    # Strip control characters
    text = _CTRL_CHARS.sub("", text)

    return text
