"""Health Router Module."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.api.dependencies import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error ({str(e)})"
    
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "service": "Medicare Advantage Risk Adjustment API",
    }
