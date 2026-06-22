"""
RoBERTa sequence-classification model definition for bias scoring.

`RobertaBiasClassifier` is a thin business-logic wrapper around a loaded
HuggingFace model + tokenizer pair: it knows that output index 1 is the
"biased" class and exposes a clean `predict_proba` API, so
`model/inference.py` never has to touch raw logits or softmax math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from module_2_bias_analysis.utils.exceptions import InferenceError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import torch  # type: ignore

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False

# Output index whose probability represents "biased" in a binary
# (unbiased=0, biased=1) classification head.
BIASED_CLASS_INDEX = 1


@dataclass
class ChunkPrediction:
    """Bias probability for a single text chunk."""

    bias_probability: float
    raw_logits: List[float]


class RobertaBiasClassifier:
    """Wraps a loaded RoBERTa sequence-classification model + tokenizer."""

    def __init__(self, model: Any, tokenizer: Any, device: str, max_seq_length: int = 512):
        if not _TORCH_AVAILABLE:
            raise InferenceError("torch is not installed; cannot run RoBERTa inference.")
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.max_seq_length = max_seq_length

    def predict_batch(self, texts: List[str]) -> List[ChunkPrediction]:
        """
        Run a forward pass over a batch of pre-chunked text strings and
        return a `ChunkPrediction` per input, each carrying the softmax
        probability of the "biased" class.
        """
        if not texts:
            return []

        try:
            encoded = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self.max_seq_length,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                logits = self.model(**encoded).logits
                probabilities = torch.softmax(logits, dim=-1)
        except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
            raise InferenceError(f"RoBERTa forward pass failed: {exc}") from exc

        predictions: List[ChunkPrediction] = []
        for row_logits, row_probs in zip(logits.tolist(), probabilities.tolist()):
            predictions.append(
                ChunkPrediction(
                    bias_probability=float(row_probs[BIASED_CLASS_INDEX]),
                    raw_logits=row_logits,
                )
            )
        return predictions


__all__ = ["RobertaBiasClassifier", "ChunkPrediction", "BIASED_CLASS_INDEX"]
