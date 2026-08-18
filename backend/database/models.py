"""
SQLAlchemy 2.x Declarative Models.

Modeled strictly after the prepared datasets in data/:
- data/members.csv                -> Member
- data/hcc_mapping.csv            -> HCCMapping
- data/events_diagnosis.csv       -> DiagnosisEvent
- data/events_prescription.csv    -> PrescriptionEvent
- data/member_timeline.csv        -> MemberTimeline
- data/member_hcc_baseline.csv    -> MemberHCCBaseline
- data/suspects.csv               -> Suspect
- data/review_decisions.csv       -> ReviewDecision
- Invalid/corrupt records log     -> IngestionRejection
"""

from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import (
    String, Integer, Boolean, Float, Date, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Member(Base):
    """
    Beneficiary Registry Table.
    Source: data/members.csv
    """
    __tablename__ = "members"

    bene_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    race: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    county: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    esrd_indicator: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    death_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    enrollment_years: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    diagnosis_events: Mapped[List["DiagnosisEvent"]] = relationship("DiagnosisEvent", back_populates="member")
    prescription_events: Mapped[List["PrescriptionEvent"]] = relationship("PrescriptionEvent", back_populates="member")
    timeline_events: Mapped[List["MemberTimeline"]] = relationship("MemberTimeline", back_populates="member")
    baselines: Mapped[List["MemberHCCBaseline"]] = relationship("MemberHCCBaseline", back_populates="member")
    suspects: Mapped[List["Suspect"]] = relationship("Suspect", back_populates="member")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="member")
    suspect_evidence: Mapped[List["SuspectEvidence"]] = relationship("SuspectEvidence", back_populates="member")


class HCCMapping(Base):
    """
    CMS-HCC V28 Reference Mapping Crosswalk.
    Source: data/hcc_mapping.csv
    """
    __tablename__ = "hcc_mappings"

    diagnosis_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hcc_v28: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    payment_2026: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_hcc_mapping_code_hcc", "diagnosis_code", "hcc_v28"),
    )


class DiagnosisEvent(Base):
    """
    Normalized Medical Claims Diagnosis Events.
    Source: data/events_diagnosis.csv
    """
    __tablename__ = "events_diagnosis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # INPATIENT, OUTPATIENT, CARRIER
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    is_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    member: Mapped["Member"] = relationship("Member", back_populates="diagnosis_events")

    __table_args__ = (
        Index("ix_diag_bene_date", "bene_id", "event_date"),
        Index("ix_diag_code_date", "diagnosis_code", "event_date"),
    )


class PrescriptionEvent(Base):
    """
    Normalized Part D Pharmacy Fill Events.
    Source: data/events_prescription.csv
    """
    __tablename__ = "events_prescription"

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    pde_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    drug_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="prescription_events")

    __table_args__ = (
        Index("ix_rx_bene_date", "bene_id", "event_date"),
    )


class MemberTimeline(Base):
    """
    Unified Chronological Medical Timeline.
    Source: data/member_timeline.csv
    """
    __tablename__ = "member_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # diagnosis or prescription
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hcc_v28: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    claim_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_principal: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="timeline_events")

    __table_args__ = (
        Index("ix_tl_bene_date_type", "bene_id", "event_date", "event_type"),
    )


class MemberHCCBaseline(Base):
    """
    Member Historical Documented Baseline Profile (2021-2022).
    Source: data/member_hcc_baseline.csv
    """
    __tablename__ = "member_hcc_baseline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    hcc_v28: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    hcc_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    baseline_diagnosis_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    baseline_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_baseline_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_baseline_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sources: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="baselines")

    __table_args__ = (
        Index("ix_mhb_bene_hcc", "bene_id", "hcc_v28"),
    )


