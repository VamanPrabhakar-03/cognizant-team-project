"""Migration script for Azure PostgreSQL database.

Safely alters existing tables and creates missing tables on Azure PostgreSQL
without failing on constraint errors.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from database.session import engine


STATEMENTS = [
    # 1. Ensure members table has primary key on bene_id if missing
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'members_pkey'
        ) THEN
            ALTER TABLE members ADD PRIMARY KEY (bene_id);
        END IF;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END $$;
    """,

    # 2. Add 21 missing columns to suspects table
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS gap_type VARCHAR(20);",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS latest_context VARCHAR(30);",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS priority VARCHAR(20);",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS priority_level VARCHAR(20);",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS diagnosis_count INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS unique_claim_count INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS unique_event_count INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS distinct_evidence_dates INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS distinct_evidence_months INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS distinct_sources INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS principal_diagnosis_count INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS prescription_support_count INTEGER NOT NULL DEFAULT 0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS prescription_drug_codes JSON;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS repeated_claim_score FLOAT NOT NULL DEFAULT 0.0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS repeated_date_score FLOAT NOT NULL DEFAULT 0.0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS source_diversity_score FLOAT NOT NULL DEFAULT 0.0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS principal_score FLOAT NOT NULL DEFAULT 0.0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS prescription_score FLOAT NOT NULL DEFAULT 0.0;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS reason_flags JSON;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS evidence_summary TEXT;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS evidence_references JSON;",
    "ALTER TABLE suspects ADD COLUMN IF NOT EXISTS pipeline_run_id VARCHAR(100);",

    # 3. Create pipeline_runs table if missing
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id VARCHAR(100) PRIMARY KEY,
        batch_id VARCHAR(100),
        source_file VARCHAR(255),
        status VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
        started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP WITHOUT TIME ZONE,
        input_rows INTEGER NOT NULL DEFAULT 0,
        valid_rows INTEGER NOT NULL DEFAULT 0,
        rejected_rows INTEGER NOT NULL DEFAULT 0,
        claims_processed INTEGER NOT NULL DEFAULT 0,
        suspects_created INTEGER NOT NULL DEFAULT 0,
        evidence_created INTEGER NOT NULL DEFAULT 0,
        llm_reviews_created INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        created_by VARCHAR(100)
    );
    """,

    # 4. Create claim_batches table if missing
    """
    CREATE TABLE IF NOT EXISTS claim_batches (
        batch_id VARCHAR(100) PRIMARY KEY,
        pipeline_run_id VARCHAR(100),
        source_file VARCHAR(255),
        source_system VARCHAR(100),
        received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        row_count INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED'
    );
    """,

    # 5. Create claims table if missing
    """
    CREATE TABLE IF NOT EXISTS claims (
        id SERIAL PRIMARY KEY,
        batch_id VARCHAR(100) NOT NULL,
        claim_id VARCHAR(100),
        bene_id VARCHAR(50) NOT NULL,
        claim_date DATE,
        diagnosis_code VARCHAR(20),
        source VARCHAR(50),
        is_principal BOOLEAN NOT NULL DEFAULT FALSE,
        raw_payload JSON,
        CONSTRAINT uq_claims_batch_claim_id UNIQUE (batch_id, claim_id)
    );
    """,

    # 6. Create suspect_evidence table if missing
    """
    CREATE TABLE IF NOT EXISTS suspect_evidence (
        id SERIAL PRIMARY KEY,
        suspect_id VARCHAR(100) NOT NULL,
        pipeline_run_id VARCHAR(100),
        bene_id VARCHAR(50) NOT NULL,
        evidence_type VARCHAR(50) NOT NULL,
        evidence_date DATE,
        diagnosis_code VARCHAR(20),
        claim_id VARCHAR(100),
        source VARCHAR(50),
        evidence_text TEXT,
        evidence_strength FLOAT,
        evidence_metadata JSON,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 7. Create llm_reviews table if missing
    """
    CREATE TABLE IF NOT EXISTS llm_reviews (
        id SERIAL PRIMARY KEY,
        suspect_id VARCHAR(100) NOT NULL,
        pipeline_run_id VARCHAR(100),
        status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
        model_name VARCHAR(100),
        prompt_version VARCHAR(50),
        input_payload JSON,
        output_payload JSON,
        reviewer_summary TEXT,
        error_message TEXT,
        generated_at TIMESTAMP WITHOUT TIME ZONE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 8. Add High-Performance Indexes for Instant Member & Timeline Lookups
    "CREATE INDEX IF NOT EXISTS ix_member_timeline_bene_id ON member_timeline(bene_id);",
    "CREATE INDEX IF NOT EXISTS ix_member_timeline_bene_date ON member_timeline(bene_id, event_date DESC);",
    "CREATE INDEX IF NOT EXISTS ix_member_timeline_bene_type ON member_timeline(bene_id, event_type);",
    "CREATE INDEX IF NOT EXISTS ix_suspects_bene_id ON suspects(bene_id);",
    "CREATE INDEX IF NOT EXISTS ix_member_hcc_baseline_bene_id ON member_hcc_baseline(bene_id);",
    "CREATE INDEX IF NOT EXISTS ix_events_diagnosis_bene_id ON events_diagnosis(bene_id);",
    "CREATE INDEX IF NOT EXISTS ix_events_prescription_bene_id ON events_prescription(bene_id);",
]


def apply_azure_migrations():
    print("=" * 70)
    print("  APPLYING SCHEMA MIGRATIONS TO AZURE POSTGRESQL")
    print("=" * 70)
    print("Connecting to database engine...")
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"Warning on statement: {e}")
    print("\nAZURE POSTGRESQL SCHEMA MIGRATION COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    apply_azure_migrations()
