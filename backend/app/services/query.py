from __future__ import annotations
import json
import time
import asyncpg
from opentelemetry import trace as otel_trace
from app.config import settings
from app.services.embeddings import embed_text
from app.services import reranker as reranker_svc

tracer = otel_trace.get_tracer("geolens.query")

_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None:
        from openai import AsyncOpenAI
        if settings.groq_api_key:
            _llm_client = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            _llm_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _llm_client


def _chat_model() -> str:
    return settings.groq_chat_model if settings.groq_api_key else settings.chat_model


def _has_llm() -> bool:
    return bool(settings.groq_api_key or settings.openai_api_key)


HYBRID_SQL = """
SELECT
    dc.id::text,
    dc.content,
    dc.metadata,
    ST_AsGeoJSON(dc.geom)        AS location,
    d.source,
    1 - (dc.embedding <=> $1::vector)                                AS vector_score,
    COALESCE(ts_rank(dc.tsv, plainto_tsquery('english', $2)), 0)     AS bm25_score,
    (
        $3::float * (1 - (dc.embedding <=> $1::vector)) +
        $4::float * COALESCE(ts_rank(dc.tsv, plainto_tsquery('english', $2)), 0)
    )                                                                 AS hybrid_score
FROM document_chunks dc
JOIN documents d ON d.id = dc.document_id
WHERE ST_Within(dc.geom, ST_GeomFromGeoJSON($5))
  AND (
        1 - (dc.embedding <=> $1::vector) > $6::float
        OR dc.tsv @@ plainto_tsquery('english', $2)
      )
ORDER BY hybrid_score DESC
LIMIT $7
"""

COUNT_SQL = """
SELECT COUNT(*) FROM document_chunks
WHERE ST_Within(geom, ST_GeomFromGeoJSON($1))
"""


async def _hyde(question: str):
    """
    Generate a hypothetical answer document and embed it.
    HyDE bridges the vocabulary gap: the embedding of a document-like answer
    sits closer to real document chunks than the short question itself.
    Returns (embedding, hypothetical_text | None).
    """
    if not _has_llm() or not settings.enable_hyde:
        return await embed_text(question), None

    client = _get_llm()
    resp = await client.chat.completions.create(
        model=_chat_model(),
        messages=[{
            "role": "user",
            "content": (
                "Write a short factual passage (2-3 sentences) that would directly "
                "answer this question about urban zoning or land-use regulations:\n"
                + question
            ),
        }],
        max_tokens=150,
        temperature=0.5,
    )
    hyp = (resp.choices[0].message.content or '').strip()
    return await embed_text(hyp), hyp


async def _expand(question: str) -> list[str]:
    """
    Generate 2 alternative phrasings so BM25 matches more vocabulary.
    Returns [original, var1, var2].
    """
    if not _has_llm() or not settings.enable_query_expansion:
        return [question]

    client = _get_llm()
    resp = await client.chat.completions.create(
        model=_chat_model(),
        messages=[{
            "role": "user",
            "content": (
                "Generate 2 alternative phrasings of this question for searching "
                "urban zoning documents. Output only the 2 questions, one per line, "
                "no numbering:\n" + question
            ),
        }],
        max_tokens=100,
        temperature=0.7,
    )
    lines = [
        l.strip()
        for l in (resp.choices[0].message.content or '').strip().split("\n")
        if l.strip()
    ][:2]
    return [question] + lines


async def _fetch_candidates(
    pool: asyncpg.Pool,
    emb,
    q_text: str,
    polygon_str: str,
    similarity_threshold: float,
    vector_weight: float,
    bm25_weight: float,
    retrieve_n: int,
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            HYBRID_SQL,
            emb.tolist(),
            q_text,
            vector_weight,
            bm25_weight,
            polygon_str,
            similarity_threshold,
            retrieve_n,
        )
    return rows


