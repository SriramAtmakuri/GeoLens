from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models.schemas import DocumentOut

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT d.id, d.title, d.source, d.created_at,
                   COUNT(dc.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """
        )
    return [dict(r) for r in rows]


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: UUID):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM documents WHERE id=$1", doc_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Document not found")
