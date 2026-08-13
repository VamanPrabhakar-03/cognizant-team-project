"""
Task 4 -- Create Member -> ICD-10 -> HCC Profile

Reads (without modifying):
    data/mvp/diagnoses.csv
    data/mvp/hcc_mapping.csv

Produces:
    data/mvp/member_diagnosis_hcc.csv   — diagnosis-level mapping
    data/mvp/member_hcc_profile.csv     — one row per member + HCC
    data/mvp/unmapped_diagnoses.csv     — ICD-10 codes with no HCC mapping
    data/mvp/hcc_profile_quality_report.md
    docs/member_hcc_profile.md

Design: single streaming pass over diagnoses.csv (potentially very large).
hcc_mapping.csv is loaded fully into a dict (~12k rows, fits in RAM).
member_diagnosis_hcc.csv is written in appended chunks.
HCC profile and unmapped counts are accumulated in-memory dicts then flushed.
"""

import csv
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MVP_DIR      = PROJECT_ROOT / "data" / "mvp"
DOCS_DIR     = PROJECT_ROOT / "docs"

DIAGNOSES_CSV         = MVP_DIR / "diagnoses.csv"
HCC_MAPPING_CSV       = MVP_DIR / "hcc_mapping.csv"
OUT_DIAG_HCC          = MVP_DIR / "member_diagnosis_hcc.csv"
OUT_HCC_PROFILE       = MVP_DIR / "member_hcc_profile.csv"
OUT_UNMAPPED          = MVP_DIR / "unmapped_diagnoses.csv"
OUT_QUALITY_REPORT    = MVP_DIR / "hcc_profile_quality_report.md"
OUT_DOC               = DOCS_DIR / "member_hcc_profile.md"

CHUNK_SIZE = 100_000  # rows per streaming chunk

# ── Helpers ────────────────────────────────────────────────────────────────────

def _bool_to_yes_no(value: str) -> str:
    """Convert 'True'/'False'/''/nan-like strings to 'Yes'/'No'/''."""
    v = str(value).strip().lower()
    if v in ("true", "yes", "1"):
        return "Yes"
    if v in ("false", "no", "0"):
        return "No"
    return ""


def _safe_date(value: str) -> str:
    """Return the date string as-is if non-empty, else ''."""
    return str(value).strip() if value and str(value).strip() not in ("", "nan") else ""


def _min_date(a: str, b: str) -> str:
    """Return the earlier of two date strings (YYYY-MM-DD). Empty string is treated as 'infinity'."""
    if not a:
        return b
    if not b:
        return a
    return a if a <= b else b


def _max_date(a: str, b: str) -> str:
    """Return the later of two date strings (YYYY-MM-DD). Empty string is treated as '-infinity'."""
    if not a:
        return b
    if not b:
        return a
    return a if a >= b else b


# ── Step 1 — Load HCC mapping into dict ───────────────────────────────────────

def load_hcc_mapping(path: Path) -> dict:
    """
    Returns dict: {diagnosis_code (str) -> {"hcc_v28": str, "payment_2026": str}}
    hcc_v28 is '' when unmapped.
    payment_2026 is 'Yes' or 'No'.
    """
    mapping = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = str(row["diagnosis_code"]).strip()
            hcc  = str(row.get("hcc_v28", "")).strip()
            pay  = _bool_to_yes_no(row.get("payment_2026", ""))
            mapping[code] = {"hcc_v28": hcc, "payment_2026": pay}
    print(f"  Loaded {len(mapping):,} entries from hcc_mapping.csv")
    return mapping


# ── Step 3+4+5 — Single streaming pass ────────────────────────────────────────

