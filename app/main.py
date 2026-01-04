import os
from typing import List

from fastapi import FastAPI, Response, Request, Form, UploadFile, File, Header, HTTPException
from fastapi.templating import Jinja2Templates

from app.core.logging import new_request_id
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.schemas.meeting_pack import MeetingPackResponse, MeetingAnalytics
from app.schemas.usage import UsageEventRow

from app.services.action_extractor import extract_actions
from app.services.summarizer import build_summary_markdown
from app.services.validators import owner_appears_in_text
from app.services.decision_extractor import extract_decisions

from app.services.ocr.azure_doc_intel import AzureDocIntelOcr
from app.services.ingest import ingest as ingest_input

from app.services.usage_db import init_db, log_event, now_utc_iso, UsageEvent, list_events
from app.services.usage_db import list_events, count_ocr_split
from app.services.usage_db import init_db, log_event, now_utc_iso, UsageEvent, list_events, count_ocr_split
from app.services.usage_metrics import get_usage_summary, to_dict as usage_to_dict



app = FastAPI(title="Meeting Notes Agent", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def _startup():
    init_db()


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

    # Guardrail: owner must appear in source text
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


def _max_upload_bytes() -> int:
    mb = int(os.getenv("MAX_UPLOAD_MB", "50"))
    return mb * 1024 * 1024


@app.post("/v2/meeting/pack", response_model=MeetingPackResponse)
async def meeting_pack_v2(
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    # 1) Read file (if provided) + enforce size limit
    file_bytes = None
    filename = None
    content_type = None

    if file is not None:
        filename = file.filename
        content_type = file.content_type
        file_bytes = await file.read()

        if len(file_bytes) > _max_upload_bytes():
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    # 2) OCR client (used only if ingest decides OCR is needed)
    ocr = AzureDocIntelOcr(
        endpoint=os.getenv("AZURE_DOC_INTEL_ENDPOINT", ""),
        key=os.getenv("AZURE_DOC_INTEL_KEY", ""),
    )

    try:
        ing = ingest_input(
            text=text,
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            ocr=ocr,
            max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "20")),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3) Reuse MVP1 pipeline on ing.text
    request_id = new_request_id()

    actions = extract_actions(ing.text, request_id)

    # Guardrail: owner must appear in source text
    safe_actions = []
    for a in actions:
        if a.owner and not owner_appears_in_text(a.owner, ing.text):
            a.owner = None
            a.confidence = min(a.confidence, 0.4)
        safe_actions.append(a)
    actions = safe_actions

    unassigned = sum(1 for a in actions if a.owner is None)
    markdown = build_summary_markdown(ing.text, "", request_id)
    decisions = extract_decisions(ing.text, request_id)

    # --- Usage logging (SQLite) ---
    token_estimate = max(1, len(ing.text) // 4)
    log_event(
        UsageEvent(
            tenant_id=x_tenant_id,
            user_id=x_user_id,
            request_id=request_id,
            endpoint="/v2/meeting/pack",
            source=ing.source,
            ocr_used=ing.ocr_used,
            ocr_pages=ing.ocr_pages,
            token_estimate=token_estimate,
            created_at_utc=now_utc_iso(),
        )
    )

    # analytics (deterministic)
    counts = {}
    for a in actions:
        if a.owner:
            counts[a.owner] = counts.get(a.owner, 0) + 1
    top_owner = max(counts, key=counts.get) if counts else None
    top_count = counts[top_owner] if top_owner else 0

    return MeetingPackResponse(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        request_id=request_id,
        source=ing.source,
        ocr_used=ing.ocr_used,
        ocr_pages=ing.ocr_pages,
        ocr_confidence=ing.ocr_confidence,
        markdown=markdown,
        actions=actions,
        unassigned_count=unassigned,
        decisions=decisions,
        analytics=MeetingAnalytics(top_owner=top_owner, top_owner_task_count=top_count),
    )


@app.get("/v2/usage/summary")
def usage_summary(
    tenant_id: str,
    user_id: str | None = None,
):
    summary = get_usage_summary(tenant_id=tenant_id, user_id=user_id)
    return usage_to_dict(summary)


@app.get("/v2/usage/events", response_model=List[UsageEventRow])
def usage_events(
    tenant_id: str,
    user_id: str | None = None,
    limit: int = 20,
):
    rows = list_events(tenant_id=tenant_id, user_id=user_id, limit=limit)
    return rows

# -------------------------
# UI Layer (HTML frontend)
# -------------------------
# -------------------------
# UI Layer (HTML frontend)
# -------------------------
@app.get("/")
def ui_home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "text": "",
            "pack": None,
            "tenant_usage": None,
            "user_usage": None,
            "usage_events": None,
        },
    )


