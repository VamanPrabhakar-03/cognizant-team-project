"""Comprehensive Endpoint Test Suite.

Tests ALL 14 API endpoints in the application:
1.  GET  /
2.  GET  /health
3.  GET  /api/dashboard/metrics
4.  GET  /api/dashboard/hcc-distribution
5.  GET  /api/dashboard/score-distribution
6.  GET  /api/members
7.  GET  /api/members/{bene_id}
8.  GET  /api/members/{bene_id}/timeline
9.  POST /api/pipeline/batches
10. GET  /api/pipeline/runs/{run_id}
11. GET  /api/suspects
12. GET  /api/suspects/{suspect_id}
13. PATCH /api/suspects/{suspect_id}
14. POST /api/reviews
15. GET  /api/reviews
16. GET  /api/reviews/stats

Usage:
    cd backend
    python scripts/test_all_endpoints.py
"""

import csv
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

# Force local SQLite DB
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

DB_FILE = BACKEND_DIR / "endpoint_test.db"
if DB_FILE.exists():
    try:
        DB_FILE.unlink()
    except Exception:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from database.models import (
    Base, Member, HCCMapping, MemberTimeline, MemberHCCBaseline,
    PrescriptionEvent, Suspect, PipelineRun, ReviewDecision,
)
from database.session import engine, SessionLocal

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
    if not val or str(val).strip() in ("", "nan", "NONE", "NULL"):
        return None
    try:
        return datetime.strptime(str(val).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_bool(val):
    return str(val or "").strip().lower() in ("true", "yes", "1")


# 1. Create DB and load base data
print("=" * 64)
print("  COMPREHENSIVE API ENDPOINTS SUITE")
print("=" * 64)

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Load 50 members
with open(DATA_DIR / "members.csv", newline="", encoding="utf-8") as f:
    for idx, row in enumerate(csv.DictReader(f)):
        if idx >= 50:
            break
        db.add(Member(
            bene_id=row["bene_id"].strip(),
            birth_date=parse_date(row.get("birth_date")),
            sex=row.get("sex", "").strip() or None,
            state=row.get("state", "").strip() or None,
        ))
db.commit()

valid_members = [m.bene_id for m in db.query(Member.bene_id).all()]

# Load HCC mapping
seen_codes = set()
with open(DATA_DIR / "hcc_mapping.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        code = row["diagnosis_code"].strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        db.add(HCCMapping(
            diagnosis_code=code,
            description=row.get("description", "").strip() or None,
            hcc_v28=row.get("hcc_v28", "").strip() or None,
            payment_2026=parse_bool(row.get("payment_2026")),
        ))
db.commit()

