"""Dashboard Router Module."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.schemas.dashboard import (
    DashboardMetrics,
    HCCDistributionItem,
    ScoreDistribution,
)
from src.api.services.dashboard_service import (
    get_dashboard_metrics,
    get_hcc_distribution,
    get_score_distribution,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics_endpoint(db: Session = Depends(get_db)):
    return get_dashboard_metrics(db)


@router.get("/hcc-distribution", response_model=List[HCCDistributionItem])
def get_hcc_distribution_endpoint(db: Session = Depends(get_db)):
    return get_hcc_distribution(db)


@router.get("/score-distribution", response_model=ScoreDistribution)
def get_score_distribution_endpoint(db: Session = Depends(get_db)):
    return get_score_distribution(db)
