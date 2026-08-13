"""Members Router Module."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.schemas.member import (
    MemberListResponse,
    MemberDetailResponse,
    TimelineResponse,
)
from src.api.services.member_service import (
    get_members,
    get_member_detail,
    get_member_timeline,
)

router = APIRouter(prefix="/members", tags=["Members"])


@router.get("", response_model=MemberListResponse)
def get_members_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for bene_id or state"),
    has_suspects: Optional[bool] = Query(None, description="Filter members with/without suspects"),
    db: Session = Depends(get_db),
):
    return get_members(db, page=page, size=size, search=search, has_suspects=has_suspects)


@router.get("/{bene_id}", response_model=MemberDetailResponse)
def get_member_detail_endpoint(bene_id: str, db: Session = Depends(get_db)):
    result = get_member_detail(db, bene_id=bene_id.strip())
    if not result:
        raise HTTPException(status_code=404, detail=f"Member with ID '{bene_id}' not found")
    return result


@router.get("/{bene_id}/timeline", response_model=TimelineResponse)
def get_member_timeline_endpoint(
    bene_id: str,
    year: Optional[str] = Query(None, description="Filter timeline events by year"),
    source: Optional[str] = Query(None, description="Filter by claim source"),
    hcc_only: bool = Query(False, description="Only include events mapped to an HCC"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    result = get_member_timeline(
        db=db, bene_id=bene_id.strip(), year=year, source=source, hcc_only=hcc_only, page=page, size=size
    )
    return result
