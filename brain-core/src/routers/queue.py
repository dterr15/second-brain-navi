"""Processing queue endpoints for Claude manual workflow (doc 05, doc 12 section 3)."""
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, AssetStatus
from src.schemas.enriched import (
    ImportEnrichedRequest, PromptResponse, TransitionResponse, EnrichedContract,
    AutoProcessResponse,
)
from src.services.prompt_service import generate_prompt
from src.services.validation_service import validate_enriched_json, parse_and_validate
from src.services.llm_service import call_llm, LLMConfigError, LLMCallError
from src.pipeline.state_machine import (
    validate_transition, validate_completion_requirements,
    TransitionError, CompletionError,
)
from src.settings import settings

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


@router.post("/{asset_id}/auto_process", response_model=AutoProcessResponse)
async def auto_process(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Automatically process an asset using the configured LLM provider.

    Flow:
      1. Generate prompt from raw_payload (same as prepare_prompt).
      2. Call LLM (provider: SB_LLM_PROVIDER, model: SB_LLM_MODEL).
      3. Strip markdown code fences if present.
      4. Parse and validate JSON against enriched_contract schema.
      5a. If valid: apply enriched fields, transition to completed.
      5b. If invalid: return 422 with validation errors, asset stays in waiting.

    The asset must be in 'waiting' status to start auto-processing.
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.status.value if hasattr(asset.status, "value") else asset.status
    if current != "waiting":
        raise HTTPException(
            status_code=409,
            detail=f"Auto-process requires asset in 'waiting', current is '{current}'"
        )

    raw = asset.raw_payload or ""
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Asset has no raw_payload to process")

    # Step 1: Generate prompt
    prompt_text = generate_prompt(raw)

    # Step 2: Call LLM
    try:
        llm_response = await call_llm(prompt_text)
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=f"LLM configuration error: {e}")
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    # Step 3: Strip markdown code fences (```json ... ``` or ``` ... ```)
    stripped = llm_response.strip()
    fence_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped)
    if fence_match:
        stripped = fence_match.group(1).strip()

    # Step 4: Parse and validate
    data, errors = parse_and_validate(stripped)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "LLM response failed JSON schema validation (C-04)",
                "errors": errors,
            }
        )

    # Step 5a: Apply enriched fields
    contract = EnrichedContract(**data)

    # Transition to processing (intermediate state)
    asset.status = AssetStatus.processing
    await db.flush()

    asset.enriched_data = data
    asset.title = contract.title
    asset.summary = contract.summary
    asset.refined_markdown = contract.refined_markdown
    asset.tags = contract.tags
    asset.priority = contract.priority
    asset.confidence_score = contract.confidence
    asset.model_used = settings.llm_model
    # verified_by_human stays false (C-02: Human Override)

    # Validate completion requirements (C-01)
    try:
        validate_completion_requirements(asset)
    except CompletionError as e:
        asset.status = AssetStatus.waiting
        await db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    # Transition to completed
    asset.status = AssetStatus.completed
    await db.commit()
    await db.refresh(asset)

    return AutoProcessResponse(id=asset.id, status="completed")
