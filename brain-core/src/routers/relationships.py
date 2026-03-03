"""Asset relationship endpoints (doc 12, doc 13)."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, AssetRelationship
from src.schemas.enriched import RelationshipCreate, RelationshipResponse

router = APIRouter(prefix="/assets", tags=["relationships"])


@router.get("/{asset_id}/relationships", response_model=list[RelationshipResponse])
async def get_relationships(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all relationships for an asset (incoming and outgoing)."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(AssetRelationship).where(
            or_(
                AssetRelationship.source_asset_id == asset_id,
                AssetRelationship.target_asset_id == asset_id,
            )
        )
    )
    return [RelationshipResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/{asset_id}/relationships", response_model=RelationshipResponse, status_code=201)
async def create_relationship(
    asset_id: UUID, body: RelationshipCreate, db: AsyncSession = Depends(get_db)
):
    """Create a directed relationship from this asset to another."""
    source = await db.get(Asset, asset_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source asset not found")

    target = await db.get(Asset, body.target_asset_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target asset not found")

    if asset_id == body.target_asset_id:
        raise HTTPException(status_code=422, detail="Cannot create self-relationship")

    rel = AssetRelationship(
        source_asset_id=asset_id,
        target_asset_id=body.target_asset_id,
        relationship_type=body.relationship_type,
        confidence_score=body.confidence_score,
        created_by=body.created_by,
    )
    db.add(rel)
    try:
        await db.commit()
        await db.refresh(rel)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Relationship already exists")

    return RelationshipResponse.model_validate(rel)
