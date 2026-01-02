from fastapi import FastAPI, Response, Request, Form
from fastapi.templating import Jinja2Templates

from app.core.logging import new_request_id
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services.action_extractor import extract_actions
from app.services.summarizer import build_summary_markdown
from app.services.validators import owner_appears_in_text

app = FastAPI(title="Meeting Notes Agent", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")


@app.get("/health")
def health():
    return {"status": "ok"}


# -------------------------
# API Layer (JSON endpoint)
# -------------------------
@app.post("/v1/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest, response: Response):
    request_id = new_request_id()
    response.headers["X-Request-Id"] = request_id

    print(f"[{request_id}] /v1/summarize START title={req.meeting_title!r} chars={len(req.text)}")

    actions = extract_actions(req.text, request_id)
    print(f"[{request_id}] actions_extracted count={len(actions)}")

    # Validation/Guardrails layer: owner must appear in text
    safe_actions = []
    for a in actions:
        if a.owner and not owner_appears_in_text(a.owner, req.text):
            a.owner = None
            a.confidence = min(a.confidence, 0.4)
        safe_actions.append(a)
    actions = safe_actions

    print(f"[{request_id}] guardrails_applied unassigned={sum(1 for a in actions if a.owner is None)}")

    markdown = build_summary_markdown(req.text, req.meeting_title, request_id)
    unassigned = sum(1 for a in actions if a.owner is None)

    print(f"[{request_id}] /v1/summarize END")
    return SummarizeResponse(markdown=markdown, actions=actions, unassigned_count=unassigned)


# -------------------------
# UI Layer (HTML frontend)
# -------------------------
@app.get("/")
def ui_home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "meeting_title": "",
            "text": "",
            "markdown": None,
            "actions": None,
            "request_id": None,
        },
    )


@app.post("/ui/summarize")
def ui_summarize(request: Request, meeting_title: str = Form(""), text: str = Form(...)):
    request_id = new_request_id()

    print(f"[{request_id}] /ui/summarize START title={meeting_title!r} chars={len(text)}")

    actions = extract_actions(text, request_id)
    print(f"[{request_id}] actions_extracted count={len(actions)}")

    safe_actions = []
    for a in actions:
        if a.owner and not owner_appears_in_text(a.owner, text):
            a.owner = None
            a.confidence = min(a.confidence, 0.4)
        safe_actions.append(a)
    actions = safe_actions

    markdown = build_summary_markdown(text, meeting_title, request_id)

    print(f"[{request_id}] /ui/summarize END")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "meeting_title": meeting_title,
            "text": text,
            "markdown": markdown,
            "actions": actions,
            "request_id": request_id,
        },
    )
