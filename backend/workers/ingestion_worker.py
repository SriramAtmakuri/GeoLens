from __future__ import annotations
import uuid
import asyncpg
from app.config import settings
from app.services.ingestion import extract_text, ingest_document


async def process_ingestion(
    ctx,
    job_id: str,
    document_id: str,
    file_bytes: bytes,
    filename: str,
    lat: float,
    lng: float,
) -> dict:
    pool: asyncpg.Pool = ctx["pool"]
    job_uuid = uuid.UUID(job_id)
    doc_uuid = uuid.UUID(document_id)

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET status='processing' WHERE id=$1",
                job_uuid,
            )

        text = await extract_text(file_bytes, filename)
        doc_source = filename

        total = await ingest_document(
            pool=pool,
            job_id=job_uuid,
            document_id=doc_uuid,
            source=doc_source,
            text=text,
            lat=lat,
            lng=lng,
        )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingestion_jobs
                SET status='completed', completed_at=NOW(), total_chunks=$1, processed_chunks=$1
                WHERE id=$2
                """,
                total, job_uuid,
            )
        return {"status": "completed", "total_chunks": total}

    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET status='failed', error_message=$1 WHERE id=$2",
                str(exc), job_uuid,
            )
        raise
