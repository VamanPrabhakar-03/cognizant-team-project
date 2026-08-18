"""Database-backed execution of the frozen HCC suspect algorithm."""

import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Claim,
    HCCMapping,
    MemberHCCBaseline,
    MemberTimeline,
    PipelineRun,
    PrescriptionEvent,
)
from services.suspect_persistence import persist_engine_candidates
from services.ml_priority_service import score_candidates
from services.llm_service import generate_candidate_summaries


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from suspect_engine.suspect_engine import (  # noqa: E402
    build_hcc_sets,
    build_llm_record,
    detect_gaps,
    evidence_summary,
    latest_context,
    prescription_support,
    reason_flags,
    score_features,
)


def assign_priority(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


def _timeline_frame(rows: list[MemberTimeline], claims: list[Claim], hcc_by_code: dict[str, str]) -> pd.DataFrame:
    records = []
    for event in rows:
        records.append(
            {
                "bene_id": event.bene_id,
                "event_date": event.event_date,
                "event_type": str(event.event_type or "").lower(),
                "code": event.code,
                "hcc_v28": event.hcc_v28,
                "source": event.source,
                "claim_id": event.claim_id,
                "event_id": event.event_id,
                "is_principal": bool(event.is_principal),
            }
        )
    for claim in claims:
        records.append(
            {
                "bene_id": claim.bene_id,
                "event_date": claim.claim_date,
                "event_type": "diagnosis",
                "code": claim.diagnosis_code,
                "hcc_v28": hcc_by_code.get(str(claim.diagnosis_code or "").strip()),
                "source": claim.source,
                "claim_id": claim.claim_id,
                "event_id": f"{claim.batch_id}:{claim.claim_id or claim.id}",
                "is_principal": bool(claim.is_principal),
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        return pd.DataFrame(columns=[
            "bene_id", "event_date", "event_type", "code", "hcc_v28",
            "source", "claim_id", "event_id", "is_principal",
        ])
    frame["bene_id"] = frame["bene_id"].astype("string").str.strip()
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce")
    frame["event_type"] = frame["event_type"].astype("string").str.lower()
    frame["hcc_v28"] = pd.to_numeric(frame["hcc_v28"], errors="coerce")
    frame["source"] = frame["source"].astype("string").str.upper()
    frame["is_principal"] = frame["is_principal"].fillna(False).astype(bool)
    frame = frame[
        (frame["event_type"] == "diagnosis")
        & frame["event_date"].notna()
        & frame["hcc_v28"].notna()
    ].copy()
    if not frame.empty:
        frame["hcc_v28"] = frame["hcc_v28"].astype(int)
    return frame


def _prescription_frame(rows: list[PrescriptionEvent]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bene_id": row.bene_id,
                "event_id": row.event_id,
                "event_date": row.event_date,
                "drug_code": row.drug_code,
            }
            for row in rows
        ],
        columns=["bene_id", "event_id", "event_date", "drug_code"],
    ).assign(event_date=lambda frame: pd.to_datetime(frame["event_date"], errors="coerce"))


def run_suspect_engine_for_run(
    db: Session,
    run_id: str,
    *,
    current_year: Optional[int] = None,
) -> dict[str, int | str]:
    """Run the frozen algorithm over database history and one claims batch."""

    run = db.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"Pipeline run not found: {run_id}")
    if not run.batch_id:
        raise ValueError(f"Pipeline run has no claim batch: {run_id}")

    claims = list(db.scalars(select(Claim).where(Claim.batch_id == run.batch_id)).all())
    if not claims:
        raise ValueError(f"Claim batch contains no claims: {run.batch_id}")

    member_ids = {claim.bene_id for claim in claims}
    baseline_rows = list(
        db.scalars(select(MemberHCCBaseline).where(MemberHCCBaseline.bene_id.in_(member_ids))).all()
    )
    baseline_hccs = {
        bene_id: {int(row.hcc_v28) for row in rows if row.hcc_v28 is not None}
        for bene_id, rows in _group_by_bene(baseline_rows).items()
    }

    dates = [claim.claim_date for claim in claims if claim.claim_date is not None]
    if not dates:
        raise ValueError("Claim batch has no valid claim dates")
    selected_year = current_year or max(d.year for d in dates)
    historical_years = {selected_year - 2, selected_year - 1}
    reference_date = pd.Timestamp(date(selected_year, 12, 31))

    timeline_rows = list(
        db.scalars(select(MemberTimeline).where(MemberTimeline.bene_id.in_(member_ids))).all()
    )
    mapping_rows = list(db.scalars(select(HCCMapping)).all())
    hcc_by_code = {
        str(row.diagnosis_code).strip(): str(row.hcc_v28).strip()
        for row in mapping_rows
        if row.diagnosis_code and row.hcc_v28
    }
    timeline = _timeline_frame(timeline_rows, claims, hcc_by_code)
    timeline = timeline[timeline["event_date"].dt.year.isin(historical_years | {selected_year})].copy()

    current_events = timeline[timeline["event_date"].dt.year == selected_year]
    historical_events = timeline[timeline["event_date"].dt.year.isin(historical_years)]
    current_hccs = build_hcc_sets(current_events)
    latest_hccs = current_hccs
    historical_index = {(b, h): group for (b, h), group in historical_events.groupby(["bene_id", "hcc_v28"], sort=False)}
    current_index = {(b, h): group for (b, h), group in current_events.groupby(["bene_id", "hcc_v28"], sort=False)}
    prescriptions = _prescription_frame(list(db.scalars(select(PrescriptionEvent).where(PrescriptionEvent.bene_id.in_(member_ids))).all()))

    suspects = detect_gaps(baseline_hccs, current_hccs)
    empty_events = timeline.iloc[0:0]
    candidates = []
    llm_candidates = []
    for suspect in suspects:
        key = (suspect["bene_id"], suspect["hcc_v28"])
        events = current_index.get(key) if suspect["gap_type"] == "EMERGING" else historical_index.get(key)
        events = events if events is not None else empty_events
        rx = prescription_support(events, prescriptions)
        row = {**suspect, **score_features(events, rx, reference_date=reference_date)}
        recency = float(row.get("recency_score", 0.0) or 0.0)
        frequency = float(row.get("frequency_score", 0.0) or 0.0)
        persistence = float(row.get("persistence_score", 0.0) or 0.0)
        diversity = float(row.get("source_diversity_score", 0.0) or 0.0)
        priority_score = round(0.30 * recency + 0.25 * frequency + 0.20 * persistence + 0.25 * diversity, 3)
        row["priority_score"] = priority_score
        row["suspect_type"] = row["gap_type"]
        row["latest_context"] = latest_context(row["gap_type"], row["hcc_v28"], latest_hccs, row["bene_id"])
        row["priority"] = assign_priority(priority_score)
        row["priority_level"] = row["priority"]
        row["reason_flags"] = reason_flags(row)
        row["evidence_summary"] = evidence_summary(row)
        candidates.append(row)
        llm_candidates.append(build_llm_record(row))

    # ML ranks only deterministic candidates; it never creates or removes gaps.
    ml_scores = score_candidates(candidates)
    for row, ml_score in zip(candidates, ml_scores):
        row.update(ml_score)

    # LLM summarization with combined gap, evidence, and ML priority context
    llm_summaries = generate_candidate_summaries(candidates, llm_candidates)

    counts = persist_engine_candidates(db, run_id, candidates, llm_candidates, llm_summaries)
    return {"run_id": run_id, **counts}


def _group_by_bene(rows: list) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.bene_id, []).append(row)
    return grouped
