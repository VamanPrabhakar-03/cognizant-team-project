"""Generate evidence-grounded, human-readable reviews from suspect JSON."""

import json
import os
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import LLMReview


PROMPT_VERSION = "hcc-human-review-v1"
DEFAULT_MODEL = "gpt-5.6"


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
    """Call the configured model and save its constrained review response."""
    review = db.get(LLMReview, review_id)
    if review is None:
        raise ValueError(f"LLM review '{review_id}' not found.")
    if not review.input_payload:
        raise ValueError(f"LLM review '{review_id}' has no input JSON payload.")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI

        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        response = OpenAI().responses.parse(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(review.input_payload)},
            ],
            text_format=HumanReviewOutput,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("The model returned no structured review output.")

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
