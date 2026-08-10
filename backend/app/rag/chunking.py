"""Token-aware text chunking.

Uses `tiktoken`'s `cl100k_base` encoding — the same tokenizer OpenAI's
`text-embedding-3-small` model uses — so the token counts here are the real
counts the embeddings API will see, not a character-count approximation.
"""
from __future__ import annotations

import tiktoken

# text-embedding-3-small (and the gpt-4.1 family) all use cl100k_base.
_ENCODING_NAME = "cl100k_base"
_encoding = tiktoken.get_encoding(_ENCODING_NAME)

DEFAULT_TARGET_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100


def chunk_text(
    text: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Splits `text` into chunks of ~`target_tokens` tokens each, with
    ~`overlap_tokens` tokens of overlap between consecutive chunks (a
    sliding window over the real token stream, not characters/words).

    Returns an empty list for empty/whitespace-only input, and a single
    chunk (the whole text) if it already fits within `target_tokens`.
    """
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be >= 0 and less than target_tokens")

    if not text or not text.strip():
        return []

    tokens = _encoding.encode(text)
    if len(tokens) <= target_tokens:
        return [text]

    step = target_tokens - overlap_tokens
    total = len(tokens)
    chunks: list[str] = []

    start = 0
    while start < total:
        end = min(start + target_tokens, total)
        window = tokens[start:end]
        decoded = _encoding.decode(window)
        if decoded.strip():
            chunks.append(decoded)
        if end == total:
            break
        start += step

    return chunks
