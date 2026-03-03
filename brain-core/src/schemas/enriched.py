"""Pydantic schemas for API request/response validation.
Mirrors enriched_contract.schema.json and doc 12 API contracts.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# ---- Enriched Contract sub-schemas ----

class ActionItem(BaseModel):
    type: str = Field(..., pattern="^(todo|calendar|read|buy|idea)$")
    text: str = Field(..., min_length=1, max_length=300)

class EntityItem(BaseModel):
    type: str = Field(..., pattern="^(person|org|tool|concept|place)$")
    value: str = Field(..., min_length=1, max_length=120)

class SourceItem(BaseModel):
    kind: str = Field(..., pattern="^(url|pdf|note|audio|image)$")
    value: str = Field(..., min_length=1, max_length=2000)


class EnrichedContract(BaseModel):
    """The JSON contract Claude must return. Validated against JSON Schema (C-04)."""
    title: str = Field(..., min_length=1, max_length=180)
    summary: str = Field(..., min_length=1, max_length=2000)
    refined_markdown: str = Field(..., min_length=1, max_length=40000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    knowledge_areas: list[str] = Field(default_factory=list, max_length=20)
    priority: int = Field(..., ge=1, le=5)
    actions: list[ActionItem] = Field(default_factory=list)
    entities: list[EntityItem] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---- Asset API schemas ----

class AssetCreate(BaseModel):
    type: str = Field(default="text", pattern="^(text|url|pdf|audio|image)$")
    title: Optional[str] = None
    raw_payload: Optional[str] = None
    source_url: Optional[str] = None
    raw_storage_path: Optional[str] = None
    metadata: Optional[dict] = None

class AssetSummary(BaseModel):
    id: UUID
    title: Optional[str]
    type: str
    status: str
    priority: Optional[int]
    confidence_score: Optional[float]
    verified_by_human: bool
    tags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

class AssetDetail(AssetSummary):
    raw_payload: Optional[str]
    source_url: Optional[str]
    raw_storage_path: Optional[str]
    summary: Optional[str]
    refined_markdown: Optional[str]
    enriched_data: Optional[dict]
    metadata: Optional[dict] = Field(None, alias="metadata_")
    model_used: Optional[str]
    verified_at: Optional[datetime]
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}

class AssetPatch(BaseModel):
    title: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    verified_by_human: Optional[bool] = None
    tags: Optional[list[str]] = None
    summary: Optional[str] = None
    refined_markdown: Optional[str] = None
    metadata: Optional[dict] = None

class TransitionRequest(BaseModel):
    to_status: str = Field(..., pattern="^(ingested|waiting|processing|completed|failed)$")
    reason: Optional[str] = None

class TransitionResponse(BaseModel):
    id: UUID
    status: str

class ImportEnrichedRequest(BaseModel):
    enriched_json: dict
    mark_verified: bool = False
    model_used: Optional[str] = "Claude Web"

class KanbanResponse(BaseModel):
    ingested: list[AssetSummary]
    waiting: list[AssetSummary]
    processing: list[AssetSummary]
    completed: list[AssetSummary]
    failed: list[AssetSummary]

class PromptResponse(BaseModel):
    prompt_text: str

class PaginatedAssets(BaseModel):
    items: list[AssetSummary]
    limit: int
    offset: int
    total: int

# ---- Knowledge Area schemas ----

class KnowledgeAreaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = None

class KnowledgeAreaResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

# ---- Relationship schemas ----

class RelationshipCreate(BaseModel):
    target_asset_id: UUID
    relationship_type: str = Field(..., pattern="^(complements|contradicts|derives_from|source_of)$")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    created_by: str = "HUMAN"

class RelationshipResponse(BaseModel):
    source_asset_id: UUID
    target_asset_id: UUID
    relationship_type: str
    confidence_score: Optional[float]
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}

# ---- Skill schemas ----

class SkillResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}

class SkillExecuteRequest(BaseModel):
    mode: str = Field(default="manual", pattern="^(manual|api|local)$")
    parameters: Optional[dict] = None

class SkillExecuteResponse(BaseModel):
    execution_id: UUID
    status: str
    outcome: Optional[dict] = None
    suggested_patch: Optional[dict] = None

# ---- Search schemas ----

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
