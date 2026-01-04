from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field

from app.schemas.summarize import ActionItem


class MeetingAnalytics(BaseModel):
    top_owner: Optional[str] = None
    top_owner_task_count: int = 0


class MeetingPackResponse(BaseModel):
    tenant_id: str
    user_id: str
    request_id: str

    source: Literal["text", "image", "pdf"]
    ocr_used: bool
    ocr_pages: int
    ocr_confidence: Optional[float] = None

    markdown: str
    actions: List[ActionItem] = Field(default_factory=list)
    unassigned_count: int = 0

    # MVP2+ (we’ll fill these next)
    decisions: List[str] = Field(default_factory=list)
    analytics: MeetingAnalytics = Field(default_factory=MeetingAnalytics)
