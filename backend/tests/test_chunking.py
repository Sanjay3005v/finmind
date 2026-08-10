"""Tests for token-aware chunking (app/rag/chunking.py)."""
import tiktoken

from app.rag.chunking import chunk_text

_encoding = tiktoken.get_encoding("cl100k_base")


def _long_synthetic_text(num_sentences: int = 400) -> str:
    return " ".join(f"sentence number {i} about markets and portfolios." for i in range(num_sentences))


def test_chunk_text_splits_long_text_into_multiple_chunks_near_target_size():
    text = _long_synthetic_text()
    total_tokens = len(_encoding.encode(text))
    assert total_tokens > 1600  # comfortably more than 2 chunks' worth

    chunks = chunk_text(text, target_tokens=800, overlap_tokens=100)

    assert len(chunks) >= 2
    # Every non-final chunk should be (close to) exactly target_tokens —
    # allow a couple of tokens of slack for decode/re-encode boundary drift.
    for chunk in chunks[:-1]:
        token_count = len(_encoding.encode(chunk))
        assert 790 <= token_count <= 800

    # The final chunk should never exceed the target.
    assert len(_encoding.encode(chunks[-1])) <= 800


def test_chunk_text_consecutive_chunks_overlap_by_roughly_overlap_tokens():
    text = _long_synthetic_text()
    chunks = chunk_text(text, target_tokens=800, overlap_tokens=100)

    for i in range(len(chunks) - 1):
        tail_tokens = _encoding.encode(chunks[i])[-100:]
        head_tokens = _encoding.encode(chunks[i + 1])[:100]
        # The overlap window is defined by the same token stream, so it
        # should match on the vast majority of positions (allow minor drift
        # from decode/re-encode at the exact boundary).
        matches = sum(1 for a, b in zip(tail_tokens, head_tokens) if a == b)
        assert matches >= 90


def test_chunk_text_short_text_returns_single_unmodified_chunk():
    text = "Short research note about a single stock's quarterly performance."
    assert chunk_text(text) == [text]


def test_chunk_text_empty_or_whitespace_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_chunk_text_rejects_invalid_overlap():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("some text", target_tokens=100, overlap_tokens=100)
    with pytest.raises(ValueError):
        chunk_text("some text", target_tokens=100, overlap_tokens=150)
