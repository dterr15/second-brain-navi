# Second Brain - UI Specification for Lovable

This document is the **source of truth** for the Lovable frontend.
It describes every screen, component, interaction, and data binding.

---

## 1. System Vision

Second Brain is a knowledge management system. Users capture information (notes, URLs, PDFs, audio) and process it through a pipeline that uses Claude AI to generate structured knowledge assets. The UI is a Kanban board showing assets flowing through pipeline states.

## 2. Technical Context

- **Backend API**: FastAPI at `http://localhost:8000` (configurable via env)
- **Authentication**: None in MVP (single user)
- **Data format**: All API responses are JSON
- **State management**: The Kanban board reflects real pipeline states from the API

---

## 3. Golden Rules (must be enforced in UI)

**R1 - Completion Rule**: An asset CANNOT move to "Data Room" (completed) without valid enriched data, refined_markdown, and priority (1-5). The "Import and Complete" button must be disabled until JSON validates.

**R2 - Human Verification Rule**: All AI-generated data shows `verified_by_human = false` by default. A toggle allows the user to verify. Verification timestamp is shown when true.

**R3 - JSON Contract Rule**: If the user pastes invalid JSON, show clear error messages listing every validation failure. Never accept invalid JSON. The asset stays in its current column.

**R4 - State Machine Rule**: Only valid transitions are allowed. The UI must not offer buttons for invalid transitions. Valid: ingested->waiting, waiting->processing, processing->completed (with valid JSON), any->failed, failed->waiting.

**R5 - Manual Claude Interaction**: The system generates a prompt. The user copies it to Claude manually. Claude returns JSON. The user pastes it back. The system NEVER sends data to an LLM automatically.

---

## 4. Screen: Pipeline Board (Kanban)

**API**: `GET /kanban`

### Layout
A horizontal Kanban board with 5 columns, left to right:

| Column | Label | API status | Color accent |
|--------|-------|------------|-------------|
| 1 | Ingreso | ingested | Gray |
| 2 | Sala de Espera | waiting | Amber/Yellow |
| 3 | Procesando | processing | Blue |
| 4 | Data Room | completed | Green |
| 5 | Fallidos | failed | Red |

### Column behavior
- Each column shows a count badge with the number of assets
- Assets are displayed as cards sorted by `created_at` descending (newest first)
- Columns should scroll vertically if content overflows

### Top bar
- App title: "Second Brain"
- Button: "+ Nuevo Asset" (opens asset creation form)
- Optional: search field that filters visible cards

### Asset Card (within each column)
Each card shows:
- **Title**: `asset.title` or "Sin titulo" if null, truncated to 60 chars
- **Type badge**: small colored pill showing `asset.type` (text=gray, url=blue, pdf=red, audio=purple, image=green)
- **Priority**: show as a number badge (1-5) with color gradient (1=light gray, 5=red)
- **Confidence**: show as a thin progress bar (0-100%) only if `confidence_score` is not null
- **Tags**: show first 3 tags as small pills, "+N" if more
- **Verification badge**: small green checkmark icon if `verified_by_human = true`, otherwise a small gray circle
- **Created date**: relative format ("hace 2h", "ayer", etc.)

### Card click
Clicking a card opens the Asset Detail Drawer (see section 5).

### New Asset Form
Triggered by "+ Nuevo Asset" button. A modal or slide-over with:
- **Type selector**: radio buttons or dropdown for text, url, pdf, audio, image
- **Title**: optional text input
- **Content**: a large textarea for raw_payload (only if type=text or type=url)
- **Source URL**: text input (visible if type=url)
- **Submit button**: "Crear Asset"

On submit: `POST /assets` with the form data.
On success: the new asset card appears in the "Ingreso" column.
After creation: automatically transition to waiting via `POST /assets/{id}/transition` with `to_status: "waiting"`.

---

## 5. Screen: Asset Detail Drawer

**API**: `GET /assets/{id}`

Opens as a slide-over panel from the right side (60-70% width) when a card is clicked.

### Section 5.1: Header

