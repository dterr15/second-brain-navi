# Skill: Resumen Ejecutivo

## Descripcion
Genera un resumen ejecutivo estructurado a partir del contenido de un asset.

## Inputs
- asset.raw_payload (texto completo)
- asset.type (para adaptar el formato)

## Output
JSON que cumple el contrato enriched_contract.schema.json.

## Reglas
- El resumen no debe exceder 2000 caracteres.
- Prioridad basada en impacto y urgencia del contenido.
- Siempre generar al menos 3 tags relevantes.
- Identificar al menos las entidades principales (personas, organizaciones, conceptos).
- El refined_markdown debe ser autocontenido y reutilizable.
