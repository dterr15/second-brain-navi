"""JSON Schema validation service (doc 09, C-04).

Three validation layers:
  Layer 1 - UI: parseable JSON, required fields, ranges (handled by frontend)
  Layer 2 - Schema: JSON Schema validation (this service)
  Layer 3 - DB: database constraints (handled by PostgreSQL)
"""
import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from src.settings import settings


_schema_cache: dict | None = None


def _load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        schema_path = Path(settings.enriched_schema_path)
        if not schema_path.exists():
            # Fallback: look relative to project root
            schema_path = Path("/app/schemas/enriched_contract.schema.json")
        with open(schema_path) as f:
            _schema_cache = json.load(f)
    return _schema_cache


def validate_enriched_json(data: dict) -> list[str]:
    """Validate enriched JSON against the official schema.

    Returns list of error messages. Empty list means valid.
    Implements Layer 2 validation (C-04).
    """
    schema = _load_schema()
    validator = Draft7Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = " -> ".join(str(p) for p in error.path) if error.path else "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def parse_and_validate(raw_json: str) -> tuple[dict | None, list[str]]:
    """Parse a JSON string and validate against schema.

    Returns (parsed_data, errors).
    If errors is non-empty, parsed_data may be None.
    """
    try:
        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except (json.JSONDecodeError, TypeError) as e:
        return None, [f"JSON parse error: {str(e)}"]

    if not isinstance(data, dict):
        return None, ["Expected a JSON object at root level"]

    errors = validate_enriched_json(data)
    if errors:
        return None, errors
    return data, []
