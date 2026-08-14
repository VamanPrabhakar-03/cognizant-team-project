"""Review Decision Schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReviewCreateRequest(BaseModel):
    supported_id: int = 0
    suspect_id: str
    decision: str  # SUPPORTED | NOT_SUPPORTED | INSUFFICIENT_EVIDENCE
    notes: Optional[str] = None
    reviewer_id: Optional[str] = "human_coder"


class ReviewDecisionSchema(BaseModel):
    id: int
    suspect_id: str
    bene_id: str
    hcc_v28: str
    suspect_type: Optional[str] = None
    priority_score: Optional[float] = None
    decision: str
    notes: Optional[str] = None
    reviewer_timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewDecisionListResponse(BaseModel):
    items: List[ReviewDecisionSchema]
    total: int
    page: int
    size: int
    pages: int


class ReviewStatsResponse(BaseModel):
    supported: int
    not_supported: int
    insufficient: int
