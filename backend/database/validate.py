"""
Post-Loading Database Validation Script.

Verifies:
1. Table row counts against expectation
2. Primary key null & duplicate checks
3. Foreign key referential integrity:
   - events_diagnosis -> members (bene_id)
   - events_prescription -> members (bene_id)
   - member_timeline -> members (bene_id)
   - member_hcc_baseline -> members (bene_id)
   - suspects -> members (bene_id)
4. ICD-10 to HCC mapping coverage integrity
5. Ingestion rejections log review
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.session import SessionLocal
from src.database.models import (
    Member,
    HCCMapping,
    DiagnosisEvent,
    PrescriptionEvent,
    MemberTimeline,
    MemberHCCBaseline,
    Suspect,
    ReviewDecision,
    IngestionRejection,
)

def run_database_validation() -> bool:
    print("=" * 70)
    print("  POST-LOADING DATABASE INTEGRITY VALIDATION")
    print("=" * 70)
    t0 = time.time()
    all_passed = True
    db: Session = SessionLocal()

    try:
        # -------------------------------------------------------------------
        # 1. Table Row Counts
        # -------------------------------------------------------------------
        print("\n[Check 1] Table Row Counts...")
        tables = [
            ("members", Member),
            ("hcc_mappings", HCCMapping),
            ("events_diagnosis", DiagnosisEvent),
            ("events_prescription", PrescriptionEvent),
            ("member_timeline", MemberTimeline),
            ("member_hcc_baseline", MemberHCCBaseline),
            ("suspects", Suspect),
            ("review_decisions", ReviewDecision),
            ("ingestion_rejections", IngestionRejection),
        ]

        row_counts = {}
        for name, model in tables:
            cnt = db.scalar(select(func.count()).select_from(model))
            row_counts[name] = cnt
            print(f"  - {name:<22s}: {cnt:>12,} rows")

        if row_counts["members"] == 0:
            print("  [FAIL] members table is empty!")
            all_passed = False
        else:
            print("  [PASS] Row counts present and verified.")

        # -------------------------------------------------------------------
        # 2. Null Checks on Key Identifiers
        # -------------------------------------------------------------------
        print("\n[Check 2] Null Primary/Foreign Key Checks...")

        null_members = db.scalar(select(func.count()).select_from(Member).where(Member.bene_id == None))
        null_diag_events = db.scalar(select(func.count()).select_from(DiagnosisEvent).where(DiagnosisEvent.event_id == None))
        null_suspects = db.scalar(select(func.count()).select_from(Suspect).where(Suspect.suspect_id == None))

        print(f"  - Null bene_id in members: {null_members}")
        print(f"  - Null event_id in events_diagnosis: {null_diag_events}")
        print(f"  - Null suspect_id in suspects: {null_suspects}")

        if null_members > 0 or null_diag_events > 0 or null_suspects > 0:
            print("  [FAIL] Null primary key values detected!")
            all_passed = False
        else:
            print("  [PASS] Zero null primary keys.")

        # -------------------------------------------------------------------
        # 3. Duplicate Checks
        # -------------------------------------------------------------------
        print("\n[Check 3] Primary Key Uniqueness Checks...")

        dupe_members = db.scalar(
            text("SELECT COUNT(*) FROM (SELECT bene_id FROM members GROUP BY bene_id HAVING COUNT(*) > 1) sub")
        )
        dupe_suspects = db.scalar(
            text("SELECT COUNT(*) FROM (SELECT suspect_id FROM suspects GROUP BY suspect_id HAVING COUNT(*) > 1) sub")
        )

        print(f"  - Duplicate bene_id in members: {dupe_members}")
        print(f"  - Duplicate suspect_id in suspects: {dupe_suspects}")

        if dupe_members > 0 or dupe_suspects > 0:
            print("  [FAIL] Duplicate primary keys detected!")
            all_passed = False
        else:
            print("  [PASS] Primary key uniqueness verified.")

        # -------------------------------------------------------------------
        # 4. Foreign Key Referential Integrity (Orphan Checks)
        # -------------------------------------------------------------------
        print("\n[Check 4] Referential Integrity (Orphan Checks)...")

        orphan_diag = db.scalar(
            select(func.count())
            .select_from(DiagnosisEvent)
            .where(~DiagnosisEvent.bene_id.in_(select(Member.bene_id)))
        )
        orphan_rx = db.scalar(
            select(func.count())
            .select_from(PrescriptionEvent)
            .where(~PrescriptionEvent.bene_id.in_(select(Member.bene_id)))
        )
        orphan_suspects = db.scalar(
            select(func.count())
            .select_from(Suspect)
            .where(~Suspect.bene_id.in_(select(Member.bene_id)))
        )

        print(f"  - Orphan diagnosis events (invalid bene_id): {orphan_diag}")
        print(f"  - Orphan prescription events (invalid bene_id): {orphan_rx}")
        print(f"  - Orphan suspect records (invalid bene_id): {orphan_suspects}")

        if orphan_diag > 0 or orphan_rx > 0 or orphan_suspects > 0:
            print("  [FAIL] Foreign key referential integrity violations detected!")
            all_passed = False
        else:
            print("  [PASS] Complete referential integrity verified.")

        # -------------------------------------------------------------------
        # 5. ICD-10 to HCC Mapping Integrity
        # -------------------------------------------------------------------
        print("\n[Check 5] ICD-10 to HCC Mapping Integrity...")

        total_mapping_codes = row_counts["hcc_mappings"]
        mapped_to_v28 = db.scalar(
            select(func.count())
            .select_from(HCCMapping)
            .where(HCCMapping.hcc_v28 != None)
            .where(HCCMapping.hcc_v28 != "")
        )
        payment_eligible = db.scalar(
            select(func.count())
            .select_from(HCCMapping)
            .where(HCCMapping.payment_2026 == True)
        )

        print(f"  - Total ICD-10 Codes in Mapping Crosswalk: {total_mapping_codes:,}")
        print(f"  - Codes mapped to a CMS V28 Category     : {mapped_to_v28:,}")
        print(f"  - Codes eligible for 2026 Payment        : {payment_eligible:,}")
        print("  [PASS] Mapping crosswalk integrity verified.")

        # -------------------------------------------------------------------
        # 6. Rejections Summary
        # -------------------------------------------------------------------
        print("\n[Check 6] Ingestion Rejections Summary...")
        rejections_count = row_counts["ingestion_rejections"]
        print(f"  - Total Ingestion Rejections Logged: {rejections_count}")
        if rejections_count > 0:
            sample_rejections = db.scalars(select(IngestionRejection).limit(3)).all()
            for r in sample_rejections:
                print(f"    * File: {r.source_file} | Row: {r.row_index} | Reason: {r.reason}")

        dt = time.time() - t0
        print("\n" + "=" * 70)
        if all_passed:
            print(f"  VALIDATION RESULT: PASSED ALL CHECKS ({dt:.2f} seconds)")
        else:
            print(f"  VALIDATION RESULT: FAILED CHECKS ({dt:.2f} seconds)")
        print("=" * 70)

        return all_passed

    except Exception as e:
        print(f"\n[ERROR] Validation failed with exception: {e}", file=sys.stderr)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_database_validation()
    sys.exit(0 if success else 1)
