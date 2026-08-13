"""Member Service Module.

Provides database query operations for Member demographics, details, and timeline events.
"""

import math
from typing import Dict, List, Optional
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session
from src.database.models import (
    Member,
    MemberHCCBaseline,
    MemberTimeline,
    Suspect,
)


def get_members(
    db: Session,
    page: int = 1,
    size: int = 20,
    search: Optional[str] = None,
    has_suspects: Optional[bool] = None,
) -> Dict:
    query = db.query(Member)

    if search:
        term = "%" + search.strip() + "%"
        query = query.filter(
            or_(Member.bene_id.ilike(term), Member.state.ilike(term))
        )

    if has_suspects is True:
        suspect_bene_ids = db.query(Suspect.bene_id).distinct()
        query = query.filter(Member.bene_id.in_(suspect_bene_ids))
    elif has_suspects is False:
        suspect_bene_ids = db.query(Suspect.bene_id).distinct()
        query = query.filter(~Member.bene_id.in_(suspect_bene_ids))

    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    items = query.order_by(Member.bene_id).offset(offset).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }



def get_member_detail(db: Session, bene_id: str) -> Optional[Dict]:
    member = db.query(Member).filter(Member.bene_id == bene_id).first()
    if not member:
        return None

    baseline_hccs = (
        db.query(MemberHCCBaseline)
        .filter(MemberHCCBaseline.bene_id == bene_id)
        .order_by(MemberHCCBaseline.hcc_v28)
        .all()
    )
    suspects = (
        db.query(Suspect)
        .filter(Suspect.bene_id == bene_id)
        .order_by(Suspect.priority_score.desc())
        .all()
    )

    total_claims = (
        db.query(func.count(MemberTimeline.id))
        .filter(
            MemberTimeline.bene_id == bene_id,
            MemberTimeline.claim_id.isnot(None),
        )
        .scalar()
        or 0
    )
    total_diagnoses = (
        db.query(func.count(MemberTimeline.id))
        .filter(
            MemberTimeline.bene_id == bene_id,
            MemberTimeline.event_type == "DIAGNOSIS",
        )
        .scalar()
        or 0
    )

    baseline_count = len(baseline_hccs)
    suspect_count = len(suspects)
    pending_count = sum(1 for s in suspects if s.status == "PENDING_REVIEW")

    return {
        "member": member,
        "baseline_hccs": baseline_hccs,
        "suspects": suspects,
        "stats": {
            "total_claims": total_claims,
            "total_diagnoses": total_diagnoses,
            "baseline_hcc_count": baseline_count,
            "suspect_hcc_count": suspect_count,
            "pending_review_count": pending_count,
        },
    }



def get_member_timeline(
    db: Session,
    bene_id: str,
    year: Optional[str] = None,
    source: Optional[str] = None,
    hcc_only: bool = False,
    page: int = 1,
    size: int = 20,
) -> Dict:
    query = db.query(MemberTimeline).filter(MemberTimeline.bene_id == bene_id)

    if year:
        pattern = year.strip() + "%"
        query = query.filter(
            cast(MemberTimeline.event_date, String).like(pattern)
        )

    if source:
        query = query.filter(MemberTimeline.source == source.strip())

    if hcc_only:
        query = query.filter(
            MemberTimeline.hcc_v28 != "", MemberTimeline.hcc_v28.isnot(None)
        )

    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    items = (
        query.order_by(
            MemberTimeline.event_date.desc(), MemberTimeline.event_type
        )
        .offset(offset)
        .limit(size)
        .all()
    )

    return{
        "bene_id": bene_id,
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }
