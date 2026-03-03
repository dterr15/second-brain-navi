-- ============================================================
-- V001__init.sql - Second Brain Initial Schema
-- ============================================================
-- Source of truth: Knowledge Pack docs 03, 07, 12, 13
-- Constraints applied: C-01 (Completion), C-02 (HITL), C-03 (Schema First)
-- Stack: PostgreSQL + pgvector(384) + pgcrypto
-- DECISION: Using CHECK constraints instead of ENUMs for forward migration flexibility.
--   Adding new values to ENUMs requires ALTER TYPE + table rewrite in Postgres.
--   CHECK constraints allow adding values via simple ALTER TABLE.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- HELPER FUNCTION: updated_at auto-update
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TABLES
-- ============================================================

-- Knowledge Areas (doc 03)
CREATE TABLE knowledge_areas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_knowledge_areas_updated_at
    BEFORE UPDATE ON knowledge_areas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- Assets - core entity (doc 03)
CREATE TABLE assets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    type             TEXT NOT NULL DEFAULT 'text'
                       CHECK (type IN ('text', 'url', 'pdf', 'audio', 'image')),
    title            TEXT,
    source_url       TEXT,

    -- Raw content
    raw_payload      TEXT,
    raw_storage_path TEXT,

    -- Pipeline control
    status           TEXT NOT NULL DEFAULT 'ingested'
                       CHECK (status IN ('ingested', 'waiting', 'processing', 'completed', 'failed')),
    model_used       TEXT,

    -- Enriched output
    summary          TEXT,
    refined_markdown TEXT,
    enriched_data    JSONB,
    tags             TEXT[] DEFAULT '{}',
    priority         INTEGER CHECK (priority >= 1 AND priority <= 5),
    confidence_score REAL    CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Human verification (C-02)
    verified_by_human BOOLEAN NOT NULL DEFAULT false,
    verified_at       TIMESTAMPTZ,

    -- Flexible metadata
    metadata         JSONB NOT NULL DEFAULT '{}',
    last_error       TEXT,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- C-01: Completion Rule — enforced at DB level as safety net
    -- Application layer (state_machine.py) is primary enforcement
    CONSTRAINT chk_completed_has_data CHECK (
        status <> 'completed'
        OR (
            enriched_data    IS NOT NULL
            AND refined_markdown IS NOT NULL
            AND refined_markdown <> ''
            AND priority         IS NOT NULL
        )
    )
);

CREATE INDEX idx_assets_status     ON assets (status);
CREATE INDEX idx_assets_type       ON assets (type);
CREATE INDEX idx_assets_priority   ON assets (priority);
CREATE INDEX idx_assets_verified   ON assets (verified_by_human);
CREATE INDEX idx_assets_created_at ON assets (created_at DESC);
CREATE INDEX idx_assets_tags       ON assets USING GIN (tags);

CREATE TRIGGER trg_assets_updated_at
    BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- Auto-set verified_at when verified_by_human changes (C-02)
CREATE OR REPLACE FUNCTION set_verified_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.verified_by_human = true AND (OLD.verified_by_human = false OR OLD.verified_by_human IS NULL) THEN
        NEW.verified_at = now();
    ELSIF NEW.verified_by_human = false THEN
        NEW.verified_at = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assets_verified_at
    BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION set_verified_at();


-- Asset <-> Knowledge Area (N:N)
CREATE TABLE asset_knowledge_areas (
    asset_id          UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    knowledge_area_id UUID NOT NULL REFERENCES knowledge_areas(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, knowledge_area_id)
);

CREATE INDEX idx_aka_area ON asset_knowledge_areas (knowledge_area_id);


-- Asset Relationships — directed graph (doc 13)
CREATE TABLE asset_relationships (
    source_asset_id   UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    target_asset_id   UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL
                        CHECK (relationship_type IN ('complements', 'contradicts', 'derives_from', 'source_of')),
    confidence_score  REAL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    created_by        TEXT NOT NULL DEFAULT 'HUMAN',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_asset_id, target_asset_id, relationship_type),
    CONSTRAINT chk_no_self_relationship CHECK (source_asset_id <> target_asset_id)
);

CREATE INDEX idx_ar_target ON asset_relationships (target_asset_id);
CREATE INDEX idx_ar_type   ON asset_relationships (relationship_type);


-- Content Chunks — for large PDFs (doc 13, AQ-03)
CREATE TABLE content_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id    UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    content     TEXT NOT NULL,
    token_count INTEGER,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, chunk_index)
);

CREATE INDEX idx_chunks_asset ON content_chunks (asset_id, chunk_index);


-- Embeddings — pgvector, dimension 384 (all-MiniLM-L6-v2)
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    chunk_id        UUID REFERENCES content_chunks(id) ON DELETE CASCADE,
    embedding       vector(384) NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    scope           TEXT NOT NULL DEFAULT 'asset'
                      CHECK (scope IN ('asset', 'chunk')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_chunk_scope CHECK (
        (scope = 'chunk' AND chunk_id IS NOT NULL)
        OR (scope = 'asset' AND chunk_id IS NULL)
    )
);

CREATE INDEX idx_embeddings_asset ON embeddings (asset_id);
CREATE INDEX idx_embeddings_chunk ON embeddings (chunk_id);
-- HNSW index for approximate nearest neighbor (cosine similarity)
CREATE INDEX idx_embeddings_hnsw  ON embeddings USING hnsw (embedding vector_cosine_ops);


-- Skills catalog (doc 08)
CREATE TABLE skills (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    manifest_path TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    last_used     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_skills_updated_at
    BEFORE UPDATE ON skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- Skill execution logs (doc 08)
CREATE TABLE skill_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id       UUID NOT NULL REFERENCES skills(id) ON DELETE RESTRICT,
    asset_id       UUID REFERENCES assets(id) ON DELETE SET NULL,
    executor       TEXT NOT NULL DEFAULT 'HUMAN',
    result         JSONB,
    estimated_cost NUMERIC(10,5) NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_skill_logs_asset ON skill_logs (asset_id);
CREATE INDEX idx_skill_logs_skill ON skill_logs (skill_id, created_at DESC);


-- ============================================================
-- SEED DATA
-- ============================================================

INSERT INTO knowledge_areas (name, description) VALUES
    ('IA',           'Inteligencia Artificial y Machine Learning'),
    ('Finanzas',     'Finanzas personales e inversiones'),
    ('Programacion', 'Desarrollo de software y tecnologia'),
    ('Proyectos',    'Gestion de proyectos y productividad');

INSERT INTO skills (name, description, manifest_path, is_active) VALUES
    ('resumen_ejecutivo', 'Genera un resumen ejecutivo estructurado del asset',
     '/skills/resumen_ejecutivo/skill.md', true);