"""Knowledge Areas endpoints (doc 12 section implied)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import KnowledgeArea
from src.schemas.enriched import KnowledgeAreaCreate, KnowledgeAreaResponse

router = APIRouter(prefix="/knowledge-areas", tags=["knowledge-areas"])


@router.get("", response_model=list[KnowledgeAreaResponse])
async def list_knowledge_areas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeArea).order_by(KnowledgeArea.name))
    return [KnowledgeAreaResponse.model_validate(ka) for ka in result.scalars().all()]


@router.post("", response_model=KnowledgeAreaResponse, status_code=201)
async def create_knowledge_area(body: KnowledgeAreaCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(KnowledgeArea).where(KnowledgeArea.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Knowledge area '{body.name}' already exists")
    ka = KnowledgeArea(name=body.name, description=body.description)
    db.add(ka)
    await db.commit()
    await db.refresh(ka)
    return KnowledgeAreaResponse.model_validate(ka)
