"""Suspect Pydantic Schemas."""

from typing import Any, List, Optional
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
    gap_type: Optional[str] = None
    latest_context: Optional[str] = None
    priority: Optional[str] = None
    priority_level: Optional[str] = None
    diagnosis_count: int = 0
    unique_claim_count: int = 0
    unique_event_count: int = 0
    distinct_evidence_dates: int = 0
    distinct_evidence_months: int = 0
    distinct_sources: int = 0
    principal_diagnosis_count: int = 0
    prescription_support_count: int = 0
    prescription_drug_codes: Optional[List[str]] = None
    repeated_claim_score: float = 0.0
    repeated_date_score: float = 0.0
    source_diversity_score: float = 0.0
    principal_score: float = 0.0
    prescription_score: float = 0.0
    reason_flags: Optional[List[str]] = None
    evidence_summary: Optional[str] = None
    evidence_references: Optional[List[dict[str, Any]]] = None
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
