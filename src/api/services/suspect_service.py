"""Suspect Service Module.

Provides query and update operations for Suspect / Review Candidate
opportunities.
"""

import math
from typing import Dict, Optional, List
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.database.models import Member, MemberHCCBaseline, MemberTimeline, Suspect


def get_suspects(
    db: Session,
    type: Optional[str] = None,
    min_score: Optional[float] = None,
    hcc: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "priority_score",
    order: str = "desc",
    page: int = 1,
    size: int = 20,
) -> Dict:
    query = db.query(Suspect)

    if type:
        query = query.filter(Suspect.suspect_type == type.upper())

    if min_score is not None:
        query = query.filter(Suspect.priority_score >= min_score)

    if hcc:
        query = query.filter(Suspect.hcc_v28 == hcc.strip())

    if status:
        query = query.filter(Suspect.status == status.strip())

    sort_col = getattr(Suspect, sort, Suspect.priority_score)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    items = query.offset(offset).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }



def get_suspect_detail(db: Session, suspect_id: str) -> Optional[Dict]:
    suspect = db.query(Suspect).filter(Suspect.suspect_id == suspect_id).first()
    if not suspect:
        return None

    member = db.query(Member).filter(Member.bene_id == suspect.bene_id).first()
    baseline_hccs = db.query(MemberHCCBaseline).filter(MemberHCCBaseline.bene_id == suspect.bene_id).all()

    diag_codes = [c.strip() for c in suspect.supporting_diagnosis_codes.split("|")] if suspect.supporting_diagnosis_codes else []
    claim_ids = [c.strip() for c in suspect.supporting_claim_ids.split("|")] if suspect.supporting_claim_ids else []

    timeline_query = db.query(MemberTimeline).filter(MemberTimeline.bene_id == suspect.bene_id)
    filters = []
    if suspect.hcc_v28:
        filters.append(MemberTimeline.hcc_v28 == str(suspect.hcc_v28))
    if diag_codes:
        filters.append(MemberTimeline.code.in_(diag_codes))
    if claim_ids:
        filters.append(MemberTimeline.claim_id.in_(claim_ids))

    if filters:
        timeline_query = timeline_query.filter(or_(*filters))

    supporting_events = timeline_query.order_by(MemberTimeline.event_date.desc()).limit(50).all()

    return {
        "suspect": suspect,
        "member": member,
        "baseline_hccs": baseline_hccs,
        "supporting_events": supporting_events,
    }



def update_suspect_status(db: Session, suspect_id: str, status: str) -> Optional[Suspect]:
    suspect = db.query(Suspect).filter(Suspect.suspect_id == suspect_id).first()
    if not suspect:
        return None

    suspect.status = status
    db.commit()
    db.refresh(suspect)
    return suspect
