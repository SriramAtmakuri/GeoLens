from __future__ import annotations
from typing import Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# ── Documents ──────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: UUID
    title: str
    source: str
    created_at: datetime
    chunk_count: int = 0


# ── Ingestion ──────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    job_id: UUID
    status: str = "pending"


class JobStatus(BaseModel):
    job_id: UUID
    status: str
    filename: str
    total_chunks: int | None
    processed_chunks: int
    progress: float
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


# ── Query ──────────────────────────────────────────────────────────────────

class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]]


class QueryRequest(BaseModel):
    question: str
    polygon: GeoJSONPolygon
    top_k: int = Field(default=8, ge=1, le=50)
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    vector_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.6, ge=0.0, le=1.0)


class ChunkResult(BaseModel):
    id: UUID
    content: str
    similarity_score: float
    vector_score: float
    bm25_score: float
    hybrid_score: float
    rerank_score: float | None
    retrieval_rank: int
    final_rank: int
    location: dict[str, Any]
    metadata: dict[str, Any]
    source: str | None = None


class QueryStats(BaseModel):
    chunks_in_polygon: int
    chunks_returned: int
    latency_ms: int


class TraceInfo(BaseModel):
    embedding_ms: int
    hybrid_query_ms: int
    reranking_ms: int
    llm_synthesis_ms: int
    total_ms: int


class QueryResponse(BaseModel):
    answer: str
    chunks: list[ChunkResult]
    query_stats: QueryStats
    trace: TraceInfo
    hyde_used: bool = False
    query_variations: list[str] = []


# ── Evaluation ─────────────────────────────────────────────────────────────

class EvalQueryCreate(BaseModel):
    question: str
    polygon_geojson: dict[str, Any]
    expected_chunk_ids: list[UUID]


class EvalQueryOut(BaseModel):
    id: UUID
    question: str
    polygon_geojson: dict[str, Any]
    expected_chunk_ids: list[UUID]
    created_at: datetime


class EvalQueryResult(BaseModel):
    question: str
    hit: bool
    rank_of_first_hit: int | None
    retrieved_ids: list[UUID]


class EvalRunResponse(BaseModel):
    hit_rate: float
    mrr: float
    results: list[EvalQueryResult]


# ── Sample data ────────────────────────────────────────────────────────────

class SampleDataResponse(BaseModel):
    documents_loaded: int
    chunks_loaded: int
    message: str
