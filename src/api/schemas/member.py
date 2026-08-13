"""Member Pydantic Schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class MemberBase(BaseModel):
    """Base schema for Member demographics."""
    bene_id: str = Field(..., description="Unique Beneficiary ID")
    age: Optional[int] = Field(None, description="Beneficiary Age")
    sex: Optional[str] = Field(None, description="Beneficiary Sex (1=Male, 2=Female)")
    state: Optional[str] = Field(None, description="US State code")

    class Config:
        from_attributes = True


class MemberListResponse(BaseModel):
    """Paginated list of members response."""
    total: int = Field(..., description="Total count of members matching query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size limit")
    pages: int = Field(..., description="Total available pages")
    items: List[MemberBase] = Field(..., description="List of members")


class BaselineHCCSchema(BaseModel):
    """Baseline HCC record schema."""
    id: int
    bene_id: str
    hcc_v28: str
    hcc_description: Optional[str] = None
    baseline_diagnosis_codes: Optional[List[str]] = None

    @field_validator("baseline_diagnosis_codes", mode="before")
    @classmethod
    def parse_pipe_codes(cls, v):
        if isinstance(v, str):
            return [code.strip() for code in v.split("|") if code.strip()]
        return v

    class Config:
        from_attributes = True


class TimelineEventSchema(BaseModel):
    """Member Timeline Event schema."""
    id: int
    bene_id: str
    event_date: str
    event_type: str
    code: str
    hcc_v28: Optional[str] = None
    source: str
    claim_id: Optional[str] = None
    is_principal: Optional[bool] = False

    @field_validator("event_date", mode="before")
    @classmethod
    def parse_date_to_str(cls, v):
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    """Paginated timeline response schema."""
    bene_id: str
    total: int
    page: int
    size: int
    pages: int
    items: List[TimelineEventSchema]


class MemberStats(BaseModel):
    """Summary statistics for a single member."""
    total_claims: int = 0
    total_diagnoses: int = 0
    baseline_hcc_count: int = 0
    suspect_hcc_count: int = 0
    pending_review_count: int = 0


# Import SuspectSchema after defining member primitives to prevent circular imports
from src.api.schemas.suspect import SuspectSchema


class MemberDetailResponse(BaseModel):
    """Detailed response for a single member."""
    member: MemberBase
    baseline_hccs: List[BaselineHCCSchema] = []
    suspects: List[SuspectSchema] = []
    stats: MemberStats