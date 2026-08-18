"""Schemas for incremental claims-batch processing."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClaimInput(BaseModel):
    bene_id: str = Field(..., min_length=1)
    claim_id: Optional[str] = None
    claim_date: Optional[str] = None
    event_date: Optional[str] = None
    diagnosis_code: Optional[str] = None
    source: Optional[str] = None
    is_principal: bool = False
    extra: Dict[str, Any] = Field(default_factory=dict)


class ClaimBatchCreateRequest(BaseModel):
    source_file: Optional[str] = None
    source_system: Optional[str] = None
    batch_id: Optional[str] = None
    run_id: Optional[str] = None
    created_by: Optional[str] = None
    claims: List[ClaimInput] = Field(..., min_length=1, max_length=50_000)


class BatchIngestionResponse(BaseModel):
    run_id: str
    batch_id: str
    status: str
    input_rows: int
    valid_rows: int
    inserted_rows: int
    rejected_rows: int
    suspects: int = 0
    evidence: int = 0
    llm_reviews: int = 0


class ZipUploadResponse(BatchIngestionResponse):
    """Response for the raw CMS ZIP upload endpoint.

    Extends BatchIngestionResponse with per-source preprocessing statistics
    so the caller can see exactly how many raw claims and diagnosis rows were
    extracted from each claim file inside the ZIP.

    preprocessing_stats keys (present only for files found in the ZIP):
      INPATIENT             - exploded diagnosis rows from inpatient.csv
      INPATIENT_raw_claims  - raw CMS claim rows in inpatient.csv
      INPATIENT_skipped     - rows skipped due to missing BENE_ID
      OUTPATIENT            - exploded diagnosis rows from outpatient.csv
      OUTPATIENT_raw_claims
      OUTPATIENT_skipped
      CARRIER               - exploded diagnosis rows from carrier.csv
      CARRIER_raw_claims
      CARRIER_skipped
      PDE                   - prescription event rows from pde.csv
      raw_claims_total      - total raw CMS claim rows across all files
      diagnosis_rows_total  - total exploded diagnosis rows
    """
    preprocessing_stats: Dict[str, int] = Field(default_factory=dict)
    pde_inserted: int = 0


class PipelineRunSchema(BaseModel):
    run_id: str
    batch_id: Optional[str] = None
    source_file: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_rows: int
    valid_rows: int
    rejected_rows: int
    claims_processed: int
    suspects_created: int
    evidence_created: int
    llm_reviews_created: int
    error_message: Optional[str] = None
    created_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
