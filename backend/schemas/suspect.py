"""Suspect Pydantic Schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from schemas.member import (
    MemberBase,
    BaselineHCCSchema,
    TimelineEventSchema,
)


class SuspectSchema(BaseModel):
    """Suspect record schema."""
    suspect_id: str = Field(..., description="Unique Suspect ID")
    bene_id: str = Field(..., description="Beneficiary ID")
    hcc_v28: str = Field(..., description="HCC V28 Category Code")
    suspect_type: str = Field(..., description="Suspect Type: EMERGING or RECAPTURE")
    priority_score: float = Field(..., description="Priority Score between 0.0 and 1.0")
    status: str = Field("PENDING_REVIEW", description="Review status (PENDING_REVIEW, REVIEWED, etc.)")
    supporting_diagnosis_codes: Optional[List[str]] = Field(default_factory=list, description="Supporting ICD-10 diagnosis codes")
    supporting_claim_ids: Optional[List[str]] = Field(default_factory=list, description="Supporting claim IDs")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("supporting_diagnosis_codes", "supporting_claim_ids", mode="before")
    @classmethod
    def parse_pipe_list(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split("|") if item.strip()]
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_str(cls, v):
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    class Config:
        from_attributes = True


class SuspectListResponse(BaseModel):
    """Paginated list of suspects response."""
    total: int
    page: int
    size: int
    pages: int
    items: List[SuspectSchema]


class SuspectStatusUpdate(BaseModel):
    """Payload for updating suspect review status."""
    status: str = Field(..., description="New status (e.g. PENDING_REVIEW, REVIEWED)")


class SuspectDetailResponse(BaseModel):
    """Detailed result for a single suspect record."""
    suspect: SuspectSchema
    member: Optional[MemberBase] = None
    baseline_hccs: List[BaselineHCCSchema] = []
    supporting_events: List[TimelineEventSchema] = []
