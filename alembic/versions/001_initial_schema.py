"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-13 21:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. members
    op.create_table(
        'members',
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('sex', sa.String(length=10), nullable=True),
        sa.Column('race', sa.String(length=10), nullable=True),
        sa.Column('state', sa.String(length=10), nullable=True),
        sa.Column('county', sa.String(length=20), nullable=True),
        sa.Column('zip', sa.String(length=20), nullable=True),
        sa.Column('esrd_indicator', sa.String(length=10), nullable=True),
        sa.Column('death_date', sa.Date(), nullable=True),
        sa.Column('enrollment_years', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('bene_id')
    )
    op.create_index('ix_members_state', 'members', ['state'], unique=False)

    # 2. hcc_mappings
    op.create_table(
        'hcc_mappings',
        sa.Column('diagnosis_code', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hcc_v28', sa.String(length=20), nullable=True),
        sa.Column('payment_2026', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('diagnosis_code')
    )
    op.create_index('ix_hcc_mappings_hcc_v28', 'hcc_mappings', ['hcc_v28'], unique=False)
    op.create_index('ix_hcc_mapping_code_hcc', 'hcc_mappings', ['diagnosis_code', 'hcc_v28'], unique=False)

    # 3. events_diagnosis
    op.create_table(
        'events_diagnosis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=100), nullable=True),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('claim_id', sa.String(length=100), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('diagnosis_code', sa.String(length=20), nullable=True),
        sa.Column('is_principal', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_events_diagnosis_bene_id', 'events_diagnosis', ['bene_id'], unique=False)
    op.create_index('ix_events_diagnosis_claim_id', 'events_diagnosis', ['claim_id'], unique=False)
    op.create_index('ix_events_diagnosis_event_date', 'events_diagnosis', ['event_date'], unique=False)
    op.create_index('ix_events_diagnosis_diagnosis_code', 'events_diagnosis', ['diagnosis_code'], unique=False)
    op.create_index('ix_diag_bene_date', 'events_diagnosis', ['bene_id', 'event_date'], unique=False)
    op.create_index('ix_diag_code_date', 'events_diagnosis', ['diagnosis_code', 'event_date'], unique=False)

    # 4. events_prescription
    op.create_table(
        'events_prescription',
        sa.Column('event_id', sa.String(length=100), nullable=False),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('pde_id', sa.String(length=100), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('drug_code', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_events_prescription_bene_id', 'events_prescription', ['bene_id'], unique=False)
    op.create_index('ix_events_prescription_pde_id', 'events_prescription', ['pde_id'], unique=False)
    op.create_index('ix_events_prescription_event_date', 'events_prescription', ['event_date'], unique=False)
    op.create_index('ix_rx_bene_date', 'events_prescription', ['bene_id', 'event_date'], unique=False)

    # 5. member_timeline
    op.create_table(
        'member_timeline',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=100), nullable=True),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('event_type', sa.String(length=20), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('hcc_v28', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('claim_id', sa.String(length=100), nullable=True),
        sa.Column('is_principal', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_member_timeline_bene_id', 'member_timeline', ['bene_id'], unique=False)
    op.create_index('ix_member_timeline_event_date', 'member_timeline', ['event_date'], unique=False)
    op.create_index('ix_member_timeline_hcc_v28', 'member_timeline', ['hcc_v28'], unique=False)
    op.create_index('ix_member_timeline_event_id', 'member_timeline', ['event_id'], unique=False)
    op.create_index('ix_tl_bene_date_type', 'member_timeline', ['bene_id', 'event_date', 'event_type'], unique=False)

    # 6. member_hcc_baseline
    op.create_table(
        'member_hcc_baseline',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('hcc_v28', sa.String(length=20), nullable=True),
        sa.Column('hcc_description', sa.Text(), nullable=True),
        sa.Column('baseline_diagnosis_codes', sa.Text(), nullable=True),
        sa.Column('baseline_claim_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_baseline_date', sa.Date(), nullable=True),
        sa.Column('last_baseline_date', sa.Date(), nullable=True),
        sa.Column('sources', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_member_hcc_baseline_bene_id', 'member_hcc_baseline', ['bene_id'], unique=False)
    op.create_index('ix_member_hcc_baseline_hcc_v28', 'member_hcc_baseline', ['hcc_v28'], unique=False)
    op.create_index('ix_mhb_bene_hcc', 'member_hcc_baseline', ['bene_id', 'hcc_v28'], unique=False)

    # 7. suspects
    op.create_table(
        'suspects',
        sa.Column('suspect_id', sa.String(length=100), nullable=False),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('hcc_v28', sa.String(length=20), nullable=True),
        sa.Column('hcc_description', sa.Text(), nullable=True),
        sa.Column('suspect_type', sa.String(length=20), nullable=True),
        sa.Column('supporting_diagnosis_codes', sa.Text(), nullable=True),
        sa.Column('supporting_claim_ids', sa.Text(), nullable=True),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_evidence_date', sa.Date(), nullable=True),
        sa.Column('last_evidence_date', sa.Date(), nullable=True),
        sa.Column('sources', sa.String(length=100), nullable=True),
        sa.Column('has_prescription_support', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('recency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('frequency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('persistence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('diversity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('priority_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING_REVIEW'),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('suspect_id')
    )
    op.create_index('ix_suspects_bene_id', 'suspects', ['bene_id'], unique=False)
    op.create_index('ix_suspects_hcc_v28', 'suspects', ['hcc_v28'], unique=False)
    op.create_index('ix_suspects_priority_score', 'suspects', ['priority_score'], unique=False)
    op.create_index('ix_suspects_status', 'suspects', ['status'], unique=False)
    op.create_index('ix_suspect_bene_status', 'suspects', ['bene_id', 'status'], unique=False)
    op.create_index('ix_suspect_type_status', 'suspects', ['suspect_type', 'status'], unique=False)
    op.create_index('ix_suspect_priority_status', 'suspects', ['priority_score', 'status'], unique=False)

    # 8. review_decisions
    op.create_table(
        'review_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('suspect_id', sa.String(length=100), nullable=False),
        sa.Column('bene_id', sa.String(length=50), nullable=False),
        sa.Column('hcc_v28', sa.String(length=20), nullable=True),
        sa.Column('suspect_type', sa.String(length=20), nullable=True),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('decision', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reviewer_timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bene_id'], ['members.bene_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['suspect_id'], ['suspects.suspect_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_review_decisions_suspect_id', 'review_decisions', ['suspect_id'], unique=False)
    op.create_index('ix_review_decisions_bene_id', 'review_decisions', ['bene_id'], unique=False)

    # 9. ingestion_rejections
    op.create_table(
        'ingestion_rejections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_file', sa.String(length=100), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingestion_rejections_source_file', 'ingestion_rejections', ['source_file'], unique=False)


def downgrade() -> None:
    op.drop_table('ingestion_rejections')
    op.drop_table('review_decisions')
    op.drop_table('suspects')
    op.drop_table('member_hcc_baseline')
    op.drop_table('member_timeline')
    op.drop_table('events_prescription')
    op.drop_table('events_diagnosis')
    op.drop_table('hcc_mappings')
    op.drop_table('members')
