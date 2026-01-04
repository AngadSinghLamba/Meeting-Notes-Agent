# Meeting Notes Agent (Portfolio Project)

A production-minded mini agent that turns raw meeting notes into:
1) a clean markdown summary, and  
2) a strict JSON list of action items (action, owner, due date, confidence)

MVP2 adds: **text OR image/PDF upload → OCR (if needed) → decisions + analytics + usage/cost logging**.

It is designed to demonstrate **enterprise agent patterns**: strict schemas, guardrails, trace IDs, safe fallbacks, adapter-based OCR, usage telemetry, and containerized deployment.

---

## What it does

### MVP1 (Text-only)
**Input:** meeting title + raw notes  
**Output:**
- `markdown`: readable summary
- `actions[]`: extracted action items (strict JSON schema)
- `unassigned_count`: how many actions have no owner

### MVP2 (Meeting Pack: Text OR Upload)
**Input:** either:
- `text` (form field), OR
- `file` (JPG/PNG/PDF; handwritten/screenshot/scanned PDF supported)

**Pipeline:**
- If upload is image/PDF → OCR via **Azure Document Intelligence**
- Reuse the same extraction pipeline on the resulting text
- Add decisions extraction + analytics + usage logging

**Output (Meeting Pack):**
- `tenant_id`, `user_id`, `request_id`
- `source`: `text | image | pdf`
- `ocr_used`, `ocr_pages`, `ocr_confidence`
- `markdown`
- `actions[]`, `unassigned_count`
- `decisions[]`
- `analytics.top_owner`, `analytics.top_owner_task_count`

---

## Guardrails (anti-hallucination)
Owners are only included when explicitly present in the notes/OCR text.  
If an owner is inferred (not explicit), the system removes it and lowers confidence.

---

## Architecture (Layer mapping)

- **App / API layer:** `app/main.py`  
  FastAPI routes + request/response wiring, returns JSON + serves the UI.

- **Ingest / OCR adapter layer:**
  - `app/services/ingest.py` (decides if OCR is needed; handles text vs file)
  - `app/services/ocr/azure_doc_intel.py` (Azure Document Intelligence OCR)

- **Execution layer (LLM calls):**
  - `app/services/action_extractor.py` (structured action extraction via JSON schema)
  - `app/services/summarizer.py` (summary generation)
  - `app/services/decision_extractor.py` (decision extraction)

- **Validation / Guardrails layer:** `app/services/validators.py`  
  Prevents hallucinated owners by requiring explicit mention.

- **Usage / telemetry layer:**
  - `app/services/usage_db.py` (SQLite events)
  - `app/services/usage_metrics.py` (summary/cost estimates)

> Note: A dedicated **Planner/Workflow layer (LangGraph)** is intentionally out of scope for MVP2.  
> Orchestration is a single-agent, linear pipeline to keep the project teachable and production-minded.

---

## Run locally (uv)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000

Open:

UI: http://127.0.0.1:8000/

Swagger: http://127.0.0.1:8000/docs

Run locally (Docker)
1) Configure environment

Create a .env file:

cp .env.example .env


Fill these in .env (do NOT commit .env):

AZURE_OPENAI_BASE_URL

AZURE_OPENAI_API_KEY

AZURE_OPENAI_DEPLOYMENT

AZURE_DOC_INTEL_ENDPOINT

AZURE_DOC_INTEL_KEY

2) Build image
docker build -t meeting-notes-agent:mvp2 .

3) Run container
Option A — Clean run (no persistence)

Usage DB resets each run.

docker run --rm -p 8000:8000 --env-file .env meeting-notes-agent:mvp2

Option B — Persistent usage.db (recommended for demos)

Keeps data/usage.db on your machine across restarts.

mkdir -p data
docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" meeting-notes-agent:mvp2

Quick API tests
MVP2: Meeting Pack (text)
curl -s -X POST "http://127.0.0.1:8000/v2/meeting/pack" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-User-Id: angad" \
  -F "text=Decision: Ship MVP2 on Friday. Action: Angad to update BRD by Wednesday."

MVP2: Meeting Pack (image/PDF OCR)
curl -s -X POST "http://127.0.0.1:8000/v2/meeting/pack" \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-User-Id: angad" \
  -F "file=@./data/samples/sample-text-2.jpeg"

Usage summary (tenant + user)
curl -s "http://127.0.0.1:8000/v2/usage/summary?tenant_id=demo-tenant&user_id=angad"

Last N usage events
curl -s "http://127.0.0.1:8000/v2/usage/events?tenant_id=demo-tenant&limit=20"

Notes

.env is ignored; .env.example provides placeholders.

data/usage.db is runtime data; it should be ignored by git (data/*.db).

OCR is only invoked when required (image/scanned PDF). Text inputs skip OCR.



