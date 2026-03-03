"""Skills endpoints (doc 08, doc 12 section 4)."""
import uuid
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.assets import Asset, Skill, SkillLog
from src.schemas.enriched import SkillResponse, SkillExecuteRequest, SkillExecuteResponse

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).order_by(Skill.name))
    return [SkillResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/assets/{asset_id}/skills/{skill_id}/execute", response_model=SkillExecuteResponse)
async def execute_skill(
    asset_id: UUID, skill_id: UUID,
    body: SkillExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a skill on an asset. Logs execution (doc 08 section 8).
    Does NOT auto-apply changes (Human Override rule).
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.is_active:
        raise HTTPException(status_code=409, detail="Skill is not active")

    # Create execution log
    log = SkillLog(
        skill_id=skill_id,
        asset_id=asset_id,
        executor=f"{body.mode}_user",
        result={"note": "Skill execution placeholder - implement skill runner"},
        status="pending",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return SkillExecuteResponse(
        execution_id=log.id,
        status="pending",
        outcome=None,
        suggested_patch=None,
    )


@router.get("/assets/{asset_id}/skills/executions")
async def list_skill_executions(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """List skill execution logs for an asset."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(SkillLog).where(SkillLog.asset_id == asset_id).order_by(SkillLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "skill_id": str(log.skill_id),
            "executor": log.executor,
            "status": log.status,
            "result": log.result,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
