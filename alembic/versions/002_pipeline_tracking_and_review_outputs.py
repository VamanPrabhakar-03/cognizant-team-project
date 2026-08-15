"""Add pipeline tracking, claim batches, evidence, and LLM review outputs.

Revision ID: 002_pipeline_tracking_and_review_outputs
Revises: 001_initial_schema
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_pipeline_tracking_and_review_outputs"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("batch_id", sa.String(length=100), nullable=True),
        sa.Column("source_file", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="RUNNING"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("input_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspects_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_reviews_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_pipeline_runs_batch_id", "pipeline_runs", ["batch_id"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])

    op.create_table(
        "claim_batches",
        sa.Column("batch_id", sa.String(length=100), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=100), nullable=True),
        sa.Column("source_file", sa.String(length=255), nullable=True),
        sa.Column("source_system", sa.String(length=100), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="RECEIVED"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.run_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("batch_id"),
    )
    op.create_index("ix_claim_batches_pipeline_run_id", "claim_batches", ["pipeline_run_id"])
    op.create_index("ix_claim_batches_status", "claim_batches", ["status"])

    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=100), nullable=False),
        sa.Column("claim_id", sa.String(length=100), nullable=True),
        sa.Column("bene_id", sa.String(length=50), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=True),
        sa.Column("diagnosis_code", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("is_principal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["claim_batches.batch_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bene_id"], ["members.bene_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "claim_id", name="uq_claims_batch_claim_id"),
    )
    op.create_index("ix_claims_batch_id", "claims", ["batch_id"])
    op.create_index("ix_claims_claim_id", "claims", ["claim_id"])
    op.create_index("ix_claims_bene_id", "claims", ["bene_id"])
    op.create_index("ix_claims_claim_date", "claims", ["claim_date"])
    op.create_index("ix_claims_diagnosis_code", "claims", ["diagnosis_code"])
    op.create_index("ix_claims_batch_bene_date", "claims", ["batch_id", "bene_id", "claim_date"])

    # Keep run provenance on generated suspects without changing existing rows.
    # Batch mode keeps this migration compatible with SQLite test databases,
    # while emitting normal ALTER statements for PostgreSQL.
    with op.batch_alter_table("suspects") as batch_op:
        batch_op.add_column(sa.Column("pipeline_run_id", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            "fk_suspects_pipeline_run_id",
            "pipeline_runs",
            ["pipeline_run_id"],
            ["run_id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_suspects_pipeline_run_id", ["pipeline_run_id"])

    op.create_table(
        "suspect_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suspect_id", sa.String(length=100), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=100), nullable=True),
        sa.Column("bene_id", sa.String(length=50), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("diagnosis_code", sa.String(length=20), nullable=True),
        sa.Column("claim_id", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("evidence_strength", sa.Float(), nullable=True),
        sa.Column("evidence_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["suspect_id"], ["suspects.suspect_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.run_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bene_id"], ["members.bene_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suspect_evidence_suspect_id", "suspect_evidence", ["suspect_id"])
    op.create_index("ix_suspect_evidence_pipeline_run_id", "suspect_evidence", ["pipeline_run_id"])
    op.create_index("ix_suspect_evidence_bene_id", "suspect_evidence", ["bene_id"])
    op.create_index("ix_suspect_evidence_evidence_date", "suspect_evidence", ["evidence_date"])
    op.create_index("ix_suspect_evidence_diagnosis_code", "suspect_evidence", ["diagnosis_code"])
    op.create_index("ix_suspect_evidence_claim_id", "suspect_evidence", ["claim_id"])
    op.create_index("ix_evidence_suspect_date", "suspect_evidence", ["suspect_id", "evidence_date"])
    op.create_index(
        "ix_evidence_bene_hcc_context",
        "suspect_evidence",
        ["bene_id", "diagnosis_code", "evidence_date"],
    )

    op.create_table(
        "llm_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suspect_id", sa.String(length=100), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("reviewer_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["suspect_id"], ["suspects.suspect_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.run_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_reviews_suspect_id", "llm_reviews", ["suspect_id"])
    op.create_index("ix_llm_reviews_pipeline_run_id", "llm_reviews", ["pipeline_run_id"])
    op.create_index("ix_llm_reviews_status", "llm_reviews", ["status"])
    op.create_index("ix_llm_reviews_suspect_status", "llm_reviews", ["suspect_id", "status"])


def downgrade() -> None:
    op.drop_table("llm_reviews")
    op.drop_table("suspect_evidence")
    with op.batch_alter_table("suspects") as batch_op:
        batch_op.drop_index("ix_suspects_pipeline_run_id")
        batch_op.drop_constraint("fk_suspects_pipeline_run_id", type_="foreignkey")
        batch_op.drop_column("pipeline_run_id")
    op.drop_table("claims")
    op.drop_table("claim_batches")
    op.drop_table("pipeline_runs")
