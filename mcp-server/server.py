"""Second Brain MCP Server.

Exposes Second Brain's knowledge-management operations as MCP tools that any
MCP-compatible client (Claude Desktop, OpenClaw, Cursor, etc.) can call.

Transport : Streamable HTTP on port 8001
Endpoint  : http://localhost:8001/mcp
Backend   : Second Brain FastAPI on http://brain-core:8000 (Docker) or
            http://localhost:8000 (local dev, controlled by SB_API_BASE)
"""
import os
import httpx
from fastmcp import FastMCP
from pydantic_settings import BaseSettings


# ── Settings ────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    api_base: str = "http://brain-core:8000"   # FastAPI backend URL
    host: str = "0.0.0.0"
    port: int = 8001

    model_config = {"env_prefix": "SB_MCP_", "env_file": ".env"}


settings = Settings()


# ── HTTP client helper ───────────────────────────────────────────────────────

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.api_base, timeout=60.0)


def _fmt_error(e: httpx.HTTPStatusError) -> str:
    """Turn an HTTP error into a readable string for the LLM agent."""
    try:
        body = e.response.json()
        detail = body.get("detail", body)
        if isinstance(detail, dict) and "errors" in detail:
            return f"Error {e.response.status_code}: " + "; ".join(detail["errors"])
        return f"Error {e.response.status_code}: {detail}"
    except Exception:
        return f"Error {e.response.status_code}: {e.response.text[:300]}"


# ── MCP Server ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="second-brain",
    instructions=(
        "Second Brain is a knowledge-management system. "
        "Use create_asset to ingest new content, auto_process to enrich it with AI, "
        "search_assets to find related knowledge, and get_kanban to see the pipeline status."
    ),
)


# ── Tool 1: create_asset ─────────────────────────────────────────────────────

@mcp.tool()
async def create_asset(
    content: str,
    type: str = "text",
    title: str | None = None,
    source_url: str | None = None,
) -> dict:
    """Create a new knowledge asset and ingest it into Second Brain.

    The asset starts in 'ingested' status. Call transition_asset with
    to_status='waiting' to queue it for processing, then auto_process to enrich it.

    Args:
        content:    The raw text content to ingest (ignored if type='url').
        type:       Asset type — one of: text, url, pdf, audio, image. Default: text.
        title:      Optional human-readable title. The AI will generate one if omitted.
        source_url: Source URL (required when type='url').

    Returns:
        { asset_id, status, title, type }
    """
    payload: dict = {"type": type}
    if content:
        payload["raw_payload"] = content
    if title:
        payload["title"] = title
    if source_url:
        payload["source_url"] = source_url

    async with _client() as c:
        try:
            r = await c.post("/assets", json=payload)
            r.raise_for_status()
            d = r.json()
            return {
                "asset_id": d["id"],
                "status": d["status"],
                "title": d.get("title"),
                "type": d["type"],
            }
        except httpx.HTTPStatusError as e:
            return {"error": _fmt_error(e)}


# ── Tool 2: search_assets ────────────────────────────────────────────────────

@mcp.tool()
async def search_assets(query: str, limit: int = 10) -> list[dict]:
    """Search Second Brain for assets matching a query string.

    Uses full-text ILIKE search across title, summary, and refined_markdown.

    Args:
        query: Search terms (e.g. "docker containers", "machine learning").
        limit: Maximum number of results to return (1–100, default 10).

    Returns:
        List of { id, title, status, summary, tags, priority, confidence_score }.
        Returns an empty list if nothing matches.
    """
    async with _client() as c:
        try:
            r = await c.post("/search", json={"query": query, "limit": min(limit, 100)})
            r.raise_for_status()
            items = r.json()
            return [
                {
                    "id": a["id"],
                    "title": a.get("title"),
                    "status": a["status"],
                    "summary": a.get("summary"),
                    "tags": a.get("tags", []),
                    "priority": a.get("priority"),
                    "confidence_score": a.get("confidence_score"),
                }
                for a in items
            ]
        except httpx.HTTPStatusError as e:
            return [{"error": _fmt_error(e)}]


# ── Tool 3: get_kanban ───────────────────────────────────────────────────────

@mcp.tool()
async def get_kanban() -> dict:
    """Get the current Kanban board showing asset counts per pipeline stage.

    The Second Brain pipeline has 5 stages:
      ingested   → newly added, not yet queued
      waiting    → queued for AI processing
      processing → currently being enriched
      completed  → fully enriched and in the Data Room
      failed     → processing failed, can be retried

    Returns:
        { ingested, waiting, processing, completed, failed } — each is a dict with
        { count, assets: [{ id, title, status, priority, tags }] }.
    """
    async with _client() as c:
        try:
            r = await c.get("/kanban")
            r.raise_for_status()
            board = r.json()
            result = {}
            for col in ["ingested", "waiting", "processing", "completed", "failed"]:
                items = board.get(col, [])
                result[col] = {
                    "count": len(items),
                    "assets": [
                        {
                            "id": a["id"],
                            "title": a.get("title"),
                            "status": a["status"],
                            "priority": a.get("priority"),
                            "tags": a.get("tags", []),
                        }
                        for a in items
                    ],
                }
            return result
        except httpx.HTTPStatusError as e:
            return {"error": _fmt_error(e)}


# ── Tool 4: auto_process ─────────────────────────────────────────────────────

