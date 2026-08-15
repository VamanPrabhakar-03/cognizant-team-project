"""Local End-to-End Pipeline Validation.

Creates a fresh SQLite database, loads a subset of production data,
starts the FastAPI server, submits a claims batch through the pipeline
endpoint, and verifies the full flow: ingestion → engine → suspects →
evidence → LLM review records.

Usage:
    cd backend
    python scripts/local_e2e_test.py
"""

import csv
import json
import os
import sys
import time
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Environment setup — force SQLite BEFORE any app imports
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

DB_FILE = BACKEND_DIR / "e2e_test.db"
if DB_FILE.exists():
    DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# Now import the app components
from database.models import (
    Base, Member, HCCMapping, MemberTimeline, MemberHCCBaseline,
    PrescriptionEvent, DiagnosisEvent, Suspect, PipelineRun,
    ClaimBatch, Claim, SuspectEvidence, LLMReview, IngestionRejection,
)
from database.session import engine, SessionLocal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
results = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  {status} {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append(condition)
    return condition


def parse_date(val):
    from datetime import datetime
    if not val or val.strip() in ("", "nan", "NONE", "NULL"):
        return None
    try:
        return datetime.strptime(val.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_bool(val):
    return str(val or "").strip().lower() in ("true", "yes", "1")


# ---------------------------------------------------------------------------
# 2. Create all tables
# ---------------------------------------------------------------------------

print("=" * 64)
print("  LOCAL END-TO-END PIPELINE VALIDATION")
print("=" * 64)

print(f"\n{INFO} Database: {DB_FILE}")
print(f"{INFO} Creating tables...")

Base.metadata.create_all(bind=engine)

table_names = list(Base.metadata.tables.keys())
check("Tables created", len(table_names) >= 12, f"{len(table_names)} tables")

# ---------------------------------------------------------------------------
# 3. Load base data subset
# ---------------------------------------------------------------------------

print(f"\n{INFO} Loading base data from CSVs...")

db = SessionLocal()

# 3a. Members — load first 200 for speed
member_count = 0
MEMBER_LIMIT = 200
with open(DATA_DIR / "members.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if member_count >= MEMBER_LIMIT:
            break
        db.add(Member(
            bene_id=row["bene_id"].strip(),
            birth_date=parse_date(row.get("birth_date")),
            sex=row.get("sex", "").strip() or None,
            race=row.get("race", "").strip() or None,
            state=row.get("state", "").strip() or None,
            county=row.get("county", "").strip() or None,
            zip=row.get("zip", "").strip() or None,
            esrd_indicator=row.get("esrd_indicator", "").strip() or None,
            death_date=parse_date(row.get("death_date")),
            enrollment_years=row.get("enrollment_years", "").strip() or None,
        ))
        member_count += 1
db.commit()
check("Members loaded", member_count > 0, f"{member_count} members")

# Collect valid bene_ids for filtering subsequent loads
valid_bene_ids = {m.bene_id for m in db.query(Member.bene_id).all()}

# 3b. HCC Mapping — load ALL (small file, ~12K rows), dedup by diagnosis_code
hcc_count = 0
seen_codes = set()
with open(DATA_DIR / "hcc_mapping.csv", newline="", encoding="utf-8") as f:
    batch = []
    for row in csv.DictReader(f):
        code = row["diagnosis_code"].strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        batch.append(HCCMapping(
            diagnosis_code=code,
            description=row.get("description", "").strip() or None,
            hcc_v28=row.get("hcc_v28", "").strip() or None,
            payment_2026=parse_bool(row.get("payment_2026")),
        ))
        hcc_count += 1
        if len(batch) >= 5000:
            db.add_all(batch)
            db.commit()
            batch = []
    if batch:
        db.add_all(batch)
        db.commit()
check("HCC mappings loaded", hcc_count > 0, f"{hcc_count} codes")

# 3c. Member HCC Baseline — only for our loaded members
baseline_count = 0
with open(DATA_DIR / "member_hcc_baseline.csv", newline="", encoding="utf-8") as f:
    batch = []
    for row in csv.DictReader(f):
        bene_id = row["bene_id"].strip()
        if bene_id not in valid_bene_ids:
            continue
        batch.append(MemberHCCBaseline(
            bene_id=bene_id,
            hcc_v28=row.get("hcc_v28", "").strip() or None,
            hcc_description=row.get("hcc_description", "").strip() or None,
            baseline_diagnosis_codes=row.get("baseline_diagnosis_codes", "").strip() or None,
            baseline_claim_count=int(float(row.get("baseline_claim_count", "0") or "0")),
            first_baseline_date=parse_date(row.get("first_baseline_date")),
            last_baseline_date=parse_date(row.get("last_baseline_date")),
            sources=row.get("sources", "").strip() or None,
        ))
        baseline_count += 1
        if len(batch) >= 5000:
            db.add_all(batch)
            db.commit()
            batch = []
    if batch:
        db.add_all(batch)
        db.commit()
check("Baselines loaded", baseline_count > 0, f"{baseline_count} records")

# 3d. Member Timeline — only for our loaded members, cap at 50K for speed
timeline_count = 0
TIMELINE_LIMIT = 50_000
with open(DATA_DIR / "member_timeline.csv", newline="", encoding="utf-8") as f:
    batch = []
    for row in csv.DictReader(f):
        if timeline_count >= TIMELINE_LIMIT:
            break
        bene_id = row["bene_id"].strip()
        if bene_id not in valid_bene_ids:
            continue
        batch.append(MemberTimeline(
            event_id=row.get("event_id", "").strip() or None,
            bene_id=bene_id,
            event_date=parse_date(row.get("event_date")),
            event_type=row.get("event_type", "").strip() or None,
            code=row.get("code", "").strip() or None,
            hcc_v28=row.get("hcc_v28", "").strip() or None,
            source=row.get("source", "").strip() or None,
            claim_id=row.get("claim_id", "").strip() or None,
            is_principal=parse_bool(row.get("is_principal")) if row.get("is_principal") else None,
        ))
        timeline_count += 1
        if len(batch) >= 10_000:
            db.add_all(batch)
            db.commit()
            batch = []
    if batch:
        db.add_all(batch)
        db.commit()
check("Timeline loaded", timeline_count > 0, f"{timeline_count} events")

# 3e. Prescriptions — only for loaded members
rx_count = 0
seen_rx_ids = set()
with open(DATA_DIR / "events_prescription.csv", newline="", encoding="utf-8") as f:
    batch = []
    for row in csv.DictReader(f):
        bene_id = row["bene_id"].strip()
        event_id = row.get("event_id", "").strip()
        if bene_id not in valid_bene_ids:
            continue
        if not event_id or event_id in seen_rx_ids:
            continue
        seen_rx_ids.add(event_id)
        batch.append(PrescriptionEvent(
            event_id=event_id,
            bene_id=bene_id,
            pde_id=row.get("pde_id", "").strip() or None,
            event_date=parse_date(row.get("event_date")),
            drug_code=row.get("drug_code", "").strip() or None,
        ))
        rx_count += 1
        if len(batch) >= 5000:
            db.add_all(batch)
            db.commit()
            batch = []
    if batch:
        db.add_all(batch)
        db.commit()
check("Prescriptions loaded", rx_count > 0, f"{rx_count} events")

db.close()

# ---------------------------------------------------------------------------
# 4. Build test claims payload from real data
# ---------------------------------------------------------------------------

print(f"\n{INFO} Building test claims batch from loaded members...")

# Pick members that have baseline data
db = SessionLocal()
baseline_members = (
    db.query(MemberHCCBaseline.bene_id, MemberHCCBaseline.hcc_v28)
    .limit(200)
    .all()
)

# Build a map of member -> set of baseline HCCs
from collections import defaultdict
member_baseline = defaultdict(set)
for row in baseline_members:
    if row.hcc_v28:
        member_baseline[row.bene_id].add(row.hcc_v28.strip())

test_bene_ids = list(member_baseline.keys())[:15]

# Build HCC -> list of diagnosis codes from hcc_mappings (only non-baseline HCCs)
all_hcc_codes = (
    db.query(HCCMapping.diagnosis_code, HCCMapping.hcc_v28)
    .filter(HCCMapping.hcc_v28.isnot(None), HCCMapping.hcc_v28 != "")
    .limit(5000)
    .all()
)
hcc_to_codes = defaultdict(list)
for row in all_hcc_codes:
    hcc_to_codes[row.hcc_v28.strip()].append(row.diagnosis_code.strip())

# All available HCCs
all_hcc_set = set(hcc_to_codes.keys())

test_claims = []
claim_counter = 0
for bene_id in test_bene_ids:
    baseline_hccs = member_baseline[bene_id]
    # Find HCCs NOT in this member's baseline -> will create EMERGING suspects
    novel_hccs = all_hcc_set - baseline_hccs
    selected_novel = sorted(novel_hccs)[:3]  # Pick up to 3 novel HCCs per member

    for hcc in selected_novel:
        codes = hcc_to_codes[hcc]
        diag_code = codes[0]  # Use first matching diagnosis code
        claim_counter += 1
        test_claims.append({
            "bene_id": bene_id,
            "claim_id": f"E2E_EMERGING_{claim_counter}",
            "claim_date": "2023-06-15",  # Fixed current-year date
            "diagnosis_code": diag_code,
            "source": "INPATIENT",
            "is_principal": claim_counter % 3 == 0,
        })

    # Also add a claim WITH a baseline HCC to test that RECAPTURE doesn't fire
    if baseline_hccs:
        baseline_hcc = sorted(baseline_hccs)[0]
        if baseline_hcc in hcc_to_codes:
            codes = hcc_to_codes[baseline_hcc]
            claim_counter += 1
            test_claims.append({
                "bene_id": bene_id,
                "claim_id": f"E2E_BASELINE_{claim_counter}",
                "claim_date": "2023-08-20",
                "diagnosis_code": codes[0],
                "source": "OUTPATIENT",
                "is_principal": True,
            })

# Add invalid claims to test rejection (valid format but unknown members)
test_claims.append({
    "bene_id": "NONEXISTENT_MEMBER_001",
    "claim_id": "E2E_INVALID_FK_1",
    "claim_date": "2023-01-01",
    "diagnosis_code": "Z99",
})
test_claims.append({
    "bene_id": "NONEXISTENT_MEMBER_002",
    "claim_id": "E2E_INVALID_FK_2",
    "claim_date": "2023-01-01",
    "diagnosis_code": "Z99",
})

db.close()

payload = {
    "source_file": "e2e_test_batch.csv",
    "source_system": "LOCAL_E2E_TEST",
    "claims": test_claims,
}

total_claims = len(test_claims)
print(f"  Prepared {total_claims} test claims ({total_claims - 2} valid + 2 invalid)")

# ---------------------------------------------------------------------------
# 5. Start FastAPI server in background thread
# ---------------------------------------------------------------------------

print(f"\n{INFO} Starting FastAPI server...")

import uvicorn
from main import app

server = uvicorn.Server(uvicorn.Config(
    app=app,
    host="127.0.0.1",
    port=8199,
    log_level="warning",
))

server_thread = threading.Thread(target=server.run, daemon=True)
server_thread.start()

# Wait for server to be ready
import urllib.request
import urllib.error

for attempt in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:8199/health", timeout=1)
        break
    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        time.sleep(0.5)
else:
    print(f"  {FAIL} Server did not start within 15 seconds")
    sys.exit(1)

check("FastAPI server started", True, "http://127.0.0.1:8199")

# ---------------------------------------------------------------------------
# 6. Submit claims batch via pipeline endpoint
# ---------------------------------------------------------------------------

print(f"\n{INFO} Submitting claims batch to POST /api/pipeline/batches ...")

req = urllib.request.Request(
    "http://127.0.0.1:8199/api/pipeline/batches",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        status_code = resp.status
        body = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    status_code = e.code
    body = json.loads(e.read().decode("utf-8"))
    print(f"  {FAIL} Pipeline returned HTTP {status_code}: {body}")

check("Pipeline returned 201", status_code == 201, f"HTTP {status_code}")

if status_code == 201:
    run_id = body.get("run_id", "")
    check("Run ID present", bool(run_id), run_id)
    check("Input rows counted", body.get("input_rows", 0) == total_claims,
          f"input_rows={body.get('input_rows')}")
    check("Rejections detected", body.get("rejected_rows", 0) >= 2,
          f"rejected_rows={body.get('rejected_rows')}")
    check("Claims inserted", body.get("inserted_rows", 0) > 0,
          f"inserted_rows={body.get('inserted_rows')}")
    check("Suspects created", body.get("suspects", 0) > 0,
          f"suspects={body.get('suspects')}")
    check("Evidence created", body.get("evidence", 0) > 0,
          f"evidence={body.get('evidence')}")
    check("LLM reviews created", body.get("llm_reviews", 0) > 0,
          f"llm_reviews={body.get('llm_reviews')}")

    # ------------------------------------------------------------------
    # 7. Verify database records directly
    # ------------------------------------------------------------------

    print(f"\n{INFO} Verifying database records...")

    db = SessionLocal()
    suspect_count = db.query(Suspect).count()
    evidence_count = db.query(SuspectEvidence).count()
    llm_count = db.query(LLMReview).count()
    claim_count = db.query(Claim).count()
    batch_count = db.query(ClaimBatch).count()
    run_count = db.query(PipelineRun).count()
    rejection_count = db.query(IngestionRejection).count()

    check("Suspects in DB", suspect_count > 0, f"{suspect_count} records")
    check("Evidence in DB", evidence_count > 0, f"{evidence_count} records")
    check("LLM reviews in DB", llm_count > 0, f"{llm_count} records")
    check("Claims in DB", claim_count > 0, f"{claim_count} records")
    check("Claim batch in DB", batch_count == 1, f"{batch_count} batches")
    check("Pipeline run in DB", run_count == 1, f"{run_count} runs")
    check("Rejections in DB", rejection_count >= 2, f"{rejection_count} rejections")

    # Verify run status
    run = db.query(PipelineRun).first()
    check("Run status COMPLETED", run.status == "COMPLETED", run.status)

    # Verify suspects have scores
    sample_suspect = db.query(Suspect).first()
    if sample_suspect:
        check("Suspect has priority_score", sample_suspect.priority_score > 0,
              f"score={sample_suspect.priority_score}")
        check("Suspect has evidence_summary", bool(sample_suspect.evidence_summary),
              (sample_suspect.evidence_summary or "")[:60])
        check("Suspect has reason_flags", bool(sample_suspect.reason_flags),
              str(sample_suspect.reason_flags)[:60] if sample_suspect.reason_flags else "")

    db.close()

    # ------------------------------------------------------------------
    # 8. Test read API endpoints
    # ------------------------------------------------------------------

    print(f"\n{INFO} Testing read API endpoints...")

    def api_get(path: str) -> dict:
        url = f"http://127.0.0.1:8199/api{path}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return {"status": resp.status, "body": json.loads(resp.read().decode("utf-8"))}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "body": json.loads(e.read().decode("utf-8"))}
        except Exception as e:
            return {"status": 0, "body": {"error": str(e)}}

    # GET /api/suspects
    r = api_get("/suspects")
    check("GET /suspects returns 200", r["status"] == 200)
    if r["status"] == 200:
        check("Suspects list non-empty", r["body"].get("total", 0) > 0,
              f"total={r['body'].get('total')}")

    # GET /api/dashboard/metrics
    r = api_get("/dashboard/metrics")
    check("GET /dashboard/metrics returns 200", r["status"] == 200)
    if r["status"] == 200:
        check("Dashboard shows members", r["body"].get("total_members", 0) > 0,
              f"members={r['body'].get('total_members')}")
        check("Dashboard shows suspects", r["body"].get("total_suspects", 0) > 0,
              f"suspects={r['body'].get('total_suspects')}")

    # GET /api/dashboard/score-distribution
    r = api_get("/dashboard/score-distribution")
    check("GET /dashboard/score-distribution returns 200", r["status"] == 200)

    # GET /api/members
    r = api_get("/members")
    check("GET /members returns 200", r["status"] == 200)
    if r["status"] == 200:
        check("Members list non-empty", r["body"].get("total", 0) > 0,
              f"total={r['body'].get('total')}")

    # GET /api/pipeline/runs/{run_id}
    r = api_get(f"/pipeline/runs/{run_id}")
    check("GET /pipeline/runs/{run_id} returns 200", r["status"] == 200)
    if r["status"] == 200:
        check("Run detail shows COMPLETED", r["body"].get("status") == "COMPLETED")

# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------

print("\n" + "=" * 64)
passed = sum(results)
total = len(results)
failed = total - passed
if failed == 0:
    print(f"  \033[92mLOCAL E2E VALIDATION: ALL {total} CHECKS PASSED\033[0m")
else:
    print(f"  \033[91mLOCAL E2E VALIDATION: {failed}/{total} CHECKS FAILED\033[0m")
print("=" * 64)

# Cleanup
server.should_exit = True
if DB_FILE.exists():
    try:
        DB_FILE.unlink()
    except PermissionError:
        pass

sys.exit(0 if failed == 0 else 1)
