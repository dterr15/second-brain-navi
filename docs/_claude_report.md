# _claude_report.md

## Knowledge Pack Scan

All 16 documents of the Knowledge Pack were read and synthesized.

## ASSUMPTIONS

- AQ-01: Table name is `asset_relationships` (doc 13 recommendation)
- AQ-02: Embedding dimension 384, model all-MiniLM-L6-v2 (task prompt binding)
- AQ-03: `content_chunks` table created in V001; chunk-level not active in MVP
- AQ-04: `import_enriched` does waiting->processing->completed as two real transitions
- AQ-05: Knowledge Explorer deferred to post-MVP
- `confidence` in JSON contract maps to `confidence_score` in DB
- `actions`, `entities`, `sources` stored inside `enriched_data` JSONB; no separate tables in V1

## DECISIONS

- `enriched_data` stores entire validated JSON; individual fields also denormalized into columns
- `knowledge_areas` stored as text array on asset AND via junction table `asset_knowledge_areas`
- Tags stored as `text[]` on asset table directly; no separate tags table in V1
- `metadata` uses JSONB for flexible schema-less data

## Risks

- Lovable interpretation drift: mitigated by explicit field bindings and acceptance tests
- JSON schema drift: mitigated by single SoT `enriched_contract.schema.json`
- pgvector availability: mitigated by Docker `pgvector/pgvector:pg16`
- Large raw_payload: mitigated by prompt service truncation with configurable max
