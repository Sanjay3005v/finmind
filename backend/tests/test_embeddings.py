"""Unit tests for app/rag/embeddings.py, mocking the real httpx call to
OpenAI via `respx` so no network traffic or API credits are used."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.errors import AppError
from app.rag.embeddings import OPENAI_EMBEDDINGS_URL, embed_texts


@pytest.mark.asyncio
@respx.mock
async def test_embed_texts_returns_vectors_in_input_order():
    respx.post(OPENAI_EMBEDDINGS_URL).mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.2, 0.2]},
                    {"index": 0, "embedding": [0.1, 0.1]},
                ]
            },
        )
    )

    vectors = await embed_texts(["first", "second"])
    assert vectors == [[0.1, 0.1], [0.2, 0.2]]


@pytest.mark.asyncio
@respx.mock
async def test_embed_texts_raises_app_error_on_non_200():
    respx.post(OPENAI_EMBEDDINGS_URL).mock(return_value=Response(500, text="internal error"))

    with pytest.raises(AppError) as exc_info:
        await embed_texts(["hello"])
    assert exc_info.value.code == "EMBEDDING_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_embed_texts_raises_app_error_on_malformed_response():
    respx.post(OPENAI_EMBEDDINGS_URL).mock(return_value=Response(200, json={"unexpected": "shape"}))

    with pytest.raises(AppError) as exc_info:
        await embed_texts(["hello"])
    assert exc_info.value.code == "EMBEDDING_FAILED"


@pytest.mark.asyncio
async def test_embed_texts_empty_input_returns_empty_list_without_any_call():
    assert await embed_texts([]) == []
