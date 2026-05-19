from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models.schemas import QueryRequest, QueryResponse
from app.services.query import run_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    result = await run_query(
        pool=pool,
        question=req.question,
        polygon_geojson=req.polygon.model_dump(),
        top_k=req.top_k,
        similarity_threshold=req.similarity_threshold,
        vector_weight=req.vector_weight,
        bm25_weight=req.bm25_weight,
    )
    return result
