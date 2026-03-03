# Project Second Brain — Architectural Manifest

Este documento es el **ancla arquitectónica del sistema**.

Cualquier modelo de IA o desarrollador debe leer este archivo antes de trabajar en el proyecto.

Su objetivo es permitir que cualquier agente entienda rápidamente:

1. qué es el sistema
2. qué problema resuelve
3. cuál es su arquitectura
4. cuáles son las decisiones técnicas ya tomadas
5. qué reglas no pueden romperse

---

# 1. Qué es Second Brain

Second Brain es un sistema que transforma información desordenada en conocimiento estructurado.

El sistema captura información desde múltiples fuentes (notas, PDFs, enlaces, audio) y la transforma en **activos de conocimiento estructurados** mediante un pipeline híbrido que combina:

- reglas determinísticas
- análisis vectorial local
- enriquecimiento mediante LLM
- validación humana

El resultado es una **base de conocimiento conectada** que evoluciona como un grafo semántico.

---

# 2. Qué hace el sistema (en términos operacionales)

Second Brain implementa un pipeline de conocimiento con tres zonas:

### Ingestion Layer
Captura información desde el mundo exterior.

Ejemplos:

- notas
- URLs
- PDFs
- audio

La información entra como **raw payload**.

---

### Processing Pipeline (Cinta)

El contenido pasa por un pipeline que:

1. clasifica
2. analiza
3. estructura
4. valida

---

### Data Room

La información validada se guarda como **knowledge assets estructurados**.

Cada asset contiene:

- resumen
- contenido refinado
- tags
- entidades
- áreas de conocimiento
- acciones derivadas

---

# 3. Entidades principales del sistema

Las entidades fundamentales del sistema son:

### Asset

Unidad básica de conocimiento.

Un asset puede representar:

- nota
- documento
- idea
- recurso

Propiedades principales:

- title
- summary
- refined_markdown
- tags
- priority
- confidence
- entities
- sources

---

### Knowledge Area

Dominios temáticos donde se clasifica el conocimiento.

Ejemplos:

- IA
- Finanzas
- Programación
- Proyectos

Un asset puede pertenecer a múltiples áreas.

---

### Asset Relationship

Define conexiones entre assets.

Tipos posibles:

- complements
- contradicts
- derives_from
- source_of

Estas relaciones forman un **grafo de conocimiento**.

---

# 4. Estados del pipeline

Los assets evolucionan a través de estados.

Estados válidos:

ingested  
waiting  
processing  
completed  
failed

Flujo normal:

ingested → waiting → processing → completed

La zona **waiting** es la “Sala de Espera”, donde el usuario decide cómo procesar el asset.

---

# 5. Constraints críticas (no negociables)

Estas reglas **no pueden romperse en la implementación**.

### Completion Rule

Un asset no puede pasar a `completed` si no tiene:

- enriched_data válido
- refined_markdown
- JSON que cumple el schema

---

### Human Verification Rule

Los datos generados por IA deben marcarse como:

verified_by_human = false

hasta que el usuario los valide.

---

### Schema First Rule

El esquema SQL es la fuente de verdad estructural.

El sistema no debe modificar tablas manualmente.

Todas las modificaciones deben ocurrir mediante migraciones.

---

# 6. Stack técnico

Estas decisiones son vinculantes para la implementación.

Backend  
Python + FastAPI

Base de datos  
PostgreSQL

Extensiones

- pgcrypto
- pgvector

Frontend  
Lovable (generando UI basada en React + Tailwind)

LLM  
Claude (modo manual como flujo principal)

Storage  
filesystem o object storage para archivos grandes.

Deployment  
Arquitectura basada en Docker.

---

# 7. Interacción con LLM

El sistema usa un modelo híbrido.

Modo principal:

manual interaction con Claude.

Flujo:

1. el sistema genera un prompt
2. el usuario lo copia
3. Claude devuelve JSON estructurado
4. el usuario pega ese JSON en la app

El JSON debe cumplir el contrato definido en el schema.

---

# 8. Arquitectura futura: Skills

El sistema soporta módulos llamados **Skills**.

Una skill es una capacidad especializada que puede ejecutarse sobre un asset.

Ejemplos:

- resumen de documentos
- clasificación temática
- extracción de entidades

Las skills viven como módulos independientes y pueden ser utilizadas por agentes o por el usuario.

---

# 9. Knowledge Pack del proyecto

Este manifest actúa como índice del knowledge pack.

Documentos:

01_vision.md  
02_system_architecture.md  
03_data_model_concepts.md  
04_pipeline_and_states.md  
05_llm_interaction_model.md  
06_ui_concepts_lovable.md  
07_system_rules_and_constraints.md  
08_system_skills_concept.md  
09_error_handling_and_validation.md  
10_acceptance_tests.md  
11_technical_stack.md  
12_api_contracts_overview.md  
13_knowledge_graph_model.md

---

# 10. Cómo debe usar este contexto una IA

Antes de implementar el sistema:

1. leer este manifest
2. consultar los documentos del knowledge pack
3. producir un SYSTEM_DIGEST.md que sintetice el sistema
4. solo entonces generar implementación técnica