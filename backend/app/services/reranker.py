from __future__ import annotations

_model = None
_available = False


def _load():
    global _model, _available
    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        _available = True
    except Exception:
        _available = False


def rerank(question: str, chunks: list[dict]) -> list[dict]:
    """
    Rerank chunks using cross-encoder. If unavailable, return original order
    with rerank_score=None.
    """
    if not _available:
        for i, c in enumerate(chunks):
            c["rerank_score"] = None
            c["final_rank"] = i + 1
        return chunks

    pairs = [(question, c["content"]) for c in chunks]
    scores = _model.predict(pairs).tolist()

    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)

    reranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
    for i, c in enumerate(reranked):
        c["final_rank"] = i + 1
    return reranked


def is_available() -> bool:
    return _available


# Load at import time so first query isn't slow
_load()
