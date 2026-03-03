# Second Brain

Transform unstructured information into structured, connected knowledge.

## Quick Start

```bash
cp .env.example .env
make up
```

API available at: http://localhost:8000
API docs at: http://localhost:8000/docs

## Architecture

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL + pgvector + pgcrypto
- **Frontend**: Lovable (React + Tailwind) - see instructions.md
- **LLM**: Claude (manual copy/paste workflow)

## Key Concepts

- **Assets**: Knowledge units that flow through a processing pipeline
- **Pipeline**: ingested -> waiting -> processing -> completed (or failed)
- **Enrichment**: Claude generates structured JSON that the system validates
- **Knowledge Graph**: Assets connect via typed relationships

## Project Structure

```
/brain-core/     Backend API (FastAPI)
/db/             Database migrations
/schemas/        JSON Schema contracts
/skills/         Extensible skill modules
/docs/           Documentation
/instructions.md Lovable UI specification
```
