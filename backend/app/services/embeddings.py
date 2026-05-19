from __future__ import annotations
import numpy as np
from app.config import settings

_openai_client = None
_st_model = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


async def embed_text(text: str) -> np.ndarray:
    return (await embed_batch([text]))[0]


async def embed_batch(texts: list[str]) -> list[np.ndarray]:
    if settings.openai_api_key:
        client = _get_openai()
        resp = await client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        return [np.array(item.embedding, dtype=np.float32) for item in resp.data]
    # Fallback: sentence-transformers (384-dim, stored as 1536 zero-padded)
    model = _get_st_model()
    raw = model.encode(texts, normalize_embeddings=True)
    result = []
    for vec in raw:
        padded = np.zeros(1536, dtype=np.float32)
        padded[: len(vec)] = vec
        result.append(padded)
    return result
