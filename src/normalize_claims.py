"""
Phase 2 -- Normalize Claims into Diagnosis Events + Prescription Events

Reads (pipe-separated, all IDs as strings):
    new data/inpatient.csv
    new data/outpatient.csv
    new data/carrier.csv
    new data/pde.csv
    data/members.csv          (for validation)

Produces:
    data/events_diagnosis.csv
    data/events_prescription.csv

Diagnosis extraction: wide ICD columns -> individual event rows.
Prescription extraction: one row per PDE event.
"""

import csv
import re
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "new data"
DATA_DIR     = PROJECT_ROOT / "data"

MEMBERS_CSV  = DATA_DIR / "members.csv"
OUT_DIAG     = DATA_DIR / "events_diagnosis.csv"
OUT_RX       = DATA_DIR / "events_prescription.csv"

CHUNK_FLUSH = 50_000  # flush to disk every N rows

# Month abbreviation -> number for date parsing
MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def clean_date(raw: str) -> str:
    """Convert 'DD-Mon-YYYY' to 'YYYY-MM-DD'. Returns '' if invalid."""
    s = raw.strip() if raw else ""
    if not s:
        return ""
    parts = s.split("-")
    if len(parts) == 3:
        day, mon, year = parts
        mon_num = MONTHS.get(mon.lower(), "")
        if mon_num and year:
            day = day.zfill(2)
            if len(year) == 2:
                year = "19" + year if int(year) > 50 else "20" + year
            return f"{year}-{mon_num}-{day}"
    return s


def clean_code(raw: str) -> str:
    """Clean diagnosis code: uppercase, strip, remove dots."""
    if not raw:
        return ""
    v = raw.strip().upper()
    v = v.replace(".", "")
    if v in ("", "NAN", "NONE", "NULL"):
        return ""
    return v


def load_valid_members(path: Path) -> set:
    """Load the set of valid BENE_IDs from members.csv."""
    members = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            members.add(row["bene_id"].strip())
    return members


# ── Diagnosis Extraction ───────────────────────────────────────────────────────

DIAG_COLS = [
    "bene_id", "event_id", "claim_id", "event_date",
    "source", "diagnosis_code", "is_principal",
]


def extract_diagnoses_from_file(
    filepath: Path,
    source: str,
    valid_members: set,
    writer: csv.DictWriter,
    date_col: str = "CLM_FROM_DT",
    max_icd: int = 25,
) -> dict:
    """
    Read a pipe-separated claims file.
    Extract PRNCPAL_DGNS_CD + ICD_DGNS_CD1..max_icd into individual rows.
    Returns stats dict.
    """
    print(f"\n  Processing {filepath.name} (source={source})...")

    total_claims = 0
    total_events = 0
    skipped_orphan = 0
    buf = []

    with open(filepath, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="|")

        for row in reader:
            bene_id = row.get("BENE_ID", "").strip()
            clm_id  = row.get("CLM_ID", "").strip()
            date    = clean_date(row.get(date_col, ""))

            if not bene_id:
                continue

            if bene_id not in valid_members:
                skipped_orphan += 1
                continue

            total_claims += 1

            # Track codes already seen on this claim to avoid duplicates
            seen_codes = set()

            # Principal diagnosis
            p_code = clean_code(row.get("PRNCPAL_DGNS_CD", ""))
            if p_code:
                event_id = f"{source}_{clm_id}_P"
                buf.append({
                    "bene_id":        bene_id,
                    "event_id":       event_id,
                    "claim_id":       clm_id,
                    "event_date":     date,
                    "source":         source,
                    "diagnosis_code": p_code,
                    "is_principal":   "True",
                })
                seen_codes.add(p_code)
                total_events += 1

            # Secondary diagnoses: ICD_DGNS_CD1 .. ICD_DGNS_CDN
            for i in range(1, max_icd + 1):
                col = f"ICD_DGNS_CD{i}"
                s_code = clean_code(row.get(col, ""))
                if s_code and s_code not in seen_codes:
                    event_id = f"{source}_{clm_id}_{i}"
                    buf.append({
                        "bene_id":        bene_id,
                        "event_id":       event_id,
                        "claim_id":       clm_id,
                        "event_date":     date,
                        "source":         source,
                        "diagnosis_code": s_code,
                        "is_principal":   "False",
                    })
                    seen_codes.add(s_code)
                    total_events += 1

            # Flush buffer
            if len(buf) >= CHUNK_FLUSH:
                writer.writerows(buf)
                buf = []

    # Final flush
    if buf:
        writer.writerows(buf)

    print(f"    Claims: {total_claims:,} | Events: {total_events:,} | "
          f"Orphans skipped: {skipped_orphan:,}")
    return {
        "source": source,
        "claims": total_claims,
        "events": total_events,
        "orphans": skipped_orphan,
    }


