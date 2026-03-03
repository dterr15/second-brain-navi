"""Semantic search endpoint (doc 12). Placeholder for pgvector search."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset
from src.schemas.enriched import SearchRequest, AssetSummary

router = APIRouter(tags=["search"])


@router.post("/search", response_model=list[AssetSummary])
async def semantic_search(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Search assets. Falls back to text search until embeddings are populated.

    Future: use pgvector cosine similarity on embeddings table.
    Current: ILIKE search on title + summary + tags.
    """
    q = f"%{body.query}%"
    result = await db.execute(
        select(Asset)
        .where(
            Asset.title.ilike(q)
            | Asset.summary.ilike(q)
            | Asset.refined_markdown.ilike(q)
        )
        .order_by(Asset.created_at.desc())
        .limit(body.limit)
    )
    return [AssetSummary.model_validate(a) for a in result.scalars().all()]
