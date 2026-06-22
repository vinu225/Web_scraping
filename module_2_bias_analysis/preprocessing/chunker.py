"""
Sliding-window chunking for long articles that exceed the RoBERTa max
sequence length.

Two strategies are provided:

- `chunk_by_tokens`: exact, tokenizer-driven sliding window using the
  HuggingFace tokenizer's native `return_overflowing_tokens` support.
  This is what `model/inference.py` uses in production, since it
  guarantees every chunk fits within `max_seq_length` after the RoBERTa
  special tokens are added.
- `chunk_by_words`: an approximate, dependency-free fallback used when no
  tokenizer is available (unit tests, or a quick pre-tokenization pass for
  feature engineering, which operates on raw text rather than token ids).

Both return `Chunk` objects carrying the chunk text plus its approximate
weight (proportional to length), used later to weight chunk predictions
during aggregation so a 500-word chunk doesn't count the same as a
50-word trailing remainder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class Chunk:
    """A single chunk of article text ready for model inference."""

    text: str
    index: int
    token_count: Optional[int] = None
    word_count: Optional[int] = None

    @property
    def weight(self) -> float:
        """Relative weight for aggregation — proportional to chunk length."""
        return float(self.token_count or self.word_count or len(self.text.split()) or 1)


def chunk_by_words(
    text: str,
    max_words: int = 380,
    overlap_words: int = 60,
) -> List[Chunk]:
    """
    Approximate sliding-window chunking on whitespace-delimited words.

    `max_words` defaults to ~380, a conservative estimate for fitting
    within RoBERTa's 512-token limit (English averages ~1.3 tokens/word
    including subword splits, special tokens, etc.).
    """
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")

    if not text or not text.strip():
        return []

    words = text.split()
    if len(words) <= max_words:
        return [Chunk(text=text.strip(), index=0, word_count=len(words))]

    chunks: List[Chunk] = []
    step = max_words - overlap_words
    start = 0
    index = 0
    while start < len(words):
        window = words[start : start + max_words]
        chunks.append(Chunk(text=" ".join(window), index=index, word_count=len(window)))
        index += 1
        if start + max_words >= len(words):
            break
        start += step

    return chunks


def chunk_by_tokens(
    text: str,
    tokenizer: Any,
    max_seq_length: int = 512,
    stride: int = 128,
) -> List[Chunk]:
    """
    Exact sliding-window chunking using a HuggingFace tokenizer.

    Encodes the full text once with `return_overflowing_tokens=True`, so
    each resulting chunk — once special tokens are added by the model —
    fits exactly within `max_seq_length`.

    Args:
        text: Cleaned article text.
        tokenizer: A HuggingFace `PreTrainedTokenizerBase` instance
            (see `model/tokenizer_manager.py`).
        max_seq_length: Max tokens per chunk, including special tokens.
        stride: Token overlap between consecutive chunks, so a sentence
            spanning a chunk boundary still appears in full in at least
            one chunk.
    """
    if not text or not text.strip():
        return []

    encoding = tokenizer(
        text,
        max_length=max_seq_length,
        truncation=True,
        stride=stride,
        return_overflowing_tokens=True,
        add_special_tokens=True,
    )

    chunks: List[Chunk] = []
    for index, input_ids in enumerate(encoding["input_ids"]):
        chunk_text = tokenizer.decode(input_ids, skip_special_tokens=True)
        if chunk_text.strip():
            chunks.append(Chunk(text=chunk_text, index=index, token_count=len(input_ids)))

    return chunks


__all__ = ["Chunk", "chunk_by_words", "chunk_by_tokens"]
