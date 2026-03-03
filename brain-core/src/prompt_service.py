"""Prompt generation service for Claude manual workflow (doc 05, ADR-004)."""
from src.settings import settings

MASTER_PROMPT_TEMPLATE = """Eres un analista de conocimiento para mi Second Brain.

Tarea:
1) Lee el CONTENIDO.
2) Extrae y normaliza la informacion.
3) Genera un refined_markdown limpio y reutilizable (sin relleno).
4) Devuelve SOLO el siguiente JSON valido, sin texto antes ni despues.

El JSON debe tener EXACTAMENTE estas keys en ingles:

{{
  "title": "titulo descriptivo (max 180 chars)",
  "summary": "resumen ejecutivo en espanol (max 2000 chars)",
  "refined_markdown": "contenido estructurado en markdown (max 40000 chars)",
  "tags": ["tag1", "tag2"],
  "knowledge_areas": ["area1", "area2"],
  "priority": 3,
  "actions": [{{"type": "todo|calendar|read|buy|idea", "text": "descripcion"}}],
  "entities": [{{"type": "person|org|tool|concept|place", "value": "nombre"}}],
  "sources": [{{"kind": "url|pdf|note|audio|image", "value": "referencia"}}],
  "confidence": 0.85
}}

Reglas:
- Usa EXACTAMENTE los nombres de campo en ingles como aparecen arriba.
- Si faltan datos usa null o listas vacias, nunca inventes.
- priority: 5=urgente/impacto alto, 3=util, 1=archivo/referencia.
- confidence: 0.0-1.0 segun claridad del contenido.
- Manten el texto de los valores en espanol.
- Sin texto fuera del JSON. Ni antes ni despues.

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
