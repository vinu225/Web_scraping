"""
input_processor.py  (root shim — backward compatibility)
─────────────────────────────────────────────────────────
This file is kept for backward compatibility.
The actual implementation has moved to: src/input/processor.py

Simply re-exports everything from the new location.
"""

from src.input.processor import (  # noqa: F401
    InputProcessor,
    InputResult,
    _extract_first_url,
    _heuristic_keywords,
    _parse_json_response,
    _build_slow_result,
    _SLOW_PATH_PROMPT,
)

__all__ = [
    "InputProcessor",
    "InputResult",
    "_extract_first_url",
    "_heuristic_keywords",
    "_parse_json_response",
    "_build_slow_result",
    "_SLOW_PATH_PROMPT",
]
