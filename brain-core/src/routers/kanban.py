"""Kanban board endpoint (doc 06, doc 12 section 2)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, AssetStatus
from src.schemas.enriched import AssetSummary, KanbanResponse

router = APIRouter(tags=["kanban"])


@router.get("/kanban", response_model=KanbanResponse)
async def get_kanban(db: AsyncSession = Depends(get_db)):
    """Return assets grouped by status for the Kanban UI."""
    result = await db.execute(select(Asset).order_by(Asset.created_at.desc()))
    assets = result.scalars().all()

    grouped = {s.value: [] for s in AssetStatus}
    for asset in assets:
        summary = AssetSummary.model_validate(asset)
        grouped[asset.status.value if hasattr(asset.status, 'value') else asset.status].append(summary)

    return KanbanResponse(**grouped)
