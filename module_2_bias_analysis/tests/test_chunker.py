"""
Unit tests for preprocessing/chunker.py.

`chunk_by_words` is dependency-free and fully testable here.
`chunk_by_tokens` is tested with a lightweight mock tokenizer so the full
HuggingFace stack is not required.
"""

from __future__ import annotations

import pytest

from module_2_bias_analysis.preprocessing.chunker import Chunk, chunk_by_words


# ─── Chunk dataclass ─────────────────────────────────────────────────────────

class TestChunk:
    def test_weight_uses_token_count_when_available(self):
        chunk = Chunk(text="hello world", index=0, token_count=50, word_count=2)
        assert chunk.weight == 50.0

    def test_weight_falls_back_to_word_count(self):
        chunk = Chunk(text="hello world", index=0, word_count=20)
        assert chunk.weight == 20.0

    def test_weight_falls_back_to_word_split(self):
        chunk = Chunk(text="hello world foo bar", index=0)
        assert chunk.weight == 4.0


# ─── chunk_by_words ──────────────────────────────────────────────────────────

class TestChunkByWords:
    def test_short_text_returns_single_chunk(self):
        text = "This is a short sentence."
        chunks = chunk_by_words(text, max_words=100)
        assert len(chunks) == 1
        assert chunks[0].index == 0

    def test_long_text_splits_into_multiple_chunks(self):
        text = " ".join([f"word{i}" for i in range(500)])
        chunks = chunk_by_words(text, max_words=100, overlap_words=20)
        assert len(chunks) > 1

    def test_each_chunk_within_max_words(self):
        text = " ".join([f"word{i}" for i in range(500)])
        chunks = chunk_by_words(text, max_words=100, overlap_words=20)
        for chunk in chunks:
            assert chunk.word_count <= 100

    def test_overlap_means_first_words_of_next_chunk_repeat(self):
        words = [f"word{i}" for i in range(200)]
        text = " ".join(words)
        chunks = chunk_by_words(text, max_words=100, overlap_words=30)
        assert len(chunks) >= 2
        last_words_of_chunk0 = chunks[0].text.split()[-30:]
        first_words_of_chunk1 = chunks[1].text.split()[:30]
        assert last_words_of_chunk0 == first_words_of_chunk1

    def test_all_content_covered(self):
        words = [f"word{i}" for i in range(250)]
        text = " ".join(words)
        chunks = chunk_by_words(text, max_words=100, overlap_words=20)
        # Every original word must appear in at least one chunk.
        combined = " ".join(c.text for c in chunks)
        for word in words:
            assert word in combined

    def test_chunk_indices_are_sequential(self):
        text = " ".join([f"word{i}" for i in range(300)])
        chunks = chunk_by_words(text, max_words=100, overlap_words=20)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_empty_string_returns_empty_list(self):
        assert chunk_by_words("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_by_words("   \n\t  ") == []

    def test_invalid_overlap_raises_value_error(self):
        with pytest.raises(ValueError, match="overlap_words"):
            chunk_by_words("some text here", max_words=10, overlap_words=10)

    def test_exact_max_words_is_single_chunk(self):
        text = " ".join(["word"] * 100)
        chunks = chunk_by_words(text, max_words=100)
        assert len(chunks) == 1

    def test_chunk_weight_equals_word_count(self):
        text = " ".join([f"w{i}" for i in range(200)])
        chunks = chunk_by_words(text, max_words=100, overlap_words=20)
        for chunk in chunks:
            assert chunk.weight == chunk.word_count


# ─── chunk_by_tokens (mock tokenizer) ───────────────────────────────────────

class MockTokenizer:
    """Minimal tokenizer stub that simulates the HuggingFace tokenizer API."""

    def __call__(self, text, max_length, truncation, stride, return_overflowing_tokens, add_special_tokens):
        words = text.split()
        step = max_length - stride
        chunks_input_ids = []
        start = 0
        while start < len(words):
            window = words[start : start + max_length]
            chunks_input_ids.append(list(range(len(window))))  # fake token ids
            if start + max_length >= len(words):
                break
            start += step

        class _Encoding(dict):
            def __init__(self, ids):
                super().__init__()
                self["input_ids"] = ids
                self.input_ids = ids

        return _Encoding(chunks_input_ids)

    def decode(self, token_ids, skip_special_tokens=True):
        # Simulate returning a fixed-width word per token id.
        return " ".join([f"tok{t}" for t in token_ids])


class TestChunkByTokens:
    def test_short_text_single_chunk(self):
        from module_2_bias_analysis.preprocessing.chunker import chunk_by_tokens
        text = "short article text here with a few words"
        tokenizer = MockTokenizer()
        chunks = chunk_by_tokens(text, tokenizer, max_seq_length=512, stride=128)
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        from module_2_bias_analysis.preprocessing.chunker import chunk_by_tokens
        text = " ".join([f"word{i}" for i in range(1000)])
        tokenizer = MockTokenizer()
        chunks = chunk_by_tokens(text, tokenizer, max_seq_length=50, stride=10)
        assert len(chunks) > 1

    def test_empty_string_returns_empty(self):
        from module_2_bias_analysis.preprocessing.chunker import chunk_by_tokens
        tokenizer = MockTokenizer()
        assert chunk_by_tokens("", tokenizer) == []

    def test_chunk_indices_sequential(self):
        from module_2_bias_analysis.preprocessing.chunker import chunk_by_tokens
        text = " ".join([f"w{i}" for i in range(500)])
        tokenizer = MockTokenizer()
        chunks = chunk_by_tokens(text, tokenizer, max_seq_length=50, stride=10)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