# Load baselines
with open(DATA_DIR / "member_hcc_baseline.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        bene = row["bene_id"].strip()
        if bene in valid_members:
            db.add(MemberHCCBaseline(
                bene_id=bene,
                hcc_v28=row.get("hcc_v28", "").strip() or None,
                hcc_description=row.get("hcc_description", "").strip() or None,
                baseline_diagnosis_codes=row.get("baseline_diagnosis_codes", "").strip() or None,
                baseline_claim_count=int(float(row.get("baseline_claim_count", "0") or "0")),
                first_baseline_date=parse_date(row.get("first_baseline_date")),
                last_baseline_date=parse_date(row.get("last_baseline_date")),
                sources=row.get("sources", "").strip() or None,
            ))
db.commit()

# Load timeline events
with open(DATA_DIR / "member_timeline.csv", newline="", encoding="utf-8") as f:
    for idx, row in enumerate(csv.DictReader(f)):
        if idx >= 10000:
            break
        bene = row["bene_id"].strip()
        if bene in valid_members:
            db.add(MemberTimeline(
                event_id=row.get("event_id", "").strip() or None,
                bene_id=bene,
                event_date=parse_date(row.get("event_date")),
                event_type=row.get("event_type", "").strip() or None,
                code=row.get("code", "").strip() or None,
                hcc_v28=row.get("hcc_v28", "").strip() or None,
                source=row.get("source", "").strip() or None,
                claim_id=row.get("claim_id", "").strip() or None,
                is_principal=parse_bool(row.get("is_principal")) if row.get("is_principal") else None,
            ))
db.commit()
db.close()

# Start Server
import uvicorn
from main import app

server = uvicorn.Server(uvicorn.Config(
    app=app,
    host="127.0.0.1",
    port=8299,
    log_level="warning",
))

server_thread = threading.Thread(target=server.run, daemon=True)
server_thread.start()

for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:8199/health", timeout=1)
        break
    except Exception:
        time.sleep(0.3)


def http_req(url_path: str, method: str = "GET", payload: dict = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:8299{url_path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return 0, {"error": str(e)}


print(f"\n{INFO} Testing System Endpoints...")

# 1. GET /
code, res = http_req("/")
check("GET /", code == 200 and "docs" in res, f"HTTP {code}")

# 2. GET /health
code, res = http_req("/health")
check("GET /health", code == 200 and res.get("status") == "ok", f"HTTP {code}")

print(f"\n{INFO} Testing Pipeline Endpoint...")

# 3. POST /api/pipeline/batches
batch_payload = {
    "source_file": "test_batch.json",
    "source_system": "ENDPOINT_TEST",
    "claims": [
        {
            "bene_id": valid_members[0],
            "claim_id": "TEST_CLM_01",
            "claim_date": "2023-05-10",
            "diagnosis_code": "E119",
            "source": "INPATIENT",
            "is_principal": True,
        },
        {
            "bene_id": valid_members[1],
            "claim_id": "TEST_CLM_02",
            "claim_date": "2023-06-12",
            "diagnosis_code": "I509",
            "source": "CARRIER",
            "is_principal": False,
        },
    ]
}
code, res = http_req("/api/pipeline/batches", method="POST", payload=batch_payload)
check("POST /api/pipeline/batches", code == 201 and "run_id" in res, f"HTTP {code}")
run_id = res.get("run_id")

# 4. GET /api/pipeline/runs/{run_id}
if run_id:
    code, res = http_req(f"/api/pipeline/runs/{run_id}")
    check("GET /api/pipeline/runs/{run_id}", code == 200 and res.get("status") == "COMPLETED", f"HTTP {code}")

print(f"\n{INFO} Testing Dashboard Endpoints...")

# 5. GET /api/dashboard/metrics
code, res = http_req("/api/dashboard/metrics")
check("GET /api/dashboard/metrics", code == 200 and "total_members" in res, f"HTTP {code}")

# 6. GET /api/dashboard/hcc-distribution
code, res = http_req("/api/dashboard/hcc-distribution")
check("GET /api/dashboard/hcc-distribution", code == 200 and isinstance(res, list), f"HTTP {code}")

# 7. GET /api/dashboard/score-distribution
code, res = http_req("/api/dashboard/score-distribution")
check("GET /api/dashboard/score-distribution", code == 200 and "high" in res, f"HTTP {code}")

print(f"\n{INFO} Testing Members Endpoints...")

# 8. GET /api/members
code, res = http_req("/api/members?page=1&size=10")
check("GET /api/members", code == 200 and res.get("total", 0) > 0, f"HTTP {code}")

# 9. GET /api/members/{bene_id}
test_bene = valid_members[0]
code, res = http_req(f"/api/members/{test_bene}")
check("GET /api/members/{bene_id}", code == 200 and res.get("member", {}).get("bene_id") == test_bene, f"HTTP {code}")

# 10. GET /api/members/{bene_id}/timeline
code, res = http_req(f"/api/members/{test_bene}/timeline?page=1&size=5")
check("GET /api/members/{bene_id}/timeline", code == 200 and "items" in res, f"HTTP {code}")

print(f"\n{INFO} Testing Suspects Endpoints...")

# 11. GET /api/suspects
code, res = http_req("/api/suspects?page=1&size=10")
check("GET /api/suspects", code == 200 and "items" in res, f"HTTP {code}")
suspects_items = res.get("items", [])
sample_suspect_id = suspects_items[0]["suspect_id"] if suspects_items else None

if sample_suspect_id:
    # 12. GET /api/suspects/{suspect_id}
    code, res = http_req(f"/api/suspects/{sample_suspect_id}")
    check("GET /api/suspects/{suspect_id}", code == 200 and "suspect" in res, f"HTTP {code}")

    # 13. PATCH /api/suspects/{suspect_id}
    patch_payload = {"status": "REVIEWED"}
    code, res = http_req(f"/api/suspects/{sample_suspect_id}", method="PATCH", payload=patch_payload)
    check("PATCH /api/suspects/{suspect_id}", code == 200 and res.get("status") == "REVIEWED", f"HTTP {code}")

print(f"\n{INFO} Testing Reviews Endpoints...")

# 14. POST /api/reviews
if sample_suspect_id:
    review_payload = {
        "suspect_id": sample_suspect_id,
        "bene_id": test_bene,
        "hcc_v28": "38",
        "suspect_type": "EMERGING",
        "priority_score": 0.85,
        "decision": "SUPPORTED",
        "notes": "E2E automated validation review decision note.",
    }
    code, res = http_req("/api/reviews", method="POST", payload=review_payload)
    check("POST /api/reviews", code == 201 and res.get("decision") == "SUPPORTED", f"HTTP {code}")

# 15. GET /api/reviews
code, res = http_req("/api/reviews?page=1&size=10")
check("GET /api/reviews", code == 200 and "items" in res, f"HTTP {code}")

# 16. GET /api/reviews/stats
code, res = http_req("/api/reviews/stats")
check("GET /api/reviews/stats", code == 200 and "supported" in res, f"HTTP {code}")

print("\n" + "=" * 64)
passed = sum(results)
total = len(results)
failed = total - passed
if failed == 0:
    print(f"  \033[92mALL {total}/{total} API ENDPOINTS WORKING PERFECTLY!\033[0m")
else:
    print(f"  \033[91m{failed}/{total} API ENDPOINT CHECKS FAILED\033[0m")
print("=" * 64)

server.should_exit = True
if DB_FILE.exists():
    try:
        DB_FILE.unlink()
    except Exception:
        pass

sys.exit(0 if failed == 0 else 1)
