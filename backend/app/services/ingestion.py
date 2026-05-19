from __future__ import annotations
import uuid
import asyncpg
from app.services.embeddings import embed_batch

EMBED_BATCH = 10


def _get_splitter():
    try:
        from semantic_text_splitter import TextSplitter
        # Splits on sentence/paragraph boundaries, respects 500-token max
        return TextSplitter.from_tiktoken_model("gpt-3.5-turbo", capacity=(100, 500))
    except Exception:
        return None


_splitter = None


def chunk_text(text: str) -> list[str]:
    global _splitter
    if _splitter is None:
        _splitter = _get_splitter()

    if _splitter is not None:
        return [c for c in _splitter.chunks(text) if c.strip()]

    # Fallback: paragraph-aware fixed-token split
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current, current_tokens = [], [], 0
    for para in paragraphs:
        tokens = enc.encode(para)
        if current_tokens + len(tokens) > 500 and current:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
        current.append(para)
        current_tokens += len(tokens)
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text[:2000]]


async def extract_text(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        import PyPDF2, io
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)
    return file_bytes.decode("utf-8", errors="replace")


async def ingest_document(
    pool: asyncpg.Pool,
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    source: str,
    text: str,
    lat: float,
    lng: float,
) -> int:
    chunks = chunk_text(text)
    total = len(chunks)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE ingestion_jobs SET status='processing', total_chunks=$1 WHERE id=$2",
            total, job_id,
        )

    processed = 0
    for batch_start in range(0, total, EMBED_BATCH):
        batch = chunks[batch_start: batch_start + EMBED_BATCH]
        embeddings = await embed_batch(batch)

        async with pool.acquire() as conn:
            async with conn.transaction():
                for idx, (chunk_text_val, emb) in enumerate(zip(batch, embeddings)):
                    await conn.execute(
                        """
                        INSERT INTO document_chunks
                            (id, document_id, content, embedding, geom, metadata)
                        VALUES ($1, $2, $3, $4,
                                ST_SetSRID(ST_MakePoint($5, $6), 4326),
                                $7::jsonb)
                        """,
                        uuid.uuid4(),
                        document_id,
                        chunk_text_val,
                        emb.tolist(),
                        lng, lat,
                        {"chunk_index": batch_start + idx, "source": source},
                    )

        processed += len(batch)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET processed_chunks=$1 WHERE id=$2",
                processed, job_id,
            )

    return total
