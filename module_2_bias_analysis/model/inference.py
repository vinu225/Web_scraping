"""
Runs sliding-window inference over chunks and aggregates chunk-level
predictions into a document-level score.

This is the only module that needs to know about *both* chunking and the
classifier — it ties `preprocessing/chunker.py` and
`model/roberta_classifier.py` together, handles batching for GPU/CPU
efficiency, and produces a single `(bias_score, confidence_score)` pair
per document from however many chunks the document split into.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List

from module_2_bias_analysis.config.settings import Settings
from module_2_bias_analysis.model.model_loader import load_model, resolve_device
from module_2_bias_analysis.model.roberta_classifier import RobertaBiasClassifier
from module_2_bias_analysis.model.tokenizer_manager import get_tokenizer
from module_2_bias_analysis.preprocessing.chunker import Chunk, chunk_by_tokens
from module_2_bias_analysis.utils.exceptions import EmptyContentError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentInferenceResult:
    """Aggregated model output for a full (possibly multi-chunk) article."""

    bias_score: float           # weighted-average probability of "biased", 0-1
    confidence_score: float     # how decisive/consistent the prediction was, 0-1
    chunk_count: int
    chunk_scores: List[float] = field(default_factory=list)


class BiasInferenceEngine:
    """
    Loads the RoBERTa model once and exposes `predict(text) ->
    DocumentInferenceResult`, transparently handling documents that exceed
    the model's max sequence length via sliding-window chunking.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        device = resolve_device(settings.device)
        self.tokenizer = get_tokenizer(settings.model_name)
        model, self.device = load_model(
            model_name=settings.model_name,
            model_path=settings.model_path or "",
            num_labels=settings.num_labels,
            device=device,
        )
        self.classifier = RobertaBiasClassifier(
            model=model,
            tokenizer=self.tokenizer,
            device=self.device,
            max_seq_length=settings.max_seq_length,
        )
        logger.info("BiasInferenceEngine ready (device=%s, model=%s)", self.device, settings.model_name)

    def _chunk(self, text: str) -> List[Chunk]:
        return chunk_by_tokens(
            text=text,
            tokenizer=self.tokenizer,
            max_seq_length=self.settings.max_seq_length,
            stride=self.settings.chunk_stride,
        )

    def predict(self, text: str) -> DocumentInferenceResult:
        """Run sliding-window inference over `text` and aggregate the result."""
        if not text or not text.strip():
            raise EmptyContentError("Cannot run inference on empty text.")

        chunks = self._chunk(text)
        if not chunks:
            raise EmptyContentError("Text produced no usable chunks after tokenization.")

        chunk_scores: List[float] = []
        weights: List[float] = []
        batch_size = self.settings.inference_batch_size

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            predictions = self.classifier.predict_batch([c.text for c in batch])
            for chunk, prediction in zip(batch, predictions):
                chunk_scores.append(prediction.bias_probability)
                weights.append(chunk.weight)

        bias_score = _weighted_average(chunk_scores, weights)
        confidence_score = _aggregate_confidence(chunk_scores)

        logger.info(
            "Inference complete: %d chunk(s), bias_score=%.4f, confidence=%.4f",
            len(chunks), bias_score, confidence_score,
        )

        return DocumentInferenceResult(
            bias_score=round(bias_score, 6),
            confidence_score=round(confidence_score, 6),
            chunk_count=len(chunks),
            chunk_scores=[round(s, 6) for s in chunk_scores],
        )


def _weighted_average(values: List[float], weights: List[float]) -> float:
    total_weight = sum(weights) or 1.0
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def _aggregate_confidence(chunk_scores: List[float]) -> float:
    """
    Confidence reflects two things:
    1. Decisiveness — how far each chunk's prediction sits from the
       uncertain midpoint (0.5). A chunk scoring 0.95 or 0.05 is decisive;
       one scoring 0.51 is not.
    2. Agreement — how consistent chunk predictions are with each other.
       High variance across chunks (e.g. one chunk screams "biased", the
       next looks neutral) should pull confidence down even if each
       individual chunk was individually decisive.
    """
    if not chunk_scores:
        return 0.0

    decisiveness = statistics.mean(abs(score - 0.5) * 2 for score in chunk_scores)

    if len(chunk_scores) > 1:
        spread = statistics.pstdev(chunk_scores)
        agreement_penalty = min(spread * 2, 1.0)
    else:
        agreement_penalty = 0.0

    confidence = decisiveness * (1 - agreement_penalty)
    return max(0.0, min(1.0, confidence))


__all__ = ["BiasInferenceEngine", "DocumentInferenceResult"]
