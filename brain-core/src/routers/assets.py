"""Asset CRUD and state transition endpoints (doc 12 section 1)."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, AssetStatus
from src.schemas.enriched import (
    AssetCreate, AssetSummary, AssetDetail, AssetPatch,
    TransitionRequest, TransitionResponse, PaginatedAssets,
)
from src.pipeline.state_machine import (
    validate_transition, validate_completion_requirements,
    TransitionError, CompletionError,
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetDetail, status_code=201)
async def create_asset(body: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Create a new asset in state 'ingested' (Test 1)."""
    asset = Asset(
        type=body.type,
        title=body.title,
        raw_payload=body.raw_payload,
        source_url=body.source_url,
        raw_storage_path=body.raw_storage_path,
        metadata_=body.metadata or {},
        status=AssetStatus.ingested,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return AssetDetail.model_validate(asset)


@router.get("", response_model=PaginatedAssets)
async def list_assets(
    status: str | None = None,
    type: str | None = None,
    verified: bool | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = "created_at_desc",
    db: AsyncSession = Depends(get_db),
):
    """List assets with filters (doc 12)."""
    query = select(Asset)

    if status:
        query = query.where(Asset.status == status)
    if type:
        query = query.where(Asset.type == type)
    if verified is not None:
        query = query.where(Asset.verified_by_human == verified)
    if q:
        query = query.where(
            Asset.title.ilike(f"%{q}%") | Asset.summary.ilike(f"%{q}%")
        )

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    if sort == "priority_desc":
        query = query.order_by(Asset.priority.desc().nullslast())
    elif sort == "created_at_asc":
        query = query.order_by(Asset.created_at.asc())
    else:
        query = query.order_by(Asset.created_at.desc())

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = [AssetSummary.model_validate(a) for a in result.scalars().all()]
    return PaginatedAssets(items=items, limit=limit, offset=offset, total=total)


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get full asset detail."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetDetail.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetDetail)
async def patch_asset(asset_id: UUID, body: AssetPatch, db: AsyncSession = Depends(get_db)):
    """Update editable fields on an asset."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata":
            setattr(asset, "metadata_", value)
        else:
            setattr(asset, field, value)

    await db.commit()
    await db.refresh(asset)
    return AssetDetail.model_validate(asset)


@router.post("/{asset_id}/transition", response_model=TransitionResponse)
async def transition_asset(
    asset_id: UUID, body: TransitionRequest, db: AsyncSession = Depends(get_db)
):
    """Transition asset to a new state (C-05 state machine)."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.status.value if hasattr(asset.status, 'value') else asset.status

    try:
        validate_transition(current, body.to_status)
    except TransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # C-01: If transitioning to completed, check requirements
    if body.to_status == "completed":
        try:
            validate_completion_requirements(asset)
        except CompletionError as e:
            raise HTTPException(status_code=422, detail=str(e))

    asset.status = body.to_status
    await db.commit()
    await db.refresh(asset)
    return TransitionResponse(id=asset.id, status=asset.status.value if hasattr(asset.status, 'value') else asset.status)


@router.post("/{asset_id}/retry", response_model=TransitionResponse)
async def retry_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retry a failed asset: failed -> waiting (Test 9)."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.status.value if hasattr(asset.status, 'value') else asset.status
    if current != "failed":
        raise HTTPException(status_code=409, detail=f"Retry only allowed from 'failed', current is '{current}'")

    asset.status = AssetStatus.waiting
    await db.commit()
    await db.refresh(asset)
    return TransitionResponse(id=asset.id, status="waiting")