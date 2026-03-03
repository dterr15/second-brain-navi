"""Second Brain API - FastAPI application entry point.

Stack: Python + FastAPI (doc 11, ADR-006)
All constraints from 07_system_rules_and_constraints.md enforced.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.settings import settings
from src.routers import assets, queue, kanban, knowledge_areas, relationships, skills, search, health

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Second Brain - Transform unstructured information into structured knowledge",
)

# CORS for Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(kanban.router)
app.include_router(assets.router)
app.include_router(queue.router)
app.include_router(knowledge_areas.router)
app.include_router(relationships.router)
app.include_router(skills.router)
app.include_router(search.router)
