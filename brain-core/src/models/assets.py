"""SQLAlchemy models - Schema First (ADR-003, C-03).
These models MUST mirror the SQL in V001__init.sql exactly.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, Enum as SAEnum,
    ForeignKey, CheckConstraint, UniqueConstraint, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


# ---- Enums matching SQL ----
import enum

class AssetType(str, enum.Enum):
    text = "text"
    url = "url"
    pdf = "pdf"
    audio = "audio"
    image = "image"

class AssetStatus(str, enum.Enum):
    ingested = "ingested"
    waiting = "waiting"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class RelationshipType(str, enum.Enum):
    complements = "complements"
    contradicts = "contradicts"
    derives_from = "derives_from"
    source_of = "source_of"

class EmbeddingScope(str, enum.Enum):
    asset = "asset"
    chunk = "chunk"


# ---- Models ----

class KnowledgeArea(Base):
    __tablename__ = "knowledge_areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False, default="text")
    title = Column(Text)
    raw_payload = Column(Text)
    raw_storage_path = Column(Text)
    source_url = Column(Text)
    summary = Column(Text)
    refined_markdown = Column(Text)
    enriched_data = Column(JSONB)
    tags = Column(ARRAY(Text), default=list)
    priority = Column(Integer)
    confidence_score = Column(Float)
    verified_by_human = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime(timezone=True))
    status = Column(String, nullable=False, default="ingested")
    metadata_ = Column("metadata", JSONB, default=dict)
    model_used = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    knowledge_areas = relationship("KnowledgeArea", secondary="asset_knowledge_areas", lazy="selectin")
    outgoing_relationships = relationship("AssetRelationship", foreign_keys="AssetRelationship.source_asset_id", lazy="selectin")


class AssetKnowledgeArea(Base):
    __tablename__ = "asset_knowledge_areas"

    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    knowledge_area_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_areas.id", ondelete="CASCADE"), primary_key=True)


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    source_asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    target_asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    relationship_type = Column(SAEnum(RelationshipType, name="relationship_type", create_type=False), primary_key=True)
    confidence_score = Column(Float)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("content_chunks.id", ondelete="CASCADE"))
    embedding = Column(Vector(384), nullable=False)
    embedding_model = Column(Text, nullable=False, default="all-MiniLM-L6-v2")
    embedding_scope = Column(SAEnum(EmbeddingScope, name="embedding_scope", create_type=False), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    manifest_path = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkillLog(Base):
    __tablename__ = "skill_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    executor = Column(Text, nullable=False)
    result = Column(JSONB)
    estimated_cost = Column(Float)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
