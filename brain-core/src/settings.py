"""Application settings via pydantic-settings."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://brain:brain@db:5432/secondbrain"
    database_url_sync: str = "postgresql://brain:brain@db:5432/secondbrain"

    # Application
    app_name: str = "Second Brain API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Prompt
    max_raw_payload_chars: int = 12000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Schema path
    enriched_schema_path: str = "/app/schemas/enriched_contract.schema.json"

    # LLM (auto-process)
    llm_provider: str = "anthropic"          # anthropic | google | openai
    llm_model: str = "claude-haiku-4-5"
    llm_api_key: str = ""

    # MCP Server
    mcp_port: int = 8001

    model_config = {"env_prefix": "SB_", "env_file": ".env"}


settings = Settings()
