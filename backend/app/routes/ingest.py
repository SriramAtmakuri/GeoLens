from __future__ import annotations
import uuid
import json
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.db import get_pool
from app.config import settings
from app.models.schemas import IngestResponse, JobStatus, SampleDataResponse
from app.services.embeddings import embed_batch

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_file(
    file: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    title: str = Form(default=""),
):
    file_bytes = await file.read()
    filename = file.filename or "upload"
    doc_title = title or filename

    pool = await get_pool()
    job_id = uuid.uuid4()
    document_id = uuid.uuid4()

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO documents (id, title, source) VALUES ($1, $2, $3)",
                document_id, doc_title, filename,
            )
            await conn.execute(
                "INSERT INTO ingestion_jobs (id, filename) VALUES ($1, $2)",
                job_id, filename,
            )

    # Enqueue ARQ job
    from arq import create_pool as arq_create_pool
    from arq.connections import RedisSettings
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await arq_create_pool(redis_settings)
    await arq_pool.enqueue_job(
        "process_ingestion",
        str(job_id), str(document_id), file_bytes, filename, lat, lng,
    )
    await arq_pool.aclose()

    return IngestResponse(job_id=job_id, status="pending")


@router.get("/ingest/jobs", response_model=list[JobStatus])
async def list_jobs():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ingestion_jobs ORDER BY started_at DESC LIMIT 50"
        )
    return [_job_row(r) for r in rows]


@router.get("/ingest/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: UUID):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ingestion_jobs WHERE id=$1", job_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_row(row)


def _job_row(row) -> dict:
    total = row["total_chunks"] or 0
    processed = row["processed_chunks"] or 0
    progress = (processed / total) if total > 0 else 0.0
    return {
        "job_id": row["id"],
        "status": row["status"],
        "filename": row["filename"],
        "total_chunks": row["total_chunks"],
        "processed_chunks": processed,
        "progress": progress,
        "error_message": row["error_message"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


@router.post("/sample-data", response_model=SampleDataResponse)
async def load_sample_data():
    """Load pre-built NYC sample data. Generates embeddings on the fly."""
    import aiofiles
    try:
        async with aiofiles.open(settings.sample_data_path, "r") as f:
            data = json.loads(await f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Sample data file not found")

    pool = await get_pool()
    docs_loaded = 0
    chunks_loaded = 0

    async with pool.acquire() as conn:
        # Insert documents (upsert by id)
        for doc in data["documents"]:
            existing = await conn.fetchval(
                "SELECT id FROM documents WHERE id=$1", UUID(doc["id"])
            )
            if not existing:
                await conn.execute(
                    "INSERT INTO documents (id, title, source) VALUES ($1, $2, $3)",
                    UUID(doc["id"]), doc["title"], doc["source"],
                )
                docs_loaded += 1

    # Generate embeddings in batches
    chunks = data["chunks"]
    batch_size = 10
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]
        embeddings = await embed_batch([c["content"] for c in batch])

        async with pool.acquire() as conn:
            async with conn.transaction():
                for chunk, emb in zip(batch, embeddings):
                    existing = await conn.fetchval(
                        "SELECT id FROM document_chunks WHERE id=$1", UUID(chunk["id"])
                    )
                    if not existing:
                        await conn.execute(
                            """
                            INSERT INTO document_chunks
                                (id, document_id, content, embedding, geom, metadata)
                            VALUES ($1, $2, $3, $4,
                                    ST_SetSRID(ST_MakePoint($5, $6), 4326),
                                    $7::jsonb)
                            """,
                            UUID(chunk["id"]),
                            UUID(chunk["document_id"]),
                            chunk["content"],
                            emb.tolist(),
                            chunk["lng"], chunk["lat"],
                            json.dumps(chunk.get("metadata", {})),
                        )
                        chunks_loaded += 1

    # Load eval queries if present
    import os
    if os.path.exists(settings.eval_data_path):
        async with aiofiles.open(settings.eval_data_path, "r") as f:
            eval_data = json.loads(await f.read())
        async with pool.acquire() as conn:
            for eq in eval_data:
                existing = await conn.fetchval(
                    "SELECT id FROM eval_queries WHERE question=$1", eq["question"]
                )
                if not existing:
                    await conn.execute(
                        """
                        INSERT INTO eval_queries
                            (question, polygon_geojson, expected_chunk_ids)
                        VALUES ($1, $2::jsonb, $3)
                        """,
                        eq["question"],
                        json.dumps(eq["polygon_geojson"]),
                        [UUID(x) for x in eq["expected_chunk_ids"]],
                    )

    return SampleDataResponse(
        documents_loaded=docs_loaded,
        chunks_loaded=chunks_loaded,
        message=f"Loaded {docs_loaded} documents and {chunks_loaded} chunks.",
    )