async def run_query(
    pool: asyncpg.Pool,
    question: str,
    polygon_geojson: dict,
    top_k: int = 8,
    similarity_threshold: float = 0.3,
    vector_weight: float = 0.4,
    bm25_weight: float = 0.6,
) -> dict:
    t_total = time.monotonic()

    with tracer.start_as_current_span("total_query") as total_span:
        total_span.set_attribute("question", question[:200])
        total_span.set_attribute("top_k", top_k)

        # ── Step 1: HyDE + embedding ──────────────────────────────────────
        t0 = time.monotonic()
        with tracer.start_as_current_span("embedding") as emb_span:
            query_emb, hyp_doc = await _hyde(question)
            hyde_used = hyp_doc is not None
            emb_span.set_attribute("hyde", hyde_used)
        embedding_ms = int((time.monotonic() - t0) * 1000)

        # ── Step 2: Query expansion ───────────────────────────────────────
        with tracer.start_as_current_span("query_expansion"):
            variations = await _expand(question)

        polygon_str = json.dumps(polygon_geojson)
        retrieve_n = max(top_k * 3, 20)

        # ── Step 3: Hybrid spatial + vector + BM25 (all variations) ──────
        t0 = time.monotonic()
        with tracer.start_as_current_span("hybrid_scoring") as hs_span:
            # Run one query per variation; keep the best score per chunk
            best: dict[str, dict] = {}
            for q_text in variations:
                rows = await _fetch_candidates(
                    pool, query_emb, q_text,
                    polygon_str, similarity_threshold,
                    vector_weight, bm25_weight, retrieve_n,
                )
                for row in rows:
                    cid = row["id"]
                    score = float(row["hybrid_score"])
                    if cid not in best or score > best[cid]["hybrid_score"]:
                        best[cid] = {
                            "id": cid,
                            "content": row["content"],
                            "metadata": (json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"])) if row["metadata"] else {},
                            "location": json.loads(row["location"]),
                            "source": row["source"],
                            "vector_score": float(row["vector_score"]),
                            "bm25_score": float(row["bm25_score"]),
                            "hybrid_score": score,
                            "similarity_score": float(row["vector_score"]),
                            "rerank_score": None,
                        }

            async with pool.acquire() as conn:
                count_row = await conn.fetchrow(COUNT_SQL, polygon_str)

            hs_span.set_attribute("candidates_found", len(best))
            hs_span.set_attribute("query_variations", len(variations))

        hybrid_query_ms = int((time.monotonic() - t0) * 1000)
        chunks_in_polygon = count_row[0]

        candidates = sorted(best.values(), key=lambda c: c["hybrid_score"], reverse=True)
        for i, c in enumerate(candidates):
            c["retrieval_rank"] = i + 1
            c["final_rank"] = i + 1

        # ── Step 4: Cross-encoder rerank ──────────────────────────────────
        t0 = time.monotonic()
        with tracer.start_as_current_span("reranking") as rr_span:
            if candidates and settings.enable_reranker and reranker_svc.is_available():
                reranked = reranker_svc.rerank(question, candidates[:retrieve_n])
                final_chunks = reranked[:top_k]
                rr_span.set_attribute("reranker", "cross-encoder/ms-marco-MiniLM-L-6-v2")
            else:
                for c in candidates:
                    c["rerank_score"] = None
                    c["final_rank"] = c["retrieval_rank"]
                final_chunks = candidates[:top_k]
                rr_span.set_attribute("reranker", "disabled")
        reranking_ms = int((time.monotonic() - t0) * 1000)

        # ── Step 5: LLM synthesis ─────────────────────────────────────────
        t0 = time.monotonic()
        with tracer.start_as_current_span("llm_synthesis") as llm_span:
            llm_span.set_attribute("model", settings.chat_model)
            llm_span.set_attribute("chunks_passed", len(final_chunks))
            answer = await _synthesize(question, final_chunks)
        llm_synthesis_ms = int((time.monotonic() - t0) * 1000)

        total_ms = int((time.monotonic() - t_total) * 1000)
        total_span.set_attribute("total_ms", total_ms)

    return {
        "answer": answer,
        "chunks": final_chunks,
        "query_stats": {
            "chunks_in_polygon": chunks_in_polygon,
            "chunks_returned": len(final_chunks),
            "latency_ms": total_ms,
        },
        "trace": {
            "embedding_ms": embedding_ms,
            "hybrid_query_ms": hybrid_query_ms,
            "reranking_ms": reranking_ms,
            "llm_synthesis_ms": llm_synthesis_ms,
            "total_ms": total_ms,
        },
        "hyde_used": hyde_used,
        "query_variations": variations,
    }


async def _synthesize(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant documents found within the selected area."

    if not _has_llm():
        snippets = "\n\n".join(
            f"[Source: {c.get('source', 'unknown')}]\n{c['content'][:300]}"
            for c in chunks
        )
        return f"(LLM disabled — set OPENAI_API_KEY or GROQ_API_KEY)\n\nRelevant excerpts:\n{snippets}"

    context = "\n\n---\n\n".join(
        f"Source: {c.get('source', 'unknown')}\n{c['content']}" for c in chunks
    )
    client = _get_llm()
    resp = await client.chat.completions.create(
        model=_chat_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a geospatial document analyst. Answer the user's question "
                    "using ONLY the provided document excerpts from the selected map area. "
                    "Be concise. When citing a source write its filename in brackets "
                    "inline, e.g. [nyc_zoning_brooklyn.txt]."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nDocument excerpts:\n{context}",
            },
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return resp.choices[0].message.content or ''
