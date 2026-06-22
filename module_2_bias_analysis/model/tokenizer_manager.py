"""
Loads and caches the HuggingFace RoBERTa tokenizer.

Import of `transformers` is deferred and guarded so that the rest of this
package (preprocessing, feature engineering, scoring, loaders) can be
imported and unit tested in environments where `torch`/`transformers`
are not installed. Any attempt to actually *use* the tokenizer without
the dependency present raises a clear `ModelLoadError`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from module_2_bias_analysis.utils.exceptions import ModelLoadError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from transformers import AutoTokenizer  # type: ignore

    _TRANSFORMERS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when transformers is absent
    AutoTokenizer = None  # type: ignore
    _TRANSFORMERS_AVAILABLE = False


@lru_cache(maxsize=4)
def get_tokenizer(model_name: str) -> Any:
    """
    Return a cached `PreTrainedTokenizerBase` for `model_name`.

    Cached via `lru_cache` so repeated calls (e.g. once per analyzed
    article) don't re-download or re-instantiate the tokenizer.
    """
    if not _TRANSFORMERS_AVAILABLE:
        raise ModelLoadError(
            "The 'transformers' package is not installed. Install project "
            "dependencies with `pip install -r requirements.txt` to enable "
            "RoBERTa-based inference."
        )

    logger.info("Loading tokenizer for '%s'...", model_name)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise ModelLoadError(f"Failed to load tokenizer '{model_name}': {exc}") from exc

    logger.info("Tokenizer for '%s' loaded successfully.", model_name)
    return tokenizer


__all__ = ["get_tokenizer"]
