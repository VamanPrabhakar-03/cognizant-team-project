"""Persist the frozen suspect-engine output into the review data model."""

import json
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    LLMReview,
    Member,
    PipelineRun,
    Suspect,
    SuspectEvidence,
)


def _collection(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return [item.strip() for item in value.split("|") if item.strip()]
    return []


def _number(row: Mapping[str, Any], field: str, default: float = 0.0) -> float:
    try:
        value = row.get(field, default)
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def _integer(row: Mapping[str, Any], field: str, default: int = 0) -> int:
    return int(_number(row, field, default))


def _date_value(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _suspect_id(row: Mapping[str, Any]) -> str:
    existing = str(row.get("suspect_id") or "").strip()
    if existing:
        return existing
    bene_id = str(row.get("bene_id") or "").strip()
    hcc = str(row.get("hcc_v28") or "").strip()
    gap_type = str(row.get("gap_type") or row.get("suspect_type") or "UNKNOWN").strip().upper()
    return f"SUS-{bene_id}-{hcc}-{gap_type}"


def _llm_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("bene_id") or "").strip(),
        str(row.get("hcc_v28") or "").strip(),
        str(row.get("gap_type") or row.get("suspect_type") or "").strip().upper(),
    )


def persist_engine_candidates(
    db: Session,
    run_id: str,
    candidates: Iterable[Mapping[str, Any]],
    llm_candidates: Optional[Iterable[Mapping[str, Any]]] = None,
) -> dict[str, int]:
    """Upsert engine candidates and append run-specific evidence/LLM records.

    Existing suspect review status is preserved. Evidence and LLM inputs are
    append-only by run, which keeps prior processing history auditable.
    """

    run = db.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"Pipeline run not found: {run_id}")

    llm_by_key = {_llm_key(row): row for row in (llm_candidates or [])}
    counts = {"suspects": 0, "evidence": 0, "llm_reviews": 0}

    try:
        for row in candidates:
            bene_id = str(row.get("bene_id") or "").strip()
            if not bene_id or db.get(Member, bene_id) is None:
                raise ValueError(f"Engine output references unknown bene_id: {bene_id}")

            suspect_id = _suspect_id(row)
            suspect_type = str(row.get("suspect_type") or row.get("gap_type") or "").strip().upper() or None
            diagnosis_codes = _collection(row.get("supporting_diagnosis_codes"))
            claim_ids = _collection(row.get("supporting_claim_ids"))
            reason_flags = _collection(row.get("reason_flags"))
            evidence_references = _collection(row.get("evidence_references"))
            prescription_codes = _collection(row.get("prescription_drug_codes"))

            suspect = db.get(Suspect, suspect_id)
            if suspect is None:
                suspect = Suspect(
                    suspect_id=suspect_id,
                    bene_id=bene_id,
                    status=str(row.get("status") or "PENDING_REVIEW"),
                )
                db.add(suspect)

            # Do not reset an existing reviewer decision when a later run updates
            # the same member/HCC candidate.
            suspect.bene_id = bene_id
            suspect.hcc_v28 = str(row.get("hcc_v28")) if row.get("hcc_v28") is not None else None
            suspect.suspect_type = suspect_type
            suspect.gap_type = str(row.get("gap_type") or suspect_type) if (row.get("gap_type") or suspect_type) else None
            suspect.latest_context = row.get("latest_context")
            suspect.priority = row.get("priority")
            suspect.priority_level = row.get("priority_level") or row.get("priority")
            suspect.supporting_diagnosis_codes = "|".join(map(str, diagnosis_codes)) or None
            suspect.supporting_claim_ids = "|".join(map(str, claim_ids)) or None
            suspect.evidence_count = _integer(row, "diagnosis_count", len(evidence_references))
            suspect.first_evidence_date = _date_value(row.get("first_evidence_date"))
            suspect.last_evidence_date = _date_value(row.get("last_evidence_date"))
            sources = sorted({str(ref.get("source")) for ref in evidence_references if isinstance(ref, dict) and ref.get("source")})
            suspect.sources = "|".join(sources) or None
            suspect.has_prescription_support = _integer(row, "prescription_support_count") > 0
            suspect.recency_score = _number(row, "recency_score")
            suspect.frequency_score = _number(row, "frequency_score")
            suspect.persistence_score = _number(row, "persistence_score")
            suspect.diversity_score = _number(row, "source_diversity_score")
            suspect.priority_score = _number(row, "priority_score")
            suspect.pipeline_run_id = run_id
            suspect.diagnosis_count = _integer(row, "diagnosis_count")
            suspect.unique_claim_count = _integer(row, "unique_claim_count")
            suspect.unique_event_count = _integer(row, "unique_event_count")
            suspect.distinct_evidence_dates = _integer(row, "distinct_evidence_dates")
            suspect.distinct_evidence_months = _integer(row, "distinct_evidence_months")
            suspect.distinct_sources = _integer(row, "distinct_sources")
            suspect.principal_diagnosis_count = _integer(row, "principal_diagnosis_count")
            suspect.prescription_support_count = _integer(row, "prescription_support_count")
            suspect.prescription_drug_codes = prescription_codes
            suspect.repeated_claim_score = _number(row, "repeated_claim_score")
            suspect.repeated_date_score = _number(row, "repeated_date_score")
            suspect.source_diversity_score = _number(row, "source_diversity_score")
            suspect.principal_score = _number(row, "principal_score")
            suspect.prescription_score = _number(row, "prescription_score")
            suspect.reason_flags = reason_flags
            suspect.evidence_summary = row.get("evidence_summary")
            suspect.evidence_references = evidence_references
            counts["suspects"] += 1

            for reference in evidence_references:
                if not isinstance(reference, dict):
                    continue
                evidence_date = reference.get("date")
                if isinstance(evidence_date, str):
                    evidence_date = datetime.strptime(evidence_date[:10], "%Y-%m-%d").date()
                db.add(
                    SuspectEvidence(
                        suspect_id=suspect_id,
                        pipeline_run_id=run_id,
                        bene_id=bene_id,
                        evidence_type="DIAGNOSIS",
                        evidence_date=evidence_date,
                        diagnosis_code=reference.get("diagnosis_code"),
                        claim_id=reference.get("claim_id"),
                        source=reference.get("source"),
                        evidence_text=row.get("evidence_summary"),
                        evidence_strength=_number(row, "priority_score"),
                        evidence_metadata=reference,
                    )
                )
                counts["evidence"] += 1

            llm_row = llm_by_key.get(_llm_key(row))
            if llm_row is not None:
                db.add(
                    LLMReview(
                        suspect_id=suspect_id,
                        pipeline_run_id=run_id,
                        status="PENDING",
                        prompt_version="1.0",
                        input_payload=dict(llm_row),
                    )
                )
                counts["llm_reviews"] += 1

        run.suspects_created = counts["suspects"]
        run.evidence_created = counts["evidence"]
        run.llm_reviews_created = counts["llm_reviews"]
        db.commit()
        return counts
    except Exception:
        db.rollback()
        raise