- **Title**: editable inline text field bound to `asset.title`
- **Type badge**: same as card
- **Status badge**: colored badge showing current status
- **Close button**: X in top right

### Section 5.2: Metadata Bar

A horizontal bar with:
- **Priority**: editable number selector (1-5) bound to `asset.priority`
- **Confidence**: read-only display of `asset.confidence_score` as percentage
- **Verified toggle**: a switch/toggle bound to `asset.verified_by_human`
  - When toggled ON: `PATCH /assets/{id}` with `verified_by_human: true`
  - Shows `verified_at` timestamp below when true
- **Tags**: editable tag pills. Click to remove, input to add. Bound to `asset.tags`
- **Save button**: saves all metadata changes via `PATCH /assets/{id}`

### Section 5.3: Content Tabs

Two tabs:

**Tab: Original**
- Shows `asset.raw_payload` in a read-only monospace text area
- If `raw_storage_path` exists, show a "file attached" indicator

**Tab: Refined**
- Shows `asset.refined_markdown` rendered as formatted Markdown
- If empty, show: "Este asset aun no ha sido enriquecido por Claude"

### Section 5.4: Claude Interaction Panel

This panel is visible ONLY when asset status is `waiting` or `processing`.

**Step A: Generate Prompt**
- Button: "Preparar para Claude"
- On click: `POST /queue/{id}/prepare_prompt`
- On success: show the returned `prompt_text` in a read-only text area
- Button: "Copiar al Portapapeles" (copies prompt_text to clipboard)
- Visual confirmation: brief "Copiado!" toast

**Step B: Paste JSON**
- Label: "Pegar respuesta de Claude"
- A large textarea where the user pastes the JSON returned by Claude
- Validation runs automatically on every change (onChange), with a 300ms debounce
- No separate "Validar JSON" button — feedback is always live
- Validation states:
  - **Empty**: no feedback shown
  - **Parsing error**: red banner "JSON no es valido. Revisa el formato."
  - **Schema errors**: red bullet list, one line per error, format: "campo: descripcion del error"
    - Examples:
      - "priority: este campo es obligatorio"
      - "priority: debe ser un numero entre 1 y 5"
      - "tags[4]: el texto no puede superar 40 caracteres"
  - **Valid**: green checkmark with text "JSON valido" shown below the textarea

**Step C: Import**
- Button: "Importar y Completar"
- DISABLED unless live validation shows green (R1, R3)
- Enabled state: solid color, clickable
- Disabled state: grayed out, not clickable, tooltip "Pega un JSON valido para continuar"
- On click: `POST /queue/{id}/import_enriched` with body:
  ```json
  {
    "enriched_json": <parsed JSON object>,
    "mark_verified": <value of toggle below>,
    "model_used": "Claude Web"
  }
  ```
- Toggle below button: "Marcar como verificado al importar" (default OFF)
- On success:
  - Show success toast "Asset completado"
  - Card moves to "Data Room" column
  - Drawer updates to show completed state
- On API error (422):
  - Show the `detail` field from the response in red
  - Asset stays in current column

### Section 5.5: Actions (for failed assets)

Visible ONLY when status is `failed`:
- Button: "Reintentar" -> `POST /assets/{id}/retry`
- On success: card moves to "Sala de Espera"

---

## 6. Field Bindings (API name -> UI label)

| API Field | UI Label | Where Shown |
|-----------|----------|-------------|
| title | Titulo | Card, Drawer header |
| type | Tipo | Card badge, Drawer badge |
| status | Estado | Column placement, Drawer badge |
| priority | Prioridad | Card number, Drawer selector |
| confidence_score | Confianza | Card bar, Drawer percentage |
| verified_by_human | Verificado | Card icon, Drawer toggle |
| verified_at | Verificado el | Drawer metadata |
| tags | Tags | Card pills, Drawer editable pills |
| raw_payload | Contenido Original | Drawer Original tab |
| refined_markdown | Contenido Refinado | Drawer Refined tab |
| enriched_data | (internal) | Not shown directly |
| created_at | Creado | Card relative date |

---

