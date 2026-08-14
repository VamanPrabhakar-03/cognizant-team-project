"""Suspects Router Module."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dependencies import get_db
from schemas.suspect import (
    SuspectSchema,
    SuspectListResponse,
    SuspectDetailResponse,
    SuspectStatusUpdate,
)
from services.suspect_service import (
    get_suspects,
    get_suspect_detail,
    update_suspect_status,
)

router = APIRouter(prefix="/suspects", tags=["Suspects / Review Queny"])


@router.get("", response_model=SuspectListResponse)
def get_suspects_endpoint(
    type: Optional[str] = Query(None, description="Filter by suspect type (EMERGING or RECAPTURE)"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum priority score"),
    hcc: Optional[str] = Query(None, description="Filter by HCC category"),
    status: Optional[str] = Query(None, description="Filter by review status (e.g. PENDING_REVIEW)"),
    sort: str = Query("priority_score", description="Sort field (priority_score, etc.)"),
    order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    result = get_suspects(
        db=db, type=type, min_score=min_score, hcc=hcc, status=status, sort=sort, order=order, page=page, size=size
    )
    return result


@router.get("/{suspect_id}", response_model=SuspectDetailResponse)
def get_suspect_detail_endpoint(
    suspect_id: str, db: Session = Depends(get_db)
):
    result = get_suspect_detail(db, suspect_id=suspect_id.strip())
    if not result:
        raise HTTPException(status_code=404, detail=f"Suspect with ID '{suspect_id}' not found")
    return result


@router.patch("/{suspect_id}", response_model=SuspectSchema)
def update_suspect_status_endpoint(
    suspect_id: str,
    payload: SuspectStatusUpdate,
    db: Session = Depends(get_db),
):
    updated = update_suspect_status(db, suspect_id=suspect_id.strip(), status=payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Suspect with ID '{suspect_id}' not found")
    return updated
