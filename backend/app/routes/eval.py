from __future__ import annotations
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models.schemas import (
    EvalQueryCreate, EvalQueryOut, EvalQueryResult, EvalRunResponse,
)
from app.services.query import run_query

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/queries", response_model=EvalQueryOut, status_code=201)
async def create_eval_query(body: EvalQueryCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO eval_queries (question, polygon_geojson, expected_chunk_ids)
            VALUES ($1, $2::jsonb, $3)
            RETURNING *
            """,
            body.question,
            json.dumps(body.polygon_geojson),
            body.expected_chunk_ids,
        )
    return _eval_row(row)


@router.get("/queries", response_model=list[EvalQueryOut])
async def list_eval_queries():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM eval_queries ORDER BY created_at DESC"
        )
    return [_eval_row(r) for r in rows]


@router.post("/run", response_model=EvalRunResponse)
async def run_evaluation():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM eval_queries ORDER BY created_at")

    if not rows:
        raise HTTPException(status_code=404, detail="No eval queries found. Load sample data first.")

    results: list[EvalQueryResult] = []
    reciprocal_ranks = []

    for row in rows:
        polygon = row["polygon_geojson"]
        if isinstance(polygon, str):
            polygon = json.loads(polygon)
        expected = set(str(x) for x in row["expected_chunk_ids"])

        result = await run_query(
            pool=pool,
            question=row["question"],
            polygon_geojson=polygon,
            top_k=10,
            similarity_threshold=0.0,
        )
        retrieved_ids = [c["id"] for c in result["chunks"]]

        hit = False
        first_rank = None
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in expected:
                hit = True
                first_rank = rank
                break

        reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
        results.append(EvalQueryResult(
            question=row["question"],
            hit=hit,
            rank_of_first_hit=first_rank,
            retrieved_ids=[UUID(x) for x in retrieved_ids],
        ))

    hit_rate = sum(1 for r in results if r.hit) / len(results)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

    return EvalRunResponse(hit_rate=hit_rate, mrr=mrr, results=results)


def _eval_row(row) -> dict:
    pg = row["polygon_geojson"]
    if isinstance(pg, str):
        pg = json.loads(pg)
    return {
        "id": row["id"],
        "question": row["question"],
        "polygon_geojson": pg,
        "expected_chunk_ids": list(row["expected_chunk_ids"]),
        "created_at": row["created_at"],
    }
