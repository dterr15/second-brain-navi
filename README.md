# Second Brain

Transform unstructured information into structured, connected knowledge.

## Quick Start

```bash
cp .env.example .env
# Edit .env — set SB_LLM_API_KEY to your OpenAI/Anthropic/Google key
docker compose up -d
```

| Service | URL |
|---|---|
| REST API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| MCP Server | http://localhost:8001/mcp |
| Frontend (dev) | http://localhost:8080 |

---

## MCP Server — Connect any AI Agent

Second Brain exposes a **Model Context Protocol (MCP) server** on port 8001.
Any MCP-compatible client (Claude Desktop, OpenClaw, Cursor, Windsurf, etc.)
can use it to read, write, and process knowledge assets.

### Available Tools

| Tool | Description |
|---|---|
| `create_asset` | Ingest new content (text, URL, PDF…) |
| `search_assets` | Full-text search across title, summary, content |
| `get_kanban` | Pipeline board with counts per stage |
| `auto_process` | AI-enrich an asset with one call (LLM → Data Room) |
| `get_asset` | Full asset detail including refined markdown |
| `list_assets` | Paginated list with optional status filter |
| `transition_asset` | Move an asset between pipeline stages |

### Connect: Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "second-brain": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

Restart Claude Desktop — you will see the Second Brain tools in the tools panel.

### Connect: OpenClaw / Cursor / Windsurf / any MCP client

Use the **Streamable HTTP** transport:

```
URL:  http://localhost:8001/mcp
Type: streamable-http   (or "http" in some clients)
```

### Connect: `fastmcp` CLI (for testing)

```bash
pip install fastmcp
fastmcp inspect http://localhost:8001/mcp          # list tools
fastmcp call http://localhost:8001/mcp get_kanban  # call a tool
```

### Example agent workflow

```
1. create_asset(content="React hooks tutorial...", type="text")
   → { asset_id: "abc-123", status: "ingested" }

2. auto_process(asset_id="abc-123")
   → { status: "completed", title: "React Hooks Guide",
       tags: ["react", "hooks"], priority: 3, confidence_score: 0.91 }

3. search_assets(query="react hooks")
   → [{ id: "abc-123", title: "React Hooks Guide", ... }]
```

### Run MCP server standalone (without Docker)

```bash
cd mcp-server
pip install -e .
SB_MCP_API_BASE=http://localhost:8000 python server.py
```

---

## Architecture

- **Backend**: Python + FastAPI (port 8000)
- **MCP Server**: fastmcp 2.x, Streamable HTTP (port 8001)
- **Database**: PostgreSQL + pgvector
- **Frontend**: React + Vite + Shadcn/ui (port 8080)
- **LLM**: Configurable — OpenAI / Anthropic / Google (set `SB_LLM_*` env vars)

## Key Concepts

- **Assets**: Knowledge units that flow through a processing pipeline
- **Pipeline**: ingested → waiting → processing → completed (or failed)
- **Enrichment**: LLM generates structured JSON validated against `enriched_contract.schema.json`
- **Knowledge Graph**: Assets connect via typed relationships

## Project Structure

```
/brain-core/     Backend API (FastAPI)
/mcp-server/     MCP Server (fastmcp, port 8001)
/db/             Database migrations
/schemas/        JSON Schema contracts
/skills/         Extensible skill modules
/frontend/       React + Vite UI
/docs/           Documentation
```
