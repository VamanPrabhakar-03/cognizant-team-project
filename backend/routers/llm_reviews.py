"""Endpoints for generating and retrieving human-review LLM summaries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import get_db
from schemas.llm_review import LLMReviewSchema
from services.llm_review_service import generate_llm_review, get_llm_review


router = APIRouter(prefix="/llm-reviews", tags=["LLM Reviews"])


@router.get("/{review_id}", response_model=LLMReviewSchema)
def get_llm_review_endpoint(review_id: int, db: Session = Depends(get_db)):
    review = get_llm_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"LLM review '{review_id}' not found")
    return review


@router.post("/{review_id}/generate", response_model=LLMReviewSchema)
def generate_llm_review_endpoint(review_id: int, db: Session = Depends(get_db)):
    try:
        return generate_llm_review(db, review_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="LLM review generation failed") from exc
