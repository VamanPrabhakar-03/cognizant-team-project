"""Align suspect storage with the frozen evidence engine output.

Revision ID: 003_align_suspect_engine_output
Revises: 002_pipeline_tracking_and_review_outputs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_align_suspect_engine_output"
down_revision: Union[str, None] = "002_pipeline_tracking_and_review_outputs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        sa.Column("gap_type", sa.String(length=20), nullable=True),
        sa.Column("latest_context", sa.String(length=30), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("priority_level", sa.String(length=20), nullable=True),
        sa.Column("diagnosis_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_evidence_dates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_evidence_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("principal_diagnosis_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prescription_support_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prescription_drug_codes", sa.JSON(), nullable=True),
        sa.Column("repeated_claim_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("repeated_date_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("source_diversity_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("principal_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("prescription_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("reason_flags", sa.JSON(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("evidence_references", sa.JSON(), nullable=True),
    ]
    with op.batch_alter_table("suspects") as batch_op:
        for column in columns:
            batch_op.add_column(column)


def downgrade() -> None:
    names = [
        "evidence_references", "evidence_summary", "reason_flags",
        "prescription_score", "principal_score", "source_diversity_score",
        "repeated_date_score", "repeated_claim_score", "prescription_drug_codes",
        "prescription_support_count", "principal_diagnosis_count", "distinct_sources",
        "distinct_evidence_months", "distinct_evidence_dates", "unique_event_count",
        "unique_claim_count", "diagnosis_count", "priority_level", "priority",
        "latest_context", "gap_type",
    ]
    with op.batch_alter_table("suspects") as batch_op:
        for name in names:
            batch_op.drop_column(name)
