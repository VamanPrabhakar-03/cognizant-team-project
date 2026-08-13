"""Dashboard Service Module.

Provides database aggregation queries for the dashboard endpoints.
"""

from typing import Dict, List
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.api.schemas.dashboard import (
    DashboardMetrics,
    HCCDistributionItem,
    ScoreDistribution,
)
from src.database.models import Member, MemberHCCBaseline, Suspect


def get_dashboard_metrics(db: Session) -> DashboardMetrics:
    total_members = db.query(func.count(Member.bene_id)).scalar() or 0
    members_with_baseline = (
        db.query(func.count(func.distinct(MemberHCCBaseline.bene_id))).scalar() or 0
    )
    total_suspects = db.query(func.count(Suspect.suspect_id)).scalar() or 0
    emerging_count = (
        db.query(func.count(Suspect.suspect_id))
        .filter(func.upper(Suspect.suspect_type) == "EMERGING")
        .scalar()
        or 0
    )
    recapture_count = (
        db.query(func.count(Suspect.suspect_id))
        .filter(func.upper(Suspect.suspect_type) == "RECAPTURE")
        .scalar()
        or 0
    )
    high_priority_count = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.priority_score >= 0.75)
        .scalar()
        or 0
    )
    reviewed_count = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.status == "REVIEWED")
        .scalar()
        or 0
    )
    pending_count = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.status == "PENDING_REVIEW")
        .scalar()
        or 0
    )

    return DashboardMetrics(
        total_members=total_members,
        members_with_baseline=members_with_baseline,
        total_suspects=total_suspects,
        emerging_count=emerging_count,
        recapture_count=recapture_count,
        high_priority_count=high_priority_count,
        reviewed_count=reviewed_count,
        pending_count=pending_count,
    )


def get_hcc_distribution(db: Session) -> List[HCCDistributionItem]:
    query = db.query(
        Suspect.hcc_v28, Suspect.suspect_type, func.count(Suspect.suspect_id)
    ).group_by(Suspect.hcc_v28, Suspect.suspect_type)

    hcc_map: Dict[str, Dict[str, int]] = {}
    for hcc, stype, count in query.all():
        hcc_code = hcc or "UNKNOWN"
        if hcc_code not in hcc_map:
            hcc_map[hcc_code] = {"emerging": 0, "recapture": 0}
        if stype and stype.upper() == "EMERGING":
            hcc_map[hcc_code]["emerging"] += count
        elif stype and stype.upper() == "RECAPTURE":
            hcc_map[hcc_code]["recapture"] += count

    out: List[HCCDistributionItem] = []
    for hcc, counts in hcc_map.items():
        out.append(
            HCCDistributionItem(
                hcc_v28=hcc,
                description=f"HCC {hcc}",
                emerging_count=counts["emerging"],
                recapture_count=counts["recapture"],
            )
        )

    out.sort(key=lambda x: (x.emerging_count + x.recapture_count), reverse=True)
    return out


def get_score_distribution(db: Session) -> ScoreDistribution:
    high = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.priority_score >= 0.75)
        .scalar() or 0
    )
    medium = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.priority_score >= 0.50)
        .filter(Suspect.priority_score < 0.75)
        .scalar() or 0
    )
    low = (
        db.query(func.count(Suspect.suspect_id))
        .filter(Suspect.priority_score < 0.50)
        .scalar() or 0
    )
    return ScoreDistribution(high=high, medium=medium, low=low)
