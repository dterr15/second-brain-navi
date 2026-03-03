"""Processing queue endpoints for Claude manual workflow (doc 05, doc 12 section 3)."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, AssetStatus
from src.schemas.enriched import (
    ImportEnrichedRequest, PromptResponse, TransitionResponse, EnrichedContract,
)
from src.services.prompt_service import generate_prompt
from src.services.validation_service import validate_enriched_json
from src.pipeline.state_machine import (
    validate_transition, validate_completion_requirements,
    TransitionError, CompletionError,
)

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/{asset_id}/prepare_prompt", response_model=PromptResponse)
async def prepare_prompt(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Generate structured prompt for Claude (Test 3).

    The asset should be in 'waiting' status.
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.status.value if hasattr(asset.status, 'value') else asset.status
    if current not in ("waiting", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Prompt generation requires asset in 'waiting' or 'processing', current is '{current}'"
        )

    raw = asset.raw_payload or ""
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Asset has no raw_payload to generate prompt from")

    prompt_text = generate_prompt(raw)
    return PromptResponse(prompt_text=prompt_text)


@router.post("/{asset_id}/import_enriched", response_model=TransitionResponse)
async def import_enriched(
    asset_id: UUID, body: ImportEnrichedRequest, db: AsyncSession = Depends(get_db)
):
    """Import enriched JSON from Claude and complete the asset (Test 4, 5, 6).

    Flow (AQ-04): waiting -> processing -> completed
    The processing state is real and persisted.

    C-04: JSON must validate against schema.
    C-01: Asset must have enriched_data + refined_markdown + priority to complete.
    C-02: verified_by_human defaults to false unless mark_verified=true.
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.status.value if hasattr(asset.status, 'value') else asset.status

    # Must be in waiting or processing to import
    if current not in ("waiting", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Import requires asset in 'waiting' or 'processing', current is '{current}'"
        )

    # Step 1: Validate JSON against schema (C-04)
    errors = validate_enriched_json(body.enriched_json)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "JSON validation failed (C-04: JSON Contract Rule)",
                "errors": errors,
            }
        )

    # Parse into typed contract for field extraction
    contract = EnrichedContract(**body.enriched_json)

    # Step 2: Transition to processing (AQ-04: real intermediate state)
    if current == "waiting":
        asset.status = AssetStatus.processing
        await db.flush()

    # Step 3: Apply enriched data to asset
    asset.enriched_data = body.enriched_json
    asset.title = contract.title
    asset.summary = contract.summary
    asset.refined_markdown = contract.refined_markdown
    asset.tags = contract.tags
    asset.priority = contract.priority
    asset.confidence_score = contract.confidence
    asset.model_used = body.model_used

    # C-02: Human verification
    if body.mark_verified:
        asset.verified_by_human = True
    # else: stays false (default from C-02)

    # Step 4: Validate completion requirements (C-01)
    try:
        validate_completion_requirements(asset)
    except CompletionError as e:
        # Rollback to waiting
        asset.status = AssetStatus.waiting
        await db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    # Step 5: Transition to completed
    asset.status = AssetStatus.completed
    await db.commit()
    await db.refresh(asset)

    return TransitionResponse(id=asset.id, status="completed")
