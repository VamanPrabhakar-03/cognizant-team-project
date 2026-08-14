"""Reviews Router Module."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dependencies import get_db
from schemas.review import (
    ReviewCreateRequest,
    ReviewDecisionListResponse,
    ReviewDecisionSchema,
    ReviewStatsResponse,
)
from services.review_service import (
    create_review_decision,
    get_review_stats,
    get_reviews,
)

router = APIRouter(prefix="/reviews", tags=["Review Decisions"])


@router.post("", response_model=ReviewDecisionSchema, status_code=201)
def create_review_endpoint(
    payload: ReviewCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return create_review_decision(db, payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, description=str(ve))


@router.get("", response_model=ReviewDecisionListResponse)
def get_reviews_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    result = get_reviews(db, page=page, size=size)
    return result


@router.get("/stats", response_model=ReviewStatsResponse)
def get_review_stats_endpoint(db: Session = Depends(get_db)):
    return get_review_stats(db)