def streaming_pass(hcc_mapping: dict):
    """
    Stream diagnoses.csv in chunks.

    Simultaneously:
      - Write member_diagnosis_hcc.csv (append per chunk)
      - Accumulate member_hcc_profile in memory dict
      - Accumulate unmapped_diagnoses Counter
      - Collect quality counters

    Returns quality stats dict.
    """

    # Profile: key=(member_id, hcc_v28), value=dict of accumulators
    hcc_profile: dict = defaultdict(lambda: {
        "count": 0,
        "codes": set(),
        "first_date": "",
        "last_date": "",
        "payment_2026": "",
    })

    unmapped_counter: Counter = Counter()

    # Quality counters
    total_rows        = 0
    mapped_rows       = 0
    unmapped_rows     = 0
    unique_codes      = set()
    unique_hccs       = set()
    member_with_hcc   = set()
    all_members       = set()

    # Open output file — write header first, then append chunks
    diag_hcc_cols = ["member_id", "diagnosis_code", "hcc_v28",
                     "payment_2026", "diagnosis_date", "is_principal"]

    with open(OUT_DIAG_HCC, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=diag_hcc_cols)
        writer.writeheader()

        chunk_num = 0
        with open(DIAGNOSES_CSV, newline="", encoding="utf-8") as in_fh:
            reader = csv.DictReader(in_fh)

            chunk_rows = []
            for row in reader:
                total_rows += 1

                member_id      = str(row.get("member_id", "")).strip()
                diag_code      = str(row.get("diagnosis_code", "")).strip()
                diag_date      = _safe_date(row.get("diagnosis_date", ""))
                is_principal   = str(row.get("is_principal", "")).strip()

                all_members.add(member_id)
                unique_codes.add(diag_code)

                # Look up HCC
                hcc_info = hcc_mapping.get(diag_code)

                if hcc_info:
                    hcc_v28     = hcc_info["hcc_v28"]    # '' if unmapped
                    payment_26  = hcc_info["payment_2026"]
                else:
                    hcc_v28    = ""
                    payment_26 = ""

                # Track mapped vs unmapped
                if hcc_v28:
                    mapped_rows += 1
                    unique_hccs.add(hcc_v28)
                    member_with_hcc.add(member_id)

                    # Accumulate profile
                    key = (member_id, hcc_v28)
                    prof = hcc_profile[key]
                    prof["count"]        += 1
                    prof["codes"].add(diag_code)
                    prof["first_date"]    = _min_date(prof["first_date"], diag_date)
                    prof["last_date"]     = _max_date(prof["last_date"], diag_date)
                    prof["payment_2026"]  = payment_26  # stable per HCC
                else:
                    unmapped_rows += 1
                    unmapped_counter[diag_code] += 1

                # Build output row
                chunk_rows.append({
                    "member_id":       member_id,
                    "diagnosis_code":  diag_code,
                    "hcc_v28":         hcc_v28,
                    "payment_2026":    payment_26 if hcc_v28 else "No",
                    "diagnosis_date":  diag_date,
                    "is_principal":    is_principal,
                })

                # Flush chunk
                if len(chunk_rows) >= CHUNK_SIZE:
                    writer.writerows(chunk_rows)
                    chunk_num += 1
                    chunk_rows = []
                    if chunk_num % 10 == 0:
                        print(f"    ... processed {total_rows:,} rows", flush=True)

            # Flush remaining rows
            if chunk_rows:
                writer.writerows(chunk_rows)

    print(f"  member_diagnosis_hcc.csv written ({total_rows:,} rows total)")

    return {
        "total_rows":      total_rows,
        "mapped_rows":     mapped_rows,
        "unmapped_rows":   unmapped_rows,
        "unique_codes":    unique_codes,
        "unique_hccs":     unique_hccs,
        "member_with_hcc": member_with_hcc,
        "all_members":     all_members,
        "hcc_profile":     hcc_profile,
        "unmapped_counter": unmapped_counter,
    }


# ── Step 4 — Write member_hcc_profile.csv ─────────────────────────────────────

