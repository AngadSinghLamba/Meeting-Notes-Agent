from pydantic import BaseModel, Field
from typing import Optional, List


class SummarizeRequest(BaseModel):
    meeting_title: Optional[str] = None
    text: str = Field(min_length=10)


class ActionItem(BaseModel):
    action: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class SummarizeResponse(BaseModel):
    markdown: str
    actions: List[ActionItem]
    unassigned_count: int