class Suspect(Base):
    """
    Review Opportunities / Candidates (Emerging & Recapture).
    Source: data/suspects.csv
    """
    __tablename__ = "suspects"

    suspect_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    hcc_v28: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    hcc_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspect_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # EMERGING or RECAPTURE
    supporting_diagnosis_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_claim_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_evidence_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_evidence_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sources: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    has_prescription_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Feature scores
    recency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    frequency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    persistence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    diversity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_REVIEW", index=True)
    gap_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latest_context: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    priority_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    diagnosis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_evidence_dates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_evidence_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    principal_diagnosis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prescription_support_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prescription_drug_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    repeated_claim_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    repeated_date_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_diversity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    principal_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    prescription_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ml_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    ml_priority_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    ml_low_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_medium_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_high_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ml_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ml_review_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ml_top_100: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    reason_flags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_references: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"), nullable=True, index=True
    )

    member: Mapped["Member"] = relationship("Member", back_populates="suspects")
    decisions: Mapped[List["ReviewDecision"]] = relationship("ReviewDecision", back_populates="suspect")
    pipeline_run: Mapped[Optional["PipelineRun"]] = relationship("PipelineRun", back_populates="suspects")
    evidence: Mapped[List["SuspectEvidence"]] = relationship("SuspectEvidence", back_populates="suspect")
    llm_reviews: Mapped[List["LLMReview"]] = relationship("LLMReview", back_populates="suspect")

    __table_args__ = (
        Index("ix_suspect_bene_status", "bene_id", "status"),
        Index("ix_suspect_type_status", "suspect_type", "status"),
        Index("ix_suspect_priority_status", "priority_score", "status"),
        Index("ix_suspect_pipeline_run", "pipeline_run_id"),
    )


class PipelineRun(Base):
    """One execution of the claims-to-review pipeline."""

    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    input_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suspects_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_reviews_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    batches: Mapped[List["ClaimBatch"]] = relationship("ClaimBatch", back_populates="pipeline_run")
    suspects: Mapped[List["Suspect"]] = relationship("Suspect", back_populates="pipeline_run")
    evidence: Mapped[List["SuspectEvidence"]] = relationship("SuspectEvidence", back_populates="pipeline_run")
    llm_reviews: Mapped[List["LLMReview"]] = relationship("LLMReview", back_populates="pipeline_run")


class ClaimBatch(Base):
    """Metadata for a received claims batch."""

    __tablename__ = "claim_batches"

    batch_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEIVED", index=True)

    pipeline_run: Mapped[Optional["PipelineRun"]] = relationship("PipelineRun", back_populates="batches")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="batch")


class Claim(Base):
    """Normalized claim line retained for batch traceability."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("claim_batches.batch_id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    bene_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    batch: Mapped["ClaimBatch"] = relationship("ClaimBatch", back_populates="claims")
    member: Mapped["Member"] = relationship("Member", back_populates="claims")

    __table_args__ = (
        Index("ix_claims_batch_bene_date", "batch_id", "bene_id", "claim_date"),
        UniqueConstraint("batch_id", "claim_id", name="uq_claims_batch_claim_id"),
    )


class SuspectEvidence(Base):
    """Atomic evidence items supporting a suspect and its reviewer explanation."""

    __tablename__ = "suspect_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suspect_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("suspects.suspect_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"), nullable=True, index=True
    )
    bene_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    claim_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    suspect: Mapped["Suspect"] = relationship("Suspect", back_populates="evidence")
    pipeline_run: Mapped[Optional["PipelineRun"]] = relationship("PipelineRun", back_populates="evidence")
    member: Mapped["Member"] = relationship("Member", back_populates="suspect_evidence")

    __table_args__ = (
        Index("ix_evidence_suspect_date", "suspect_id", "evidence_date"),
        Index("ix_evidence_bene_hcc_context", "bene_id", "diagnosis_code", "evidence_date"),
    )


class LLMReview(Base):
    """Versioned structured LLM output prepared for human review."""

    __tablename__ = "llm_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suspect_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("suspects.suspect_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reviewer_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    suspect: Mapped["Suspect"] = relationship("Suspect", back_populates="llm_reviews")
    pipeline_run: Mapped[Optional["PipelineRun"]] = relationship("PipelineRun", back_populates="llm_reviews")

    __table_args__ = (
        Index("ix_llm_reviews_suspect_status", "suspect_id", "status"),
    )


class ReviewDecision(Base):
    """
    Coder / Auditor Decisions & Audit Trail.
    Source: data/review_decisions.csv
    """
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suspect_id: Mapped[str] = mapped_column(String(100), ForeignKey("suspects.suspect_id", ondelete="CASCADE"), nullable=False, index=True)
    bene_id: Mapped[str] = mapped_column(String(50), ForeignKey("members.bene_id", ondelete="CASCADE"), nullable=False, index=True)
    hcc_v28: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    suspect_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    priority_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False) # SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_EVIDENCE
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    suspect: Mapped["Suspect"] = relationship("Suspect", back_populates="decisions")


class IngestionRejection(Base):
    """
    Audit log table for rejected, invalid, or corrupted records during ingestion.
    """
    __tablename__ = "ingestion_rejections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
