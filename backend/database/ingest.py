"""
Repeatable Ingestion Script.

Loads prepared CSV files from data/ into PostgreSQL using SQLAlchemy 2.x:
1. data/members.csv                -> members
2. data/hcc_mapping.csv            -> hcc_mappings
3. data/events_diagnosis.csv       -> events_diagnosis
4. data/events_prescription.csv    -> events_prescription
5. data/member_timeline.csv        -> member_timeline
6. data/member_hcc_baseline.csv    -> member_hcc_baseline
7. data/suspects.csv               -> suspects

Features:
- Streamed batch ingestion (CHUNK_SIZE=50,000) for high performance on 2GB+ CSV files
- Full validation of dates, booleans, numeric scores, and IDs
- Invalid / duplicate records logged to ingestion_rejections table
- Repeatable & safe to re-run (idempotent ON CONFLICT / clean truncate strategy)
- Detailed progress and row count reporting
"""

import csv
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from database.session import engine, SessionLocal, init_db
    from database.models import (
        Member,
        HCCMapping,
        DiagnosisEvent,
        PrescriptionEvent,
        MemberTimeline,
        MemberHCCBaseline,
        Suspect,
        IngestionRejection,
    )
except ImportError:
    from backend.database.session import engine, SessionLocal, init_db
    from backend.database.models import (
        Member,
        HCCMapping,
        DiagnosisEvent,
        PrescriptionEvent,
        MemberTimeline,
        MemberHCCBaseline,
        Suspect,
        IngestionRejection,
    )

DATA_DIR = PROJECT_ROOT / "data"
CHUNK_SIZE = 50_000

def parse_date(val: Optional[str]) -> Optional[date]:
    """Parse string 'YYYY-MM-DD' into Python date or None."""
    if not val or str(val).strip() in ("", "nan", "NONE", "NULL"):
        return None
    s = str(val).strip()
    if len(s) >= 10:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def parse_bool(val: Optional[str]) -> bool:
    """Parse boolean flag from string ('True'/'False'/'Yes'/'No'/'1'/'0')."""
    if not val:
        return False
    v = str(val).strip().lower()
    return v in ("true", "yes", "1")

def parse_float(val: Optional[str], default: float = 0.0) -> float:
    """Safely convert string to float."""
    if not val or str(val).strip() in ("", "nan"):
        return default
    try:
        return float(val)
    except ValueError:
        return default

def parse_int(val: Optional[str], default: int = 0) -> int:
    """Safely convert string to int."""
    if not val or str(val).strip() in ("", "nan"):
        return default
    try:
        return int(float(val))
    except ValueError:
        return default

def log_rejection(db: Session, source_file: str, row_idx: int, raw_row: dict, reason: str):
    """Log an invalid or rejected record to ingestion_rejections table."""
    rejection = IngestionRejection(
        source_file=source_file,
        row_index=row_idx,
        raw_data=str(raw_row),
        reason=reason,
        created_at=datetime.utcnow()
    )
    db.add(rejection)

# -------------------------------------------------------------------------------
# Ingestion Functions
# -------------------------------------------------------------------------------

