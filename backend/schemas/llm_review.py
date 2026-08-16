"""Schemas for evidence-grounded LLM reviewer summaries."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class LLMReviewSchema(BaseModel):
    id: int
    suspect_id: str
    pipeline_run_id: Optional[str] = None
    status: str
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    reviewer_summary: Optional[str] = None
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