@mcp.tool()
async def auto_process(asset_id: str) -> dict:
    """Automatically enrich an asset using the configured LLM (default: gpt-4o-mini).

    The asset must be in 'waiting' status. If it's still 'ingested', call
    transition_asset(asset_id, 'waiting') first.

    The LLM will:
    - Generate a structured title, summary, and refined markdown
    - Extract tags, knowledge areas, entities, and actions
    - Assign a priority (1–5) and confidence score (0–1)

    On success the asset moves to 'completed' in the Data Room.
    On LLM validation failure the asset stays in 'waiting' and errors are returned.

    Args:
        asset_id: UUID of the asset to process.

    Returns:
        On success: { status, title, summary, tags, priority, confidence_score }
        On failure: { error, validation_errors }
    """
    # First transition to waiting if needed
    async with _client() as c:
        try:
            # Check current status
            asset_r = await c.get(f"/assets/{asset_id}")
            asset_r.raise_for_status()
            asset = asset_r.json()
            current = asset["status"]

            if current == "ingested":
                t = await c.post(f"/assets/{asset_id}/transition", json={"to_status": "waiting"})
                t.raise_for_status()

            # Run auto-process
            r = await c.post(f"/queue/{asset_id}/auto_process")
            r.raise_for_status()

            # Fetch enriched result
            detail_r = await c.get(f"/assets/{asset_id}")
            detail_r.raise_for_status()
            d = detail_r.json()

            return {
                "status": d["status"],
                "title": d.get("title"),
                "summary": d.get("summary"),
                "tags": d.get("tags", []),
                "priority": d.get("priority"),
                "confidence_score": d.get("confidence_score"),
                "model_used": d.get("model_used"),
            }
        except httpx.HTTPStatusError as e:
            try:
                body = e.response.json()
                detail = body.get("detail", {})
                if isinstance(detail, dict) and "errors" in detail:
                    return {
                        "error": detail.get("message", "Validation failed"),
                        "validation_errors": detail["errors"],
                    }
                return {"error": _fmt_error(e)}
            except Exception:
                return {"error": _fmt_error(e)}


# ── Tool 5: get_asset ────────────────────────────────────────────────────────

@mcp.tool()
async def get_asset(asset_id: str) -> dict:
    """Get the full detail of a specific asset, including its refined markdown content.

    Use this after auto_process to read the enriched knowledge, or to inspect
    any asset's current state, tags, entities, and actions.

    Args:
        asset_id: UUID of the asset to retrieve.

    Returns:
        Full asset detail: { id, title, status, type, priority, confidence_score,
        verified_by_human, tags, summary, refined_markdown, enriched_data,
        raw_payload, created_at, updated_at }.
        Returns { error } if not found.
    """
    async with _client() as c:
        try:
            r = await c.get(f"/assets/{asset_id}")
            r.raise_for_status()
            d = r.json()
            return {
                "id": d["id"],
                "title": d.get("title"),
                "status": d["status"],
                "type": d["type"],
                "priority": d.get("priority"),
                "confidence_score": d.get("confidence_score"),
                "verified_by_human": d.get("verified_by_human", False),
                "tags": d.get("tags", []),
                "summary": d.get("summary"),
                "refined_markdown": d.get("refined_markdown"),
                "enriched_data": d.get("enriched_data"),
                "raw_payload": d.get("raw_payload"),
                "model_used": d.get("model_used"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
        except httpx.HTTPStatusError as e:
            return {"error": _fmt_error(e)}


# ── Tool 6: list_assets ──────────────────────────────────────────────────────

@mcp.tool()
async def list_assets(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """List assets with optional status filter. Useful for browsing the Data Room.

    Args:
        status: Filter by pipeline stage — one of: ingested, waiting, processing,
                completed, failed. Omit to return all statuses.
        limit:  Max results per page (1–200, default 20).
        offset: Pagination offset (default 0).

    Returns:
        { total, limit, offset, items: [{ id, title, status, priority, tags,
          confidence_score, created_at }] }
    """
    params: dict = {"limit": min(limit, 200), "offset": offset}
    if status:
        params["status"] = status

    async with _client() as c:
        try:
            r = await c.get("/assets", params=params)
            r.raise_for_status()
            d = r.json()
            return {
                "total": d.get("total", 0),
                "limit": d.get("limit", limit),
                "offset": d.get("offset", offset),
                "items": [
                    {
                        "id": a["id"],
                        "title": a.get("title"),
                        "status": a["status"],
                        "priority": a.get("priority"),
                        "tags": a.get("tags", []),
                        "confidence_score": a.get("confidence_score"),
                        "created_at": a.get("created_at"),
                    }
                    for a in d.get("items", [])
                ],
            }
        except httpx.HTTPStatusError as e:
            return {"error": _fmt_error(e)}


# ── Tool 7: transition_asset ─────────────────────────────────────────────────

@mcp.tool()
async def transition_asset(asset_id: str, to_status: str) -> dict:
    """Move an asset to a new pipeline stage.

    Valid transitions (C-05 state machine):
      ingested  → waiting
      waiting   → processing | failed
      processing → completed* | failed
      failed    → waiting  (use this to retry)

    * Direct transition to 'completed' requires enriched_data, refined_markdown,
      and priority to be set. Use auto_process instead for a one-step flow.

    Args:
        asset_id:  UUID of the asset to transition.
        to_status: Target status — one of: ingested, waiting, processing,
                   completed, failed.

    Returns:
        { id, status } on success, { error } on invalid transition.
    """
    async with _client() as c:
        try:
            r = await c.post(
                f"/assets/{asset_id}/transition",
                json={"to_status": to_status},
            )
            r.raise_for_status()
            d = r.json()
            return {"id": d["id"], "status": d["status"]}
        except httpx.HTTPStatusError as e:
            return {"error": _fmt_error(e)}


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Starting Second Brain MCP Server on {settings.host}:{settings.port}")
    print(f"Backend API: {settings.api_base}")
    print(f"MCP endpoint: http://{settings.host}:{settings.port}/mcp")
    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        path="/mcp",
    )