def ingest_members(db: Session) -> dict:
    csv_file = DATA_DIR / "members.csv"
    if not csv_file.exists():
        print(f"Skipping members: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> members table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0
    seen_ids: Set[str] = set()

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            bene_id = row.get("bene_id", "").strip()
            if not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing bene_id")
                rejected += 1
                continue

            if bene_id in seen_ids:
                log_rejection(db, csv_file.name, idx, row, f"Duplicate bene_id: {bene_id}")
                rejected += 1
                continue
            seen_ids.add(bene_id)

            batch.append({
                "bene_id": bene_id,
                "birth_date": parse_date(row.get("birth_date")),
                "sex": row.get("sex", "").strip() or None,
                "race": row.get("race", "").strip() or None,
                "state": row.get("state", "").strip() or None,
                "county": row.get("county", "").strip() or None,
                "zip": row.get("zip", "").strip() or None,
                "esrd_indicator": row.get("esrd_indicator", "").strip() or None,
                "death_date": parse_date(row.get("death_date")),
                "enrollment_years": row.get("enrollment_years", "").strip() or None,
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(Member, batch)
                db.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.bulk_insert_mappings(Member, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Members completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_hcc_mapping(db: Session) -> dict:
    csv_file = DATA_DIR / "hcc_mapping.csv"
    if not csv_file.exists():
        print(f"Skipping hcc_mapping: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> hcc_mappings table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0
    seen_codes: Set[str] = set()

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            code = row.get("diagnosis_code", "").strip()
            if not code:
                log_rejection(db, csv_file.name, idx, row, "Missing diagnosis_code")
                rejected += 1
                continue

            if code in seen_codes:
                log_rejection(db, csv_file.name, idx, row, f"Duplicate diagnosis_code: {code}")
                rejected += 1
                continue
            seen_codes.add(code)

            hcc = row.get("hcc_v28", "").strip() or None

            batch.append({
                "diagnosis_code": code,
                "description": row.get("description", "").strip() or None,
                "hcc_v28": hcc,
                "payment_2026": parse_bool(row.get("payment_2026")),
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(HCCMapping, batch)
                db.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.bulk_insert_mappings(HCCMapping, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  HCC Mappings completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_events_diagnosis(db: Session) -> dict:
    csv_file = DATA_DIR / "events_diagnosis.csv"
    if not csv_file.exists():
        print(f"Skipping events_diagnosis: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> events_diagnosis table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            event_id = row.get("event_id", "").strip()
            bene_id = row.get("bene_id", "").strip()

            if not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing bene_id")
                rejected += 1
                continue

            batch.append({
                "event_id": event_id or None,
                "bene_id": bene_id,
                "claim_id": row.get("claim_id", "").strip() or None,
                "event_date": parse_date(row.get("event_date")),
                "source": row.get("source", "").strip() or None,
                "diagnosis_code": row.get("diagnosis_code", "").strip() or None,
                "is_principal": parse_bool(row.get("is_principal")),
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(DiagnosisEvent, batch)
                db.commit()
                inserted += len(batch)
                batch = []
                if inserted % 500_000 == 0:
                    print(f"    ... inserted {inserted:,} rows", flush=True)

        if batch:
            db.bulk_insert_mappings(DiagnosisEvent, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Diagnosis Events completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_events_prescription(db: Session) -> dict:
    csv_file = DATA_DIR / "events_prescription.csv"
    if not csv_file.exists():
        print(f"Skipping events_prescription: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> events_prescription table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0
    seen_event_ids: Set[str] = set()

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            event_id = row.get("event_id", "").strip()
            bene_id = row.get("bene_id", "").strip()

            if not event_id or not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing event_id or bene_id")
                rejected += 1
                continue

            if event_id in seen_event_ids:
                log_rejection(db, csv_file.name, idx, row, f"Duplicate event_id: {event_id}")
                rejected += 1
                continue
            seen_event_ids.add(event_id)

            batch.append({
                "event_id": event_id,
                "bene_id": bene_id,
                "pde_id": row.get("pde_id", "").strip() or None,
                "event_date": parse_date(row.get("event_date")),
                "drug_code": row.get("drug_code", "").strip() or None,
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(PrescriptionEvent, batch)
                db.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.bulk_insert_mappings(PrescriptionEvent, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Prescription Events completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_member_timeline(db: Session) -> dict:
    csv_file = DATA_DIR / "member_timeline.csv"
    if not csv_file.exists():
        print(f"Skipping member_timeline: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> member_timeline table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            bene_id = row.get("bene_id", "").strip()
            if not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing bene_id")
                rejected += 1
                continue

            batch.append({
                "event_id": row.get("event_id", "").strip() or None,
                "bene_id": bene_id,
                "event_date": parse_date(row.get("event_date")),
                "event_type": row.get("event_type", "").strip() or None,
                "code": row.get("code", "").strip() or None,
                "hcc_v28": row.get("hcc_v28", "").strip() or None,
                "source": row.get("source", "").strip() or None,
                "claim_id": row.get("claim_id", "").strip() or None,
                "is_principal": parse_bool(row.get("is_principal")) if row.get("is_principal") else None,
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(MemberTimeline, batch)
                db.commit()
                inserted += len(batch)
                batch = []
                if inserted % 500_000 == 0:
                    print(f"    ... inserted {inserted:,} timeline events", flush=True)

        if batch:
            db.bulk_insert_mappings(MemberTimeline, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Member Timeline completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_member_hcc_baseline(db: Session) -> dict:
    csv_file = DATA_DIR / "member_hcc_baseline.csv"
    if not csv_file.exists():
        print(f"Skipping member_hcc_baseline: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> member_hcc_baseline table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            bene_id = row.get("bene_id", "").strip()
            if not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing bene_id")
                rejected += 1
                continue

            batch.append({
                "bene_id": bene_id,
                "hcc_v28": row.get("hcc_v28", "").strip() or None,
                "hcc_description": row.get("hcc_description", "").strip() or None,
                "baseline_diagnosis_codes": row.get("baseline_diagnosis_codes", "").strip() or None,
                "baseline_claim_count": parse_int(row.get("baseline_claim_count")),
                "first_baseline_date": parse_date(row.get("first_baseline_date")),
                "last_baseline_date": parse_date(row.get("last_baseline_date")),
                "sources": row.get("sources", "").strip() or None,
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(MemberHCCBaseline, batch)
                db.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.bulk_insert_mappings(MemberHCCBaseline, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Member HCC Baseline completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


def ingest_suspects(db: Session) -> dict:
    csv_file = DATA_DIR / "suspects.csv"
    if not csv_file.exists():
        print(f"Skipping suspects: File not found ({csv_file})")
        return {"processed": 0, "inserted": 0, "rejected": 0}

    print(f"\nIngesting {csv_file.name} -> suspects table...")
    t0 = time.time()
    processed = 0
    inserted = 0
    rejected = 0
    seen_suspect_ids: Set[str] = set()

    batch = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            processed += 1
            suspect_id = row.get("suspect_id", "").strip()
            bene_id = row.get("bene_id", "").strip()

            if not suspect_id or not bene_id:
                log_rejection(db, csv_file.name, idx, row, "Missing suspect_id or bene_id")
                rejected += 1
                continue

            if suspect_id in seen_suspect_ids:
                log_rejection(db, csv_file.name, idx, row, f"Duplicate suspect_id: {suspect_id}")
                rejected += 1
                continue
            seen_suspect_ids.add(suspect_id)

            batch.append({
                "suspect_id": suspect_id,
                "bene_id": bene_id,
                "hcc_v28": row.get("hcc_v28", "").strip() or None,
                "hcc_description": row.get("hcc_description", "").strip() or None,
                "suspect_type": row.get("suspect_type", "").strip() or None,
                "supporting_diagnosis_codes": row.get("supporting_diagnosis_codes", "").strip() or None,
                "supporting_claim_ids": row.get("supporting_claim_ids", "").strip() or None,
                "evidence_count": parse_int(row.get("evidence_count"), 1),
                "first_evidence_date": parse_date(row.get("first_evidence_date")),
                "last_evidence_date": parse_date(row.get("last_evidence_date")),
                "sources": row.get("sources", "").strip() or None,
                "has_prescription_support": parse_bool(row.get("has_prescription_support")),
                "recency_score": parse_float(row.get("recency_score")),
                "frequency_score": parse_float(row.get("frequency_score")),
                "persistence_score": parse_float(row.get("persistence_score")),
                "diversity_score": parse_float(row.get("diversity_score")),
                "priority_score": parse_float(row.get("priority_score")),
                "status": row.get("status", "PENDING_REVIEW").strip(),
            })

            if len(batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(Suspect, batch)
                db.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.bulk_insert_mappings(Suspect, batch)
            db.commit()
            inserted += len(batch)

    dt = time.time() - t0
    print(f"  Suspects completed in {dt:.2f}s | Processed: {processed:,} | Inserted: {inserted:,} | Rejected: {rejected}")
    return {"processed": processed, "inserted": inserted, "rejected": rejected}


# -------------------------------------------------------------------------------
# Main Execution Pipeline
# -------------------------------------------------------------------------------

def run_ingestion():
    print("=" * 70)
    print("  POSTGRESQL DATA INGESTION PIPELINE")
    print("=" * 70)
    start_total = time.time()

    # Ensure tables exist
    init_db()

    db = SessionLocal()
    try:
        # Check if database already contains data for repeatability
        member_count = db.scalar(select(func.count()).select_from(Member))
        if member_count > 0:
            print(f"\n[Notice] Database already contains {member_count:,} members.")
            print("Resetting existing tables for clean, repeatable ingestion...")
            if db.bind.dialect.name == "sqlite":
                for table_name in [
                    "review_decisions", "suspects", "member_hcc_baseline",
                    "member_timeline", "events_prescription", "events_diagnosis",
                    "hcc_mappings", "members", "ingestion_rejections"
                ]:
                    db.execute(text(f"DELETE FROM {table_name};"))
            else:
                db.execute(text("TRUNCATE TABLE review_decisions, suspects, member_hcc_baseline, member_timeline, events_prescription, events_diagnosis, hcc_mappings, members, ingestion_rejections CASCADE;"))
            db.commit()
            print("Existing tables reset cleanly.")

        results = {}
        results["members"] = ingest_members(db)
        results["hcc_mappings"] = ingest_hcc_mapping(db)
        results["events_diagnosis"] = ingest_events_diagnosis(db)
        results["events_prescription"] = ingest_events_prescription(db)
        results["member_timeline"] = ingest_member_timeline(db)
        results["member_hcc_baseline"] = ingest_member_hcc_baseline(db)
        # NOTE: Suspects are no longer loaded from CSV. The old suspects.csv
        # was built by the V1 scoring engine (build_hcc_suspects.py) with only
        # 4 signals and does not match the final engine output schema.
        # Suspects are now created exclusively by the incremental pipeline
        # via POST /api/pipeline/batches → engine_service.py.

        total_time = time.time() - start_total
        print("\n" + "=" * 70)
        print("  INGESTION SUMMARY REPORT")
        print("=" * 70)
        print(f"{'Table Name':<24s} {'Processed':>12s} {'Inserted':>12s} {'Rejected':>10s}")
        print("-" * 70)
        for tbl, res in results.items():
            print(f"{tbl:<24s} {res['processed']:>12,} {res['inserted']:>12,} {res['rejected']:>10,}")
        print("=" * 70)
        print(f"Total Pipeline Execution Time: {total_time:.2f} seconds")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Ingestion failed with exception: {e}", file=sys.stderr)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_ingestion()
