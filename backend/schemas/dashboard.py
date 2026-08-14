"""Dashboard Schemas."""

from typing import List, Optional
from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_members: int
    members_with_baseline: int
    total_suspects: int
    emerging_count: int
    recapture_count: int
    high_priority_count: int
    reviewed_count: int
    pending_count: int


class HCCDistributionItem(BaseModel):
    hcc_v28: str
    description: str
    emerging_count: int
    recapture_count: int


class ScoreDistribution(BaseModel):
    high: int  # priority_score >= 0.75
    medium: int  # 0.50 <= priority_score < 0.75
    low: int  # priority_score < 0.50
