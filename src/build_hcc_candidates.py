"""
Task 5 -- Build Baseline vs Current HCC Comparison

Reads (without modifying):
    data/mvp/diagnoses.csv
    data/mvp/hcc_mapping.csv

Produces:
    data/mvp/hcc_review_candidates.csv
    data/mvp/hcc_candidate_quality_report.md
    docs/hcc_review_candidate_logic.md

Logic:
    Historical baseline  : diagnosis_date in 2021-2022
    Current evidence     : diagnosis_date in 2023
    Candidate HCCs       : current_hcc_set - historical_hcc_set  (per member)

Note: The CMS-CTS source data covers 2015-2023. The task spec called for
2023-2024 (historical) and 2025 (current), but those years are not present
in the source files. Periods have been adapted to the latest available data.

A candidate is NOT a confirmed diagnosis.
It is a review opportunity for a human coder/clinician.

Single streaming pass over diagnoses.csv:
  - Rows with date in 2023-2024 -> historical accumulators
  - Rows with date in 2025       -> current accumulators
  - All other dates are ignored for this comparison
"""

import csv
import sys
from collections import defaultdict, Counter
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MVP_DIR      = PROJECT_ROOT / "data" / "mvp"
DOCS_DIR     = PROJECT_ROOT / "docs"

DIAGNOSES_CSV  = MVP_DIR / "diagnoses.csv"
HCC_MAPPING_CSV = MVP_DIR / "hcc_mapping.csv"

OUT_CANDIDATES   = MVP_DIR / "hcc_review_candidates.csv"
OUT_QUALITY      = MVP_DIR / "hcc_candidate_quality_report.md"
OUT_DOC          = DOCS_DIR / "hcc_review_candidate_logic.md"

CHUNK_SIZE = 100_000

HISTORICAL_YEARS = {"2021", "2022"}
CURRENT_YEAR     = "2023"

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_hcc_mapping(path: Path) -> dict:
    """
    Returns {diagnosis_code -> {"hcc_v28": str, "payment_2026": str}}
    Mirrors the logic used in build_hcc_profile.py exactly.
    """
    mapping = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["diagnosis_code"].strip()
            hcc  = row.get("hcc_v28", "").strip()
            pay  = row.get("payment_2026", "").strip().lower()
            mapping[code] = {
                "hcc_v28":      hcc,
                "payment_2026": "Yes" if pay in ("true", "yes", "1") else "No",
            }
    print(f"  Loaded {len(mapping):,} HCC mapping entries")
    return mapping


def _year(date_str: str) -> str:
    """Extract 4-character year from a YYYY-MM-DD date string, or '' if invalid."""
    s = date_str.strip() if date_str else ""
    return s[:4] if len(s) >= 4 else ""


def _min_date(a: str, b: str) -> str:
    if not a: return b
    if not b: return a
    return a if a <= b else b


def _max_date(a: str, b: str) -> str:
    if not a: return b
    if not b: return a
    return a if a >= b else b


# ── Single streaming pass ──────────────────────────────────────────────────────
#
# For each member we accumulate two dicts keyed by hcc_v28:
#
#   hist[member_id][hcc_v28] = set of ICD-10 codes
#   curr[member_id][hcc_v28] = {
#       "codes":      set of ICD-10 codes,
#       "claim_ids":  set of claim_ids,
#       "first_date": str,
#       "last_date":  str,
#       "count":      int,
#   }
#
# We also track quality counters.

