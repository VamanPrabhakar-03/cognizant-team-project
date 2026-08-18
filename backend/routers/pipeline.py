"""Incremental claims pipeline endpoints."""

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
# pyrefly: ignore [missing-import]
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.batch_ingest import ingest_claim_rows
from database.models import Member, PipelineRun, PrescriptionEvent
from dependencies import get_db
from services.claims_preprocessor import preprocess_claims_zip
from services.engine_service import run_suspect_engine_for_run
from schemas.pipeline import (
    BatchIngestionResponse,
    ClaimBatchCreateRequest,
    PipelineRunSchema,
    ZipUploadResponse,
)


router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# ── Helper: Insert PDE rows with conflict handling ────────────────────────────

def _insert_pde_rows(db: Session, pde_rows: list[dict]) -> int:
    """Insert Part D prescription events, skipping any that already exist."""
    if not pde_rows:
        return 0

    # Validate bene_ids against members table (FK constraint)
    bene_ids = {row["bene_id"] for row in pde_rows}
    known = set(
        db.scalars(select(Member.bene_id).where(Member.bene_id.in_(bene_ids))).all()
    )
    valid_rows = [r for r in pde_rows if r["bene_id"] in known]
    if not valid_rows:
        return 0

    # Convert event_date strings to Python date objects
    prepared = []
    for row in valid_rows:
        event_date = None
        raw = row.get("event_date")
        if raw:
            try:
                event_date = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        prepared.append({
            "event_id":   row.get("event_id") or f"PDE_AUTO_{uuid.uuid4().hex[:12]}",
            "bene_id":    row["bene_id"],
            "pde_id":     row.get("pde_id"),
            "event_date": event_date,
            "drug_code":  row.get("drug_code"),
        })

    stmt = pg_insert(PrescriptionEvent).values(prepared).on_conflict_do_nothing(
        index_elements=["event_id"]
    )
    db.execute(stmt)
    db.commit()
    return len(prepared)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=ZipUploadResponse,
    status_code=201,
    summary="Upload raw CMS claims ZIP",
    description=(
        "Accept a ZIP archive containing raw pipe-delimited CMS claims files "
        "(inpatient.csv, outpatient.csv, carrier.csv, and optionally pde.csv). "
        "Preprocesses wide ICD columns into individual diagnosis rows, ingests "
        "them, then runs the full pipeline: suspect engine → ML priority scoring "
        "→ LLM clinical summary → reviewer queue."
    ),
)
async def upload_claims_zip_endpoint(
    file: UploadFile = File(
        ...,
        description="ZIP file containing CMS pipe-delimited claims CSVs",
    ),
    source_system: Optional[str] = Form(None, description="e.g. CMS_DE_SynPUF"),
    created_by:    Optional[str] = Form(None, description="Uploader name / system ID"),
    db: Session = Depends(get_db),
):
    """Upload a ZIP of raw CMS claims files and run the full HCC detection pipeline."""

    # ── 1. Read uploaded bytes ────────────────────────────────────────────────
    zip_bytes = await file.read()
    if not zip_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── 2. Preprocess: extract & normalize all claim files inside the ZIP ─────
    try:
        claim_rows, pde_rows, preprocessing_stats = preprocess_claims_zip(zip_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not claim_rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid diagnosis rows extracted from the ZIP. "
                "Ensure the CSV files are pipe-delimited and contain BENE_ID + "
                "at least one of PRNCPAL_DGNS_CD or ICD_DGNS_CD1."
            ),
        )

    # ── 3. Ingest normalized claim rows (creates PipelineRun + ClaimBatch) ────
    try:
        ingestion_result = ingest_claim_rows(
            db,
            claim_rows,
            source_file=file.filename or "claims_upload.zip",
            source_system=source_system,
            created_by=created_by,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    run_id = ingestion_result["run_id"]

    # ── 4. Insert Part D prescription events (optional, skip duplicates) ──────
    pde_inserted = 0
    if pde_rows:
        try:
            pde_inserted = _insert_pde_rows(db, pde_rows)
        except Exception:
            # PDE is supplementary; don't fail the whole pipeline on Rx errors
            pde_inserted = 0

    # ── 5. Run suspect engine → ML priority scoring → LLM summaries ──────────
    try:
        engine_result = run_suspect_engine_for_run(db, run_id)
    except Exception as exc:
        db.rollback()
        failed_run = db.get(PipelineRun, run_id)
        if failed_run is not None:
            failed_run.status = "FAILED"
            failed_run.completed_at = datetime.utcnow()
            failed_run.error_message = str(exc)
            db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline engine failed: {exc}",
        ) from exc

    return {
        **ingestion_result,
        **engine_result,
        "preprocessing_stats": preprocessing_stats,
        "pde_inserted": pde_inserted,
    }


@router.post("/batches", response_model=BatchIngestionResponse, status_code=201)
def ingest_claim_batch_endpoint(
    payload: ClaimBatchCreateRequest,
    db: Session = Depends(get_db),
):
    """Accept one validated JSON claims batch without replacing existing data."""

    rows = []
    for claim in payload.claims:
        row = claim.model_dump(exclude={"extra"})
        row.update(claim.extra)
        rows.append(row)

    try:
        ingestion_result = ingest_claim_rows(
            db,
            rows,
            source_file=payload.source_file,
            batch_id=payload.batch_id,
            run_id=payload.run_id,
            source_system=payload.source_system,
            created_by=payload.created_by,
        )
        try:
            engine_result = run_suspect_engine_for_run(db, ingestion_result["run_id"])
        except Exception as exc:
            db.rollback()
            failed_run = db.get(PipelineRun, ingestion_result["run_id"])
            if failed_run is not None:
                failed_run.status = "FAILED"
                failed_run.completed_at = datetime.utcnow()
                failed_run.error_message = str(exc)
                db.commit()
            raise HTTPException(status_code=500, detail="Suspect engine execution failed") from exc
        return {**ingestion_result, **engine_result}
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/reset",
    status_code=200,
    summary="Reset Pipeline Test Data",
    description="Wipes only pipeline-generated records (suspects, reviews, claims, pipeline_runs) while preserving historical foundation data.",
)
def reset_pipeline_endpoint(db: Session = Depends(get_db)):
    """Reset pipeline-generated tables for testing."""
    from database.models import Claim, ClaimBatch, LLMReview, PipelineRun, ReviewDecision, Suspect, SuspectEvidence

    # Delete in FK-safe order
    db.query(ReviewDecision).delete(synchronize_session=False)
    db.query(LLMReview).delete(synchronize_session=False)
    db.query(SuspectEvidence).delete(synchronize_session=False)
    db.query(Suspect).delete(synchronize_session=False)
    db.query(Claim).delete(synchronize_session=False)
    db.query(ClaimBatch).delete(synchronize_session=False)
    db.query(PipelineRun).delete(synchronize_session=False)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": "All pipeline test records (suspects, reviews, claims, runs) cleared. Database ready for new upload.",
    }


@router.get("/runs/{run_id}", response_model=PipelineRunSchema)

def get_pipeline_run_endpoint(run_id: str, db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id.strip())
    if run is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run

