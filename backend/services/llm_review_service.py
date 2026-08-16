"""Generate evidence-grounded, human-readable reviews from suspect JSON."""

import json
import os
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import LLMReview


PROMPT_VERSION = "hcc-human-review-gemini-v1"
DEFAULT_MODEL = "gemini-3.6-flash"


class HumanReviewOutput(BaseModel):
    reviewer_summary: str = Field(description="Concise plain-language summary for the human reviewer.")
    evidence_assessment: str = Field(description="Evidence-only assessment: strong, moderate, limited, or no_evidence.")
    recommended_next_step: str = Field(description="A record-review action; never a coding or diagnosis decision.")
    limitations: list[str] = Field(description="Missing, conflicting, or insufficient evidence in the supplied JSON.")


SYSTEM_PROMPT = (
    "You are an evidence-grounded assistant supporting a Medicare Advantage documentation reviewer. "
    "Analyze only the supplied JSON. Do not infer facts that are not present. Do not diagnose a patient, "
    "choose a billing code, make a payment claim, or state that an HCC is clinically supported. Explain the "
    "evidence plainly, identify limitations, and recommend that a qualified human review the associated medical "
    "record. Your reviewer_summary must be readable text for a human reviewer and must state that it is decision "
    "support, not a final coding decision."
)


def generate_llm_review(db: Session, review_id: int) -> LLMReview:
    """Call Gemini and save its constrained review response."""
    review = db.get(LLMReview, review_id)
    if review is None:
        raise ValueError(f"LLM review '{review_id}' not found.")
    if not review.input_payload:
        raise ValueError(f"LLM review '{review_id}' has no input JSON payload.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    try:
        from google import genai

        model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        client = genai.Client(api_key=api_key)
        response = client.interactions.create(
            model=model,
            input=(
                f"{SYSTEM_PROMPT}\n\n"
                f"Evidence JSON to analyze:\n{json.dumps(review.input_payload)}"
            ),
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": HumanReviewOutput.model_json_schema(),
            },
        )
        if not response.output_text:
            raise ValueError("The model returned no structured review output.")
        parsed = HumanReviewOutput.model_validate_json(response.output_text)

        review.output_payload = parsed.model_dump()
        review.reviewer_summary = parsed.reviewer_summary
        review.model_name = model
        review.prompt_version = PROMPT_VERSION
        review.status = "COMPLETED"
        review.error_message = None
        review.generated_at = datetime.utcnow()
        db.commit()
        db.refresh(review)
        return review
    except Exception as exc:
        db.rollback()
        review = db.get(LLMReview, review_id)
        if review is not None:
            review.status = "FAILED"
            review.error_message = str(exc)
            db.commit()
        raise


def get_llm_review(db: Session, review_id: int) -> LLMReview | None:
    return db.get(LLMReview, review_id)
