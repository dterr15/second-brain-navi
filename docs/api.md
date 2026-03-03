# Second Brain API Documentation

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

## Endpoints

### Health
- `GET /health` - Service health check

### Kanban
- `GET /kanban` - Assets grouped by status for Kanban board

### Assets
- `POST /assets` - Create new asset (starts as 'ingested')
- `GET /assets` - List assets with filters (status, type, verified, q, sort)
- `GET /assets/{id}` - Get full asset detail
- `PATCH /assets/{id}` - Update editable fields
- `POST /assets/{id}/transition` - Change asset state (enforces state machine)
- `POST /assets/{id}/retry` - Retry failed asset (failed -> waiting)

### Processing Queue (Claude Workflow)
- `POST /queue/{id}/prepare_prompt` - Generate prompt for Claude
- `POST /queue/{id}/import_enriched` - Import Claude's JSON response

### Knowledge Areas
- `GET /knowledge-areas` - List all areas
- `POST /knowledge-areas` - Create new area

### Relationships
- `GET /assets/{id}/relationships` - Get asset relationships
- `POST /assets/{id}/relationships` - Create relationship

### Skills
- `GET /skills` - List available skills
- `POST /assets/{id}/skills/{skill_id}/execute` - Execute skill
- `GET /assets/{id}/skills/executions` - List skill executions

### Search
- `POST /search` - Search assets (text search, future: semantic)

## State Machine Rules

Valid transitions:
- ingested -> waiting
- waiting -> processing
- processing -> waiting (on error)
- processing -> completed (requires valid enriched_data)
- any -> failed
- failed -> waiting (retry)

FORBIDDEN: waiting -> completed (without valid enrichment)