@app.post("/ui/pack")
async def ui_pack(
    request: Request,
    tenant_id: str = Form("demo-tenant"),
    user_id: str = Form("angad"),
    text: str = Form(""),
    file: UploadFile | None = File(default=None),
):
    # 1) Read file (optional) + enforce upload limit
    file_bytes = None
    filename = None
    content_type = None

    if file is not None and file.filename:
        filename = file.filename
        content_type = file.content_type
        file_bytes = await file.read()

        if len(file_bytes) > _max_upload_bytes():
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    # 2) OCR client (only used if ingest decides OCR is needed)
    ocr = AzureDocIntelOcr(
        endpoint=os.getenv("AZURE_DOC_INTEL_ENDPOINT", ""),
        key=os.getenv("AZURE_DOC_INTEL_KEY", ""),
    )

    try:
        ing = ingest_input(
            text=text if text.strip() else None,
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            ocr=ocr,
            max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "20")),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3) Run pipeline
    request_id = new_request_id()

    actions = extract_actions(ing.text, request_id)

    # Guardrail: owner must appear in source text
    safe_actions = []
    for a in actions:
        if a.owner and not owner_appears_in_text(a.owner, ing.text):
            a.owner = None
            a.confidence = min(a.confidence, 0.4)
        safe_actions.append(a)
    actions = safe_actions

    unassigned = sum(1 for a in actions if a.owner is None)
    markdown = build_summary_markdown(ing.text, "", request_id)
    decisions = extract_decisions(ing.text, request_id)

    # Analytics (deterministic)
    counts: dict[str, int] = {}
    for a in actions:
        if a.owner:
            counts[a.owner] = counts.get(a.owner, 0) + 1
    top_owner = max(counts, key=counts.get) if counts else None
    top_count = counts[top_owner] if top_owner else 0

    # 4) Usage logging
    token_estimate = max(1, len(ing.text) // 4)

    log_event(
        UsageEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            endpoint="/ui/pack",
            source=ing.source,
            ocr_used=ing.ocr_used,
            ocr_pages=ing.ocr_pages,
            token_estimate=token_estimate,
            created_at_utc=now_utc_iso(),
        )
    )

    # 5) This-run cost estimate (simple)
    llm_cost_per_1k = float(os.getenv("LLM_COST_PER_1K_TOKENS_USD", "0.001"))
    ocr_cost_per_page = float(os.getenv("OCR_COST_PER_PAGE_USD", "0.0015"))

    llm_cost_usd = (token_estimate / 1000.0) * llm_cost_per_1k
    ocr_cost_usd = (ing.ocr_pages * ocr_cost_per_page) if ing.ocr_used else 0.0
    total_cost_usd = llm_cost_usd + ocr_cost_usd

    # 6) Tenant/user usage summaries + OCR split + last 20 events
    tenant_summary = get_usage_summary(tenant_id=tenant_id, user_id=None)
    user_summary = get_usage_summary(tenant_id=tenant_id, user_id=user_id)

    tenant_ocr, tenant_non_ocr = count_ocr_split(tenant_id=tenant_id, user_id=None)
    user_ocr, user_non_ocr = count_ocr_split(tenant_id=tenant_id, user_id=user_id)

    tenant_usage = usage_to_dict(tenant_summary)
    tenant_usage["ocr_requests"] = tenant_ocr
    tenant_usage["non_ocr_requests"] = tenant_non_ocr

    user_usage = usage_to_dict(user_summary)
    user_usage["ocr_requests"] = user_ocr
    user_usage["non_ocr_requests"] = user_non_ocr

    usage_events = list_events(tenant_id=tenant_id, user_id=None, limit=20)

    # 7) Pack object for UI
    pack = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "request_id": request_id,
        "source": ing.source,
        "ocr_used": ing.ocr_used,
        "ocr_pages": ing.ocr_pages,
        "ocr_confidence": ing.ocr_confidence,
        "markdown": markdown,
        "actions": [a.model_dump() for a in actions],
        "unassigned_count": unassigned,
        "decisions": decisions,
        "analytics": {"top_owner": top_owner, "top_owner_task_count": top_count},
        "usage": {
            "token_estimate": token_estimate,
            "llm_cost_usd_est": llm_cost_usd,
            "ocr_cost_usd_est": ocr_cost_usd,
            "total_cost_usd_est": total_cost_usd,
        },
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "text": text,
            "pack": pack,
            "tenant_usage": tenant_usage,
            "user_usage": user_usage,
            "usage_events": usage_events,
        },
    )
