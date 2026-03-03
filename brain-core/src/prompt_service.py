"""Prompt generation service for Claude manual workflow (doc 05, ADR-004)."""
from src.settings import settings

MASTER_PROMPT_TEMPLATE = """Eres un analista de conocimiento para mi Second Brain.

Tarea:
1) Lee el CONTENIDO.
2) Extrae y normaliza: titulo, resumen, tags, areas de conocimiento,
   prioridad (1-5), acciones, entidades.
3) Genera un refined_markdown limpio y reutilizable (sin relleno).
4) Devuelve SOLO JSON valido (sin explicacion, sin markdown fuera
   del campo refined_markdown).

Reglas:
- Si faltan datos, usa null o listas vacias (no inventes).
- Prioridad: 5=urgente/impacto alto, 3=util, 1=archivo/referencia.
- confidence 0.0-1.0 segun claridad del contenido.
- Manten el texto en espanol.
- No incluyas texto fuera del JSON. Ni antes ni despues.

CONTENIDO:
<<<
{raw_payload}
>>>"""


def generate_prompt(raw_payload: str) -> str:
    """Generate the structured prompt for Claude.

    Truncates raw_payload to max_raw_payload_chars if necessary.
    """
    max_chars = settings.max_raw_payload_chars
    truncated = raw_payload
    warning = ""
    if raw_payload and len(raw_payload) > max_chars:
        truncated = raw_payload[:max_chars]
        warning = f"\n\n[NOTA: contenido truncado a {max_chars} caracteres de {len(raw_payload)} originales]"

    return MASTER_PROMPT_TEMPLATE.format(raw_payload=truncated + warning)
