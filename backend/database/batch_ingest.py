"""Incremental claims-batch ingestion.

This module deliberately does not truncate or replace existing tables. It records
one pipeline run and one claim batch, validates each incoming claim row, and
persists accepted rows with batch provenance.
"""

import csv
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Claim, ClaimBatch, IngestionRejection, Member, PipelineRun


CHUNK_SIZE = 5_000


def _parse_date(value: object) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "NAN"}:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid claim date: {text}") from exc


def _parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1", "y"}


def _new_run_id() -> str:
    return f"RUN-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"


def _new_batch_id() -> str:
    return f"BATCH-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"


def _reject(
    db: Session,
    source_file: str,
    row_index: int,
    row: Dict[str, object],
    reason: str,
) -> None:
    db.add(
        IngestionRejection(
            source_file=source_file,
            row_index=row_index,
            raw_data=str(row),
            reason=reason,
            created_at=datetime.utcnow(),
        )
    )


def ingest_claim_rows(
    db: Session,
    rows: Iterable[Dict[str, object]],
    *,
    source_file: Optional[str] = None,
    batch_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source_system: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, object]:
    """Ingest a new claims batch without replacing existing data.

    The input uses the stable fields ``bene_id`` and ``claim_id``. Date values
    may be supplied as ``claim_date`` or ``event_date``. Duplicate claim IDs
    within the same batch are rejected; an existing batch ID is rejected rather
    than appended to, making retries explicit and safe.
    """

    source_name = source_file or "claims_batch"
    effective_batch_id = batch_id or _new_batch_id()
    effective_run_id = run_id or _new_run_id()
    now = datetime.utcnow()

    if db.get(PipelineRun, effective_run_id) is not None:
        raise ValueError(f"Pipeline run already exists: {effective_run_id}")
    if db.get(ClaimBatch, effective_batch_id) is not None:
        raise ValueError(f"Claim batch already exists: {effective_batch_id}")

    run = PipelineRun(
        run_id=effective_run_id,
        batch_id=effective_batch_id,
        source_file=source_name,
        status="RUNNING",
        started_at=now,
        created_by=created_by,
    )
    batch = ClaimBatch(
        batch_id=effective_batch_id,
        pipeline_run_id=effective_run_id,
        source_file=source_name,
        source_system=source_system,
        received_at=now,
        status="RECEIVED",
    )
    db.add_all([run, batch])
    db.flush()
    # Persist the run header first so a later failure can be recorded as FAILED
    # without losing the audit record during rollback.
    db.commit()

    summary = {
        "run_id": effective_run_id,
        "batch_id": effective_batch_id,
        "status": "COMPLETED",
        "input_rows": 0,
        "valid_rows": 0,
        "inserted_rows": 0,
        "rejected_rows": 0,
    }
    seen_claim_ids: set[str] = set()
    pending: list[dict] = []

    try:
        for row_index, row in enumerate(rows, 1):
            summary["input_rows"] += 1
            bene_id = str(row.get("bene_id") or "").strip()
            claim_id = str(row.get("claim_id") or "").strip() or None

            if not bene_id:
                _reject(db, source_name, row_index, row, "Missing bene_id")
                summary["rejected_rows"] += 1
                continue

            if claim_id and claim_id in seen_claim_ids:
                _reject(db, source_name, row_index, row, f"Duplicate claim_id in batch: {claim_id}")
                summary["rejected_rows"] += 1
                continue
            if claim_id:
                seen_claim_ids.add(claim_id)

            try:
                claim_date = _parse_date(row.get("claim_date") or row.get("event_date"))
            except ValueError as exc:
                _reject(db, source_name, row_index, row, str(exc))
                summary["rejected_rows"] += 1
                continue

            pending.append(
                {
                    "batch_id": effective_batch_id,
                    "claim_id": claim_id,
                    "bene_id": bene_id,
                    "claim_date": claim_date,
                    "diagnosis_code": str(row.get("diagnosis_code") or "").strip() or None,
                    "source": str(row.get("source") or "").strip() or None,
                    "is_principal": _parse_bool(row.get("is_principal")),
                    "raw_payload": dict(row),
                }
            )
            summary["valid_rows"] += 1

            if len(pending) >= CHUNK_SIZE:
                _insert_chunk(db, pending, source_name, row_index, summary)
                pending = []

        if pending:
            _insert_chunk(db, pending, source_name, summary["input_rows"], summary)

        run.status = "COMPLETED"
        run.completed_at = datetime.utcnow()
        run.input_rows = summary["input_rows"]
        run.valid_rows = summary["valid_rows"]
        run.rejected_rows = summary["rejected_rows"]
        run.claims_processed = summary["inserted_rows"]
        batch.row_count = summary["inserted_rows"]
        batch.status = "PROCESSED"
        db.commit()
        return summary
    except Exception as exc:
        db.rollback()
        failed_run = db.get(PipelineRun, effective_run_id)
        failed_batch = db.get(ClaimBatch, effective_batch_id)
        if failed_run is not None:
            failed_run.status = "FAILED"
            failed_run.completed_at = datetime.utcnow()
            failed_run.error_message = str(exc)
            failed_run.input_rows = summary["input_rows"]
            failed_run.valid_rows = summary["valid_rows"]
            failed_run.rejected_rows = summary["rejected_rows"]
        if failed_batch is not None:
            failed_batch.status = "FAILED"
        db.commit()
        raise


def _insert_chunk(
    db: Session,
    rows: list[dict],
    source_file: str,
    row_index: int,
    summary: Dict[str, object],
) -> None:
    bene_ids = {row["bene_id"] for row in rows}
    known_members = set(
        db.scalars(select(Member.bene_id).where(Member.bene_id.in_(bene_ids))).all()
    )
    accepted = []
    for row in rows:
        if row["bene_id"] not in known_members:
            _reject(
                db,
                source_file,
                row_index,
                row,
                f"Unknown bene_id: {row['bene_id']}",
            )
            summary["rejected_rows"] += 1
            summary["valid_rows"] -= 1
            continue
        accepted.append(row)

    if accepted:
        db.bulk_insert_mappings(Claim, accepted)
        summary["inserted_rows"] += len(accepted)


def ingest_claim_csv(
    db: Session,
    csv_path: str | Path,
    **kwargs: object,
) -> Dict[str, object]:
    """Stream a CSV file into :func:`ingest_claim_rows`."""

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return ingest_claim_rows(
            db,
            csv.DictReader(handle),
            source_file=kwargs.pop("source_file", path.name),
            **kwargs,
        )
