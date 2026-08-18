"""
Quick Reset Script for Testing.

Safely resets only generated pipeline data:
- suspects
- llm_reviews
- review_decisions
- suspect_evidence
- claims
- claim_batches
- pipeline_runs

Preserves all historical foundation tables:
- members
- member_timeline
- member_hcc_baseline
- hcc_mappings
- events_diagnosis
- events_prescription
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import psycopg

def reset_pipeline():
    conn_str = (
        f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
        f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
        f"password={os.getenv('DB_PASSWORD')} sslmode={os.getenv('DB_SSLMODE')}"
    )
    
    print("Connecting to Azure PostgreSQL Database...")
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # Foreign-key safe deletion order
            tables = [
                ("review_decisions", "DELETE FROM review_decisions"),
                ("llm_reviews",      "DELETE FROM llm_reviews"),
                ("suspect_evidence", "DELETE FROM suspect_evidence"),
                ("suspects",         "DELETE FROM suspects"),
                ("claims",           "DELETE FROM claims"),
                ("claim_batches",    "DELETE FROM claim_batches"),
                ("pipeline_runs",    "DELETE FROM pipeline_runs"),
            ]
            
            print("\nClearing pipeline test data...")
            for table_name, query in tables:
                cur.execute(query)
                print(f"  [OK] Cleared {table_name}: {cur.rowcount} rows deleted")
            
            conn.commit()
            print("\n[SUCCESS] Pipeline reset complete! Ready for a fresh claims batch upload.")

if __name__ == "__main__":
    reset_pipeline()
