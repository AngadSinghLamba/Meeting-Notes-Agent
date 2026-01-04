from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class UsageEventRow(BaseModel):
    id: int
    tenant_id: str
    user_id: str
    request_id: str
    endpoint: str
    source: str
    ocr_used: bool
    ocr_pages: int
    token_estimate: int
    created_at_utc: str