## 7. Visual Conventions

### Status Colors
- ingested: `gray-400` background, `gray-700` text
- waiting: `amber-100` background, `amber-800` text
- processing: `blue-100` background, `blue-800` text
- completed: `green-100` background, `green-800` text
- failed: `red-100` background, `red-800` text

### Priority Colors
- 1: `gray-300`
- 2: `blue-300`
- 3: `yellow-400`
- 4: `orange-400`
- 5: `red-500`

### Type Icons/Colors
- text: document icon, gray
- url: link icon, blue
- pdf: file icon, red
- audio: music icon, purple
- image: camera icon, green

### General Style
- Clean, minimal design
- White background with subtle gray borders
- System font stack
- Responsive: works on desktop (primary) and tablet
- Dark mode: not required for MVP

---

## 8. User Flows

### Flow 1: Create and Process a Note
1. User clicks "+ Nuevo Asset"
2. Selects type "text", enters title and content
3. Clicks "Crear Asset" -> card appears in "Ingreso", auto-moves to "Sala de Espera"
4. User clicks the card -> drawer opens
5. Clicks "Preparar para Claude" -> prompt appears
6. Clicks "Copiar al Portapapeles"
7. Goes to claude.ai, pastes prompt, gets JSON back
8. Returns to app, pastes JSON in the text area
9. Live validation shows green checkmark automatically
10. Clicks "Importar y Completar" -> card moves to "Data Room"
11. Opens card, sees refined markdown, toggles "Verificado"

### Flow 2: Handle Invalid JSON
1. User pastes malformed JSON in step 8
2. Live validation immediately shows: "JSON no es valido. Revisa el formato."
3. "Importar y Completar" stays disabled
4. User fixes and retries

### Flow 3: Handle Schema Validation Errors
1. User pastes valid JSON but missing required field "priority"
2. Live validation immediately shows: "priority: este campo es obligatorio"
3. "Importar y Completar" stays disabled
4. User goes back to Claude, asks for correction, pastes fixed JSON
5. Live validation shows green checkmark, button enables

### Flow 4: Retry Failed Asset
1. Asset is in "Fallidos" column
2. User clicks card -> drawer opens
3. Clicks "Reintentar" -> card moves to "Sala de Espera"
4. User can now re-process with Claude

---

## 9. Acceptance Tests (UI level)

| # | Test | Expected |
|---|------|----------|
| T1 | Create asset via form | Card appears in Ingreso, auto-transitions to Sala de Espera |
| T2 | Click card | Drawer opens with all sections |
| T3 | Click "Preparar para Claude" | Prompt text appears, copy button works |
| T4 | Paste valid JSON | Live validation shows green, Import button enables automatically |
| T5 | Paste invalid JSON | Live validation shows red errors, Import button stays disabled |
| T6 | Paste JSON missing one required field | Specific field error shown, button disabled |
| T7 | Click "Importar y Completar" with valid JSON | Card moves to Data Room |
| T8 | Toggle verified_by_human | Badge updates, verified_at shows timestamp |
| T9 | Click Retry on failed asset | Card moves to Sala de Espera |
| T10 | Kanban shows correct counts | Each column header shows accurate count |
| T11 | Edit title, priority, tags in drawer | Changes persist after refresh |

---

## 10. API Endpoints Used by UI

| Action | Method | Endpoint |
|--------|--------|----------|
| Load Kanban | GET | /kanban |
| Create asset | POST | /assets |
| Get asset detail | GET | /assets/{id} |
| Update asset fields | PATCH | /assets/{id} |
| Change state | POST | /assets/{id}/transition |
| Retry failed | POST | /assets/{id}/retry |
| Generate prompt | POST | /queue/{id}/prepare_prompt |
| Import enriched JSON | POST | /queue/{id}/import_enriched |

---

## 11. Error Display Rules

- Never show stack traces to the user
- JSON validation errors: shown inline below the textarea as a bullet list (field + error)
- API errors: show the `detail` field from the response
- Network errors: show "Error de conexion. Verifica que el servidor esta activo."
- All error messages in Spanish