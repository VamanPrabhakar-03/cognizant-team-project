"""Review Service Module.

Manages human reviewer decision audit logging and statistics.
"""

import math
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from schemas.review import ReviewCreateRequest
from database.models import Suspect, ReviewDecision

ALLOWED_DECISIONS = {"SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_EVIDENCE"}


def create_review_decision(
    db: Session,
    payload: ReviewCreateRequest,
) -> Optional[ReviewDecision]:
    decision_upper = payload.decision.upper().strip()
    if decision_upper not in ALLOWED_DECISIONS:
        raise ValueError(f"Invalid decision '{payload.decision}'. Must be one of {ALLOWED_DECISIONS}")
    
    suspect = db.query(Suspect).filter(Suspect.suspect_id == payload.suspect_id).first()
    if not suspect:
        raise ValueError(f"Suspect record '{payload.suspect_id}' not found.")
    
    review = ReviewDecision(
        suspect_id=suspect.suspect_id,
        bene_id=suspect.bene_id,
        hcc_v28=str(suspect.hcc_v28),
        suspect_type=suspect.suspect_type,
        priority_score=suspect.priority_score,
        decision=decision_upper,
        notes=payload.notes,
        reviewer_timestamp=datetime.now(),
    )
    
    suspect.status = "REVIEWED"
    
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_reviews(
    db: Session,
    suspect_id: Optional[str] = None,
    bene_id: Optional[str] = None,
    decision: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> Dict:
    query = db.query(ReviewDecision)
    
    if suspect_id:
        query = query.filter(ReviewDecision.suspect_id == suspect_id.strip())
    
    if bene_id:
        query = query.filter(ReviewDecision.bene_id == bene_id.strip())
    
    if decision:
        query = query.filter(ReviewDecision.decision == decision.upper().strip())
    
    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    items = query.order_by(ReviewDecision.reviewer_timestamp.desc()).offset(offset).limit(size).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }



def get_review_stats(db: Session) -> Dict:
    supported = db.query(func.count(ReviewDecision.id)).filter(ReviewDecision.decision == 'SUPPORTED').scalar() or 0
    not_supported = db.query(func.count(ReviewDecision.id)).filter(ReviewDecision.decision == 'NOT_SUPPORTED').scalar() or 0
    insufficient = db.query(func.count(ReviewDecision.id)).filter(ReviewDecision.decision == 'INSUFFICIENT_EVIDENCE').scalar() or 0
    
    return {
        "supported": supported,
        "not_supported": not_supported,
        "insufficient": insufficient,
    }