def streaming_pass(hcc_mapping: dict) -> dict:
    """
    Single pass over diagnoses.csv.
    Returns stats dict with all accumulators.
    """
    # Historical: member_id -> set of hcc_v28
    hist_hcc:  dict = defaultdict(set)

    # Current: member_id -> hcc_v28 -> evidence dict
    curr_hcc:  dict = defaultdict(lambda: defaultdict(lambda: {
        "codes":      set(),
        "claim_ids":  set(),
        "first_date": "",
        "last_date":  "",
        "count":      0,
    }))

    # Quality counters
    total_rows   = 0
    hist_rows    = 0
    curr_rows    = 0
    other_rows   = 0
    all_members  = set()

    chunk_num = 0
    buf = []

    with open(DIAGNOSES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            buf.append(row)
            if len(buf) >= CHUNK_SIZE:
                _process_chunk(buf, hcc_mapping,
                               hist_hcc, curr_hcc, all_members)
                total_rows += len(buf)
                hist_rows  += sum(1 for r in buf if _year(r.get("diagnosis_date","")) in HISTORICAL_YEARS)
                curr_rows  += sum(1 for r in buf if _year(r.get("diagnosis_date","")) == CURRENT_YEAR)
                other_rows += sum(1 for r in buf
                                  if _year(r.get("diagnosis_date","")) not in HISTORICAL_YEARS
                                  and _year(r.get("diagnosis_date","")) != CURRENT_YEAR)
                buf = []
                chunk_num += 1
                if chunk_num % 10 == 0:
                    print(f"    ... processed {total_rows:,} rows", flush=True)

        if buf:
            _process_chunk(buf, hcc_mapping, hist_hcc, curr_hcc, all_members)
            total_rows += len(buf)
            hist_rows  += sum(1 for r in buf if _year(r.get("diagnosis_date","")) in HISTORICAL_YEARS)
            curr_rows  += sum(1 for r in buf if _year(r.get("diagnosis_date","")) == CURRENT_YEAR)
            other_rows += sum(1 for r in buf
                              if _year(r.get("diagnosis_date","")) not in HISTORICAL_YEARS
                              and _year(r.get("diagnosis_date","")) != CURRENT_YEAR)

    print(f"  Streamed {total_rows:,} rows total")
    print(f"    Historical (2023-2024): {hist_rows:,} rows")
    print(f"    Current    (2025):      {curr_rows:,} rows")
    print(f"    Other years (ignored):  {other_rows:,} rows")

    return {
        "hist_hcc":    hist_hcc,
        "curr_hcc":    curr_hcc,
        "all_members": all_members,
        "total_rows":  total_rows,
        "hist_rows":   hist_rows,
        "curr_rows":   curr_rows,
        "other_rows":  other_rows,
    }


def _process_chunk(chunk, hcc_mapping, hist_hcc, curr_hcc, all_members):
    for row in chunk:
        mid      = row["member_id"].strip()
        code     = row["diagnosis_code"].strip()
        date_str = row.get("diagnosis_date", "").strip()
        claim_id = row.get("claim_id", "").strip()
        yr       = _year(date_str)

        all_members.add(mid)

        info = hcc_mapping.get(code, {})
        hcc  = info.get("hcc_v28", "")
        if not hcc:
            continue   # unmapped — skip for both periods

        if yr in HISTORICAL_YEARS:
            hist_hcc[mid].add(hcc)

        elif yr == CURRENT_YEAR:
            ev = curr_hcc[mid][hcc]
            ev["codes"].add(code)
            if claim_id:
                ev["claim_ids"].add(claim_id)
            ev["first_date"] = _min_date(ev["first_date"], date_str)
            ev["last_date"]  = _max_date(ev["last_date"],  date_str)
            ev["count"]     += 1


# ── Step 3 — Compute candidates ────────────────────────────────────────────────

def compute_candidates(hist_hcc: dict, curr_hcc: dict, all_members: set) -> list:
    """
    For each member:  candidates = curr_hcc_set - hist_hcc_set
    Returns list of candidate dicts.
    """
    candidates = []
    for mid in sorted(all_members):
        historical = hist_hcc.get(mid, set())
        current    = curr_hcc.get(mid, {})

        for hcc, ev in current.items():
            if hcc not in historical:
                candidates.append({
                    "member_id":                  mid,
                    "hcc_v28":                    hcc,
                    "supporting_diagnosis_codes": "|".join(sorted(ev["codes"])),
                    "supporting_claim_ids":       "|".join(sorted(ev["claim_ids"])),
                    "evidence_count":             ev["count"],
                    "first_evidence_date":        ev["first_date"],
                    "last_evidence_date":         ev["last_date"],
                    "status":                     "PENDING_REVIEW",
                })

    print(f"  Candidates identified: {len(candidates):,}")
    return candidates


# ── Step 5 — Write candidates CSV ─────────────────────────────────────────────

def write_candidates(candidates: list):
    cols = [
        "member_id", "hcc_v28", "supporting_diagnosis_codes",
        "supporting_claim_ids", "evidence_count",
        "first_evidence_date", "last_evidence_date", "status",
    ]
    with open(OUT_CANDIDATES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(candidates)
    size_kb = OUT_CANDIDATES.stat().st_size / 1024
    print(f"  Written: {OUT_CANDIDATES.name} ({size_kb:.1f} KB, {len(candidates):,} rows)")


# ── Quality Report ─────────────────────────────────────────────────────────────

def write_quality_report(stats: dict, candidates: list):
    hist_hcc   = stats["hist_hcc"]
    curr_hcc   = stats["curr_hcc"]
    all_members = stats["all_members"]

    members_analyzed      = len(all_members)
    hist_member_hcc_count = sum(len(v) for v in hist_hcc.values())
    curr_member_hcc_count = sum(len(v) for v in curr_hcc.values())
    members_with_cands    = len({c["member_id"] for c in candidates})

    # Candidates by HCC
    cand_by_hcc: Counter = Counter(c["hcc_v28"] for c in candidates)

    # Candidates with multiple supporting occurrences
    multi_support = sum(1 for c in candidates if c["evidence_count"] >= 2)

    lines = [
        "# HCC Review Candidate Quality Report",
        "",
        "---",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Members analyzed | {members_analyzed:,} |",
        f"| Historical diagnosis rows (2023-2024) | {stats['hist_rows']:,} |",
        f"| Current diagnosis rows (2025) | {stats['curr_rows']:,} |",
        f"| Rows in other years (ignored) | {stats['other_rows']:,} |",
        f"| Historical (member, HCC) pairs | {hist_member_hcc_count:,} |",
        f"| Current (member, HCC) pairs | {curr_member_hcc_count:,} |",
        f"| Total review candidates | {len(candidates):,} |",
        f"| Unique members with candidates | {members_with_cands:,} |",
        f"| Candidates with ≥2 supporting occurrences | {multi_support:,} |",
        "",
        "---",
        "",
        "## Candidates by HCC Category",
        "",
        "| HCC V28 | Candidate Count |",
        "|---|---|",
    ]
    for hcc, cnt in sorted(cand_by_hcc.items(), key=lambda x: -x[1]):
        lines.append(f"| {hcc} | {cnt:,} |")

    lines += [
        "",
        "---",
        "",
        "> **Reminder:** A candidate signals that a 2025 diagnosis maps to an HCC",
        "> not seen in the 2023-2024 baseline. It is NOT a confirmed diagnosis,",
        "> documentation gap, or coding error. Human clinical review is required.",
    ]

    with open(OUT_QUALITY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {OUT_QUALITY.name}")


# ── Documentation ──────────────────────────────────────────────────────────────

DOCUMENTATION = """\
# HCC Review Candidate Logic — Documentation

## Overview

This document describes the prototype rule-based mechanism that surfaces
**HCC review opportunities** for a Medicare Advantage population.

It is NOT an automated coding system, diagnosis engine, or risk score calculator.
Every candidate must be reviewed and confirmed by a qualified human reviewer
before any action is taken.

---

## 1. Baseline Period

**Years: 2021 and 2022**

All diagnosis records with a `diagnosis_date` in 2021 or 2022 are used to build
the member's **historical documented HCC set** — the set of CMS HCC V28 categories
supported by prior claims in those two years.

> Note: The task specification called for 2023-2024 as the baseline and 2025 as
> the current period. The CMS-CTS source data available covers 2015-2023 only.
> Periods have been adapted to use the most recent two full years (2021-2022) as
> the baseline and 2023 as the current evidence year.

---

## 2. Current Evidence Period

**Year: 2023**

All diagnosis records with a `diagnosis_date` in 2023 are used to build the
member's **current HCC signal set** — HCC categories supported by recent claims.

---

## 3. ICD-10 → V28 Mapping

The same `hcc_mapping.csv` file used to build `member_hcc_profile.csv` is used
here. It is the CMS 2026 Final ICD-10-CM Mappings crosswalk.

- Only codes with a non-empty `hcc_v28` field are considered.
- No other HCC models (V24, ESRD, etc.) are used.
- No inference, fuzzy matching, or interpolation is performed.

---

## 4. Comparison Logic

For each member:

```
candidate_hccs = current_hcc_set (2025) - historical_hcc_set (2023-2024)
```

Each HCC in `candidate_hccs` is a **review opportunity**: a recent diagnosis
maps to an HCC category that was not documented in the prior two years.

Members with no 2025 diagnosis data will have no candidates.
Members with no historical baseline will have all 2025 HCCs flagged
(conservative — everything is "new" relative to an empty baseline).

---

## 5. Evidence Fields

Each candidate record contains:

| Field | Description |
|---|---|
| `member_id` | Member identifier |
| `hcc_v28` | CMS HCC V28 category number |
| `supporting_diagnosis_codes` | Pipe-delimited ICD-10 codes driving this candidate |
| `supporting_claim_ids` | Pipe-delimited claim IDs where evidence was found |
| `evidence_count` | Number of diagnosis records supporting this candidate in 2025 |
| `first_evidence_date` | Earliest 2025 date this HCC was seen |
| `last_evidence_date` | Latest 2025 date this HCC was seen |
| `status` | Initially `PENDING_REVIEW` |

---

## 6. Candidate Definition

A **candidate** is a (member, HCC V28) pair where:

1. At least one 2025 diagnosis code maps to that HCC under V28, AND
2. No 2023-2024 diagnosis code mapped to that HCC for the same member.

A candidate does **not** mean:
- The member definitely has the condition.
- A coding error was made.
- A documentation gap exists.
- Any action is required.

---

## 7. Human-Review Requirement

All candidates have `status = PENDING_REVIEW`.

Before any status change, a qualified reviewer (clinical coder, nurse, or
physician) must:

1. Examine the supporting diagnosis codes and claim context.
2. Review the member's full medical record.
3. Determine whether the condition is active, properly documented, and
   appropriate for coding.

This system does **not** approve, reject, or modify any diagnosis or claim.

---

## 8. Limitations

- **No recency within 2025**: All 2025 evidence is treated equally regardless
  of month. A January diagnosis and a December diagnosis are weighted the same.
- **Binary baseline**: A code seen once in 2023 counts the same as one seen
  100 times. Future versions may require a minimum count threshold.
- **No clinical context**: The system cannot distinguish a resolved acute
  condition from a chronic one.
- **No comorbidity logic**: HCCs are evaluated independently; co-occurring
  conditions are not considered.
- **No member eligibility check**: Members without a full year of 2025 coverage
  may have fewer diagnoses and artificially fewer candidates.
- **Prototype only**: This is an MVP demonstration. Production use requires
  clinical validation, compliance review, and regulatory approval.
"""


def write_documentation():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DOC, "w", encoding="utf-8") as f:
        f.write(DOCUMENTATION)
    print(f"  Written: {OUT_DOC.name}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Task 5 -- Baseline vs Current HCC Comparison")
    print("=" * 60)

    for p in [DIAGNOSES_CSV, HCC_MAPPING_CSV]:
        if not p.exists():
            print(f"ERROR: Missing required input: {p}", file=sys.stderr)
            sys.exit(1)

    MVP_DIR.mkdir(parents=True, exist_ok=True)

    # Load HCC mapping dict
    print("\n[Init] Loading HCC mapping...")
    hcc_mapping = load_hcc_mapping(HCC_MAPPING_CSV)

    # Single streaming pass
    print(f"[Step 1+2] Streaming diagnoses.csv (historical=2021-2022, current=2023)...")
    stats = streaming_pass(hcc_mapping)

    # Compute candidates
    print("\n[Step 3] Computing review candidates (current - historical)...")
    candidates = compute_candidates(stats["hist_hcc"], stats["curr_hcc"], stats["all_members"])

    # Write outputs
    print("\n[Step 5] Writing hcc_review_candidates.csv...")
    write_candidates(candidates)

    print("\n[Quality] Writing quality report...")
    write_quality_report(stats, candidates)

    print("\n[Docs] Writing hcc_review_candidate_logic.md...")
    write_documentation()

    print("\n" + "=" * 60)
    print("DONE. Output files:")
    for p in [OUT_CANDIDATES, OUT_QUALITY, OUT_DOC]:
        size_kb = p.stat().st_size / 1024 if p.exists() else 0
        print(f"  {p.relative_to(PROJECT_ROOT)}  ({size_kb:.1f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
