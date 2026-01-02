# Meeting Notes Agent (Portfolio Project)

A production-minded mini agent that turns raw meeting notes into:
1) a clean markdown summary, and  
2) a strict JSON list of action items (action, owner, due date, confidence)

It is designed to demonstrate **enterprise agent patterns**: strict schemas, guardrails, trace IDs, safe fallbacks, and containerized deployment.

---

## What it does (MVP 1)

**Input:** meeting title + raw notes  
**Output:**
- `markdown`: a readable summary
- `actions[]`: extracted action items (strict JSON schema)
- `unassigned_count`: how many actions have no owner (explicitly missing)

### Guardrail behavior (anti-hallucination)
Owners and due dates are only included when explicitly present in the notes.  
If an owner is inferred (not explicit), the system removes it and lowers confidence.

---

## Architecture (Layer mapping)

- **App / API layer:** `app/main.py`  
  FastAPI routes + request/response wiring, returns JSON + serves the UI.

- **AI Gateway layer:** `app/services/llm_client.py`  
  Creates the Azure OpenAI client using env vars, selects deployment.

- **Execution layer (LLM calls):**
  - `app/services/action_extractor.py` (structured action extraction via JSON schema)
  - `app/services/summarizer.py` (summary generation)

- **Validation / Guardrails layer:** `app/services/validators.py`  
  Prevents hallucinated owners by requiring explicit mention.

- **Observability layer:** request IDs + logs  
  Each request gets `X-Request-Id` and is logged end-to-end.

> Note: A dedicated **Planner layer** (LangGraph) is planned next.  
> Right now orchestration is a simple linear pipeline in `app/main.py`.

---

## Run locally (uv)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