# ── Prescription Extraction ────────────────────────────────────────────────────

RX_COLS = [
    "bene_id", "event_id", "pde_id", "event_date", "drug_code",
]


def extract_prescriptions(filepath: Path, valid_members: set) -> dict:
    """Read PDE file, write events_prescription.csv."""
    print(f"\n  Processing {filepath.name} (prescriptions)...")

    total = 0
    skipped_orphan = 0

    with open(OUT_RX, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=RX_COLS)
        writer.writeheader()

        buf = []

        with open(filepath, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter="|")
            for row in reader:
                bene_id = row.get("BENE_ID", "").strip()
                pde_id  = row.get("PDE_ID", "").strip()
                date    = clean_date(row.get("SRVC_DT", ""))
                drug    = row.get("PROD_SRVC_ID", "").strip()

                if not bene_id:
                    continue

                if bene_id not in valid_members:
                    skipped_orphan += 1
                    continue

                total += 1
                event_id = f"PDE_{pde_id}"

                buf.append({
                    "bene_id":   bene_id,
                    "event_id":  event_id,
                    "pde_id":    pde_id,
                    "event_date": date,
                    "drug_code": drug,
                })

                if len(buf) >= CHUNK_FLUSH:
                    writer.writerows(buf)
                    buf = []

        if buf:
            writer.writerows(buf)

    print(f"    Prescriptions: {total:,} | Orphans skipped: {skipped_orphan:,}")
    return {"prescriptions": total, "orphans": skipped_orphan}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Phase 2 -- Normalize Claims")
    print("=" * 60)

    # Validate inputs
    for p in [MEMBERS_CSV,
              RAW_DIR / "inpatient.csv",
              RAW_DIR / "outpatient.csv",
              RAW_DIR / "carrier.csv",
              RAW_DIR / "pde.csv"]:
        if not p.exists():
            print(f"ERROR: Missing: {p}", file=sys.stderr)
            sys.exit(1)

    # Load valid members
    print("\n  Loading valid members from members.csv...")
    valid_members = load_valid_members(MEMBERS_CSV)
    print(f"    {len(valid_members):,} valid BENE_IDs")

    # ── Diagnosis events ──
    stats_all = []

    with open(OUT_DIAG, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=DIAG_COLS)
        writer.writeheader()

        # Inpatient: up to 25 ICD columns
        stats_all.append(extract_diagnoses_from_file(
            RAW_DIR / "inpatient.csv", "INPATIENT", valid_members, writer,
            date_col="CLM_FROM_DT", max_icd=25,
        ))

        # Outpatient: up to 25 ICD columns
        stats_all.append(extract_diagnoses_from_file(
            RAW_DIR / "outpatient.csv", "OUTPATIENT", valid_members, writer,
            date_col="CLM_FROM_DT", max_icd=25,
        ))

        # Carrier: up to 12 ICD columns
        stats_all.append(extract_diagnoses_from_file(
            RAW_DIR / "carrier.csv", "CARRIER", valid_members, writer,
            date_col="CLM_FROM_DT", max_icd=12,
        ))

    diag_size = OUT_DIAG.stat().st_size / (1024 * 1024)
    print(f"\n  Written: {OUT_DIAG.name} ({diag_size:.1f} MB)")

    total_events = sum(s["events"] for s in stats_all)
    total_claims = sum(s["claims"] for s in stats_all)
    print(f"  Total claims processed: {total_claims:,}")
    print(f"  Total diagnosis events: {total_events:,}")

    # ── Prescription events ──
    rx_stats = extract_prescriptions(RAW_DIR / "pde.csv", valid_members)

    rx_size = OUT_RX.stat().st_size / (1024 * 1024)
    print(f"\n  Written: {OUT_RX.name} ({rx_size:.1f} MB)")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("Phase 2 DONE")
    print()
    print("  Diagnosis events by source:")
    for s in stats_all:
        print(f"    {s['source']:12s}  claims={s['claims']:>10,}  events={s['events']:>10,}")
    print(f"    {'TOTAL':12s}  claims={total_claims:>10,}  events={total_events:>10,}")
    print(f"\n  Prescription events: {rx_stats['prescriptions']:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
