"""
Loads model weights and manages GPU/CPU device placement.

Separated from `roberta_classifier.py` so that "how do we get a loaded,
device-placed model object" is independent of "what do we do with it
once we have it" — the loader can be swapped (e.g. to load a quantized
or ONNX checkpoint later) without touching classifier/inference logic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Tuple

from module_2_bias_analysis.utils.exceptions import ModelLoadError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import torch  # type: ignore
    from transformers import AutoModelForSequenceClassification  # type: ignore

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when torch is absent
    torch = None  # type: ignore
    AutoModelForSequenceClassification = None  # type: ignore
    _TORCH_AVAILABLE = False


def resolve_device(device_setting: str) -> str:
    """
    Resolve a configured device string ("auto", "cpu", "cuda", "cuda:0",
    ...) into a concrete device string, falling back to CPU whenever CUDA
    is requested but unavailable.
    """
    if not _TORCH_AVAILABLE:
        return "cpu"

    if device_setting == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"

    if device_setting.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("Device '%s' requested but CUDA is unavailable; falling back to CPU.", device_setting)
        return "cpu"

    return device_setting


@lru_cache(maxsize=2)
def load_model(model_name: str, model_path: str, num_labels: int, device: str) -> Tuple[Any, str]:
    """
    Load (and cache) a `AutoModelForSequenceClassification`, placed on
    `device` and set to eval mode.

    Args:
        model_name: Base architecture / HF hub id (e.g. "roberta-base").
        model_path: Path to a fine-tuned checkpoint, or "" to use
            `model_name` directly with a freshly initialized classification
            head (useful for end-to-end testing of the pipeline before a
            fine-tuned bias-detection checkpoint is available).
        num_labels: Number of output classes (2 for binary biased/unbiased).
        device: Resolved device string ("cpu" or "cuda[:N]").

    Returns:
        (model, device) tuple.
    """
    if not _TORCH_AVAILABLE:
        raise ModelLoadError(
            "The 'torch' and 'transformers' packages are not installed. "
            "Install project dependencies with `pip install -r requirements.txt`."
        )

    source = model_path or model_name
    if not model_path:
        logger.warning(
            "No fine-tuned model_path configured — loading '%s' with a freshly "
            "initialized classification head. Predictions will be uninformative "
            "until a fine-tuned bias-classification checkpoint is supplied via "
            "BIAS_MODEL_PATH.",
            model_name,
        )

    logger.info("Loading model '%s' onto device '%s'...", source, device)
    try:
        model = AutoModelForSequenceClassification.from_pretrained(source, num_labels=num_labels)
        model.to(device)
        model.eval()
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise ModelLoadError(f"Failed to load model '{source}': {exc}") from exc

    logger.info("Model '%s' ready on '%s'.", source, device)
    return model, device


__all__ = ["resolve_device", "load_model"]
