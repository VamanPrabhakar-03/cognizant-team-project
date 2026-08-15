"""Incremental claims pipeline endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.batch_ingest import ingest_claim_rows
from database.models import PipelineRun
from dependencies import get_db
from services.engine_service import run_suspect_engine_for_run
from schemas.pipeline import (
    BatchIngestionResponse,
    ClaimBatchCreateRequest,
    PipelineRunSchema,
)


router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


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


@router.get("/runs/{run_id}", response_model=PipelineRunSchema)
def get_pipeline_run_endpoint(run_id: str, db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id.strip())
    if run is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return run