def write_hcc_profile(hcc_profile: dict):
    cols = ["member_id", "hcc_v28", "supporting_diagnosis_count",
            "unique_diagnosis_codes", "first_diagnosis_date",
            "last_diagnosis_date", "payment_2026"]

    with open(OUT_HCC_PROFILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for (member_id, hcc_v28), prof in sorted(hcc_profile.items()):
            writer.writerow({
                "member_id":                  member_id,
                "hcc_v28":                    hcc_v28,
                "supporting_diagnosis_count": prof["count"],
                "unique_diagnosis_codes":     "|".join(sorted(prof["codes"])),
                "first_diagnosis_date":       prof["first_date"],
                "last_diagnosis_date":        prof["last_date"],
                "payment_2026":               prof["payment_2026"],
            })
    print(f"  member_hcc_profile.csv written ({len(hcc_profile):,} rows)")


# ── Step 5 — Write unmapped_diagnoses.csv ─────────────────────────────────────

def write_unmapped(unmapped_counter: Counter):
    with open(OUT_UNMAPPED, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["diagnosis_code", "occurrence_count"])
        writer.writeheader()
        for code, count in unmapped_counter.most_common():
            writer.writerow({"diagnosis_code": code, "occurrence_count": count})
    print(f"  unmapped_diagnoses.csv written ({len(unmapped_counter):,} unique codes)")


# ── Step 6 — Write quality report ─────────────────────────────────────────────

def write_quality_report(stats: dict, hcc_profile: dict, unmapped_counter: Counter):
    total_rows      = stats["total_rows"]
    mapped_rows     = stats["mapped_rows"]
    unmapped_rows   = stats["unmapped_rows"]
    unique_codes    = stats["unique_codes"]
    unique_hccs     = stats["unique_hccs"]
    member_with_hcc = stats["member_with_hcc"]
    all_members     = stats["all_members"]

    members_no_hcc = all_members - member_with_hcc

    # Top HCC categories by member count
    hcc_member_count: Counter = Counter()
    for (member_id, hcc_v28) in hcc_profile.keys():
        hcc_member_count[hcc_v28] += 1

    top_hccs = hcc_member_count.most_common(15)

    # Top unmapped codes
    top_unmapped = unmapped_counter.most_common(15)

    pct_mapped   = (mapped_rows   / total_rows * 100) if total_rows else 0
    pct_unmapped = (unmapped_rows / total_rows * 100) if total_rows else 0

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# HCC Profile Quality Report",
        f"",
        f"Generated: {now}",
        f"",
        f"---",
        f"",
        f"## Diagnosis Row Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total diagnosis rows processed | {total_rows:,} |",
        f"| Rows with V28 HCC mapping | {mapped_rows:,} ({pct_mapped:.1f}%) |",
        f"| Rows without V28 HCC mapping | {unmapped_rows:,} ({pct_unmapped:.1f}%) |",
        f"| Unique ICD-10 codes seen | {len(unique_codes):,} |",
        f"| Unique mapped HCC categories | {len(unique_hccs):,} |",
        f"",
        f"---",
        f"",
        f"## Member Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total unique members | {len(all_members):,} |",
        f"| Members with ≥1 HCC mapped | {len(member_with_hcc):,} |",
        f"| Members with no mapped HCC | {len(members_no_hcc):,} |",
        f"",
        f"---",
        f"",
        f"## Top 15 HCC Categories by Member Count",
        f"",
        f"| HCC V28 | Member Count |",
        f"|---|---|",
    ]
    for hcc, cnt in top_hccs:
        lines.append(f"| {hcc} | {cnt:,} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Top 15 Unmapped ICD-10 Codes",
        f"",
        f"| Diagnosis Code | Occurrence Count |",
        f"|---|---|",
    ]
    for code, cnt in top_unmapped:
        lines.append(f"| {code} | {cnt:,} |")

    lines += [
        f"",
        f"---",
        f"",
        f"> **Note:** Unmapped codes are valid ICD-10 diagnoses that do not map to a",
        f"> CMS HCC V28 category under the 2026 payment model. They are preserved in",
        f"> `diagnoses.csv` and tracked in `unmapped_diagnoses.csv`.",
    ]

    with open(OUT_QUALITY_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  hcc_profile_quality_report.md written")


# ── Documentation ──────────────────────────────────────────────────────────────

DOCUMENTATION = """\
# Member HCC Profile — Documentation

## 1. Purpose

This dataset provides a **member-level HCC (Hierarchical Condition Category) profile**
derived from documented ICD-10 diagnosis codes in the MVP claims data.

It answers: *"Which CMS HCC V28 categories are supported by existing claims for each member?"*

It does **not**:
- Calculate risk scores
- Identify gaps or suspects
- Make clinical inferences
- Use machine learning or LLMs

---

## 2. Input Datasets

| File | Description |
|---|---|
| `data/mvp/diagnoses.csv` | Claim-level diagnosis records for 5,000 members |
| `data/mvp/hcc_mapping.csv` | CMS 2026 ICD-10-CM → HCC V28 crosswalk (11,870 codes) |

---

## 3. ICD-10 → HCC Mapping Logic

1. Load `hcc_mapping.csv` fully into memory as a lookup dict keyed by `diagnosis_code`.
2. For each row in `diagnoses.csv`, perform an exact string match on `diagnosis_code`.
3. If matched, extract `hcc_v28` and `payment_2026` from the mapping entry.
4. Only the **V28 model** is used. No other HCC models (V24, ESRD, etc.) are consulted.
5. No inference, interpolation, or fuzzy matching is performed.

---

## 4. Handling of Unmapped Codes

An ICD-10 code is considered **unmapped** when:
- It does not appear in `hcc_mapping.csv`, **or**
- It appears in `hcc_mapping.csv` but has an empty `hcc_v28` field (CMS knows the code
  but it does not map to an HCC payment category under V28).

Unmapped codes are:
- Kept as-is in `member_diagnosis_hcc.csv` with empty `hcc_v28` and `payment_2026=No`
- Counted in `unmapped_diagnoses.csv`
- **Not** assigned to any HCC category
- **Not** removed from the dataset

---

## 5. Aggregation Logic (member_hcc_profile.csv)

For each unique `(member_id, hcc_v28)` pair:

| Column | Logic |
|---|---|
| `supporting_diagnosis_count` | Count of all diagnosis rows mapping to this HCC for this member |
| `unique_diagnosis_codes` | Pipe-separated sorted list of distinct ICD-10 codes supporting this HCC |
| `first_diagnosis_date` | Earliest `diagnosis_date` among supporting rows |
| `last_diagnosis_date` | Latest `diagnosis_date` among supporting rows |
| `payment_2026` | `Yes` if the HCC is payment-eligible in 2026 (stable per HCC category) |

Rows with an empty `hcc_v28` are **excluded** from the profile.

---

## 6. Output Columns

### member_diagnosis_hcc.csv

| Column | Type | Description |
|---|---|---|
| `member_id` | string | Member identifier |
| `diagnosis_code` | string | ICD-10-CM code (no dots) |
| `hcc_v28` | string | CMS HCC V28 category number, or empty if unmapped |
| `payment_2026` | string | `Yes` / `No` — 2026 payment eligibility |
| `diagnosis_date` | date | Date the diagnosis was recorded |
| `is_principal` | boolean | Whether this was the principal diagnosis on the claim |

### member_hcc_profile.csv

| Column | Type | Description |
|---|---|---|
| `member_id` | string | Member identifier |
| `hcc_v28` | string | CMS HCC V28 category number |
| `supporting_diagnosis_count` | integer | Number of diagnosis records supporting this HCC |
| `unique_diagnosis_codes` | string | Pipe-delimited ICD-10 codes supporting this HCC |
| `first_diagnosis_date` | date | Earliest date this HCC was documented |
| `last_diagnosis_date` | date | Latest date this HCC was documented |
| `payment_2026` | string | `Yes` / `No` |

### unmapped_diagnoses.csv

| Column | Type | Description |
|---|---|---|
| `diagnosis_code` | string | ICD-10-CM code with no V28 HCC mapping |
| `occurrence_count` | integer | Number of times this code appeared in diagnoses |

---

## 7. Quality Checks

See `data/mvp/hcc_profile_quality_report.md` for:
- Total diagnosis rows processed
- Rows with / without V28 mapping
- Unique ICD-10 codes and HCC categories
- Members with / without at least one HCC
- Top HCC categories by member count
- Top unmapped diagnosis codes

---

## 8. Limitations

- **Snapshot only**: Reflects diagnoses in the MVP dataset. Real-world gaps are not modelled.
- **No recency weighting**: A diagnosis from 2010 and 2025 are treated equally in the profile.
- **No clinical validation**: HCC assignment is purely based on ICD-10 → CMS crosswalk lookups.
- **V28 model only**: Codes that map to other CMS models (V24, ESRD) but not V28 appear as unmapped.
- **No risk score**: This profile is an input to, not a substitute for, a risk score calculation.
"""


def write_documentation():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DOC, "w", encoding="utf-8") as f:
        f.write(DOCUMENTATION)
    print(f"  docs/member_hcc_profile.md written")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Task 4 -- Member -> ICD-10 -> HCC Profile")
    print("=" * 60)

    # Validate inputs
    for path in [DIAGNOSES_CSV, HCC_MAPPING_CSV]:
        if not path.exists():
            print(f"ERROR: Required input not found: {path}", file=sys.stderr)
            sys.exit(1)

    MVP_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1 — Load mapping
    print("\n[Step 1] Loading HCC mapping...")
    hcc_mapping = load_hcc_mapping(HCC_MAPPING_CSV)

    # Steps 3+4+5 combined — single streaming pass
    print("\n[Step 3/4/5] Streaming diagnoses.csv ...")
    stats = streaming_pass(hcc_mapping)

    # Step 4 — Write profile
    print("\n[Step 4] Writing member_hcc_profile.csv ...")
    write_hcc_profile(stats["hcc_profile"])

    # Step 5 — Write unmapped
    print("\n[Step 5] Writing unmapped_diagnoses.csv ...")
    write_unmapped(stats["unmapped_counter"])

    # Step 6 — Write quality report
    print("\n[Step 6] Writing quality report ...")
    write_quality_report(stats, stats["hcc_profile"], stats["unmapped_counter"])

    # Documentation
    print("\n[Docs] Writing member_hcc_profile.md ...")
    write_documentation()

    print("\n" + "=" * 60)
    print("DONE. Output files:")
    for p in [OUT_DIAG_HCC, OUT_HCC_PROFILE, OUT_UNMAPPED,
              OUT_QUALITY_REPORT, OUT_DOC]:
        size_mb = p.stat().st_size / 1_048_576 if p.exists() else 0
        print(f"  {p.relative_to(PROJECT_ROOT)}  ({size_mb:.1f} MB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
