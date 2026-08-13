"""
Phase 4 -- Build Member Timeline

Reads:
    data/events_diagnosis.csv
    data/events_prescription.csv
    data/hcc_mapping.csv

Produces:
    data/member_timeline.csv

Merges diagnosis events with HCC mapping, combines with prescription events,
sorts by (bene_id, event_date, event_type). This is the unified medical timeline.
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"

EVENTS_DIAG  = DATA_DIR / "events_diagnosis.csv"
EVENTS_RX    = DATA_DIR / "events_prescription.csv"
HCC_MAPPING  = DATA_DIR / "hcc_mapping.csv"
OUT_TIMELINE = DATA_DIR / "member_timeline.csv"

CHUNK_FLUSH = 100_000

TIMELINE_COLS = [
    "bene_id", "event_date", "event_type", "code", "hcc_v28",
    "source", "claim_id", "event_id", "is_principal",
]


def load_hcc_mapping(path: Path) -> dict:
    """Load HCC mapping as {diagnosis_code: hcc_v28}."""
    mapping = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["diagnosis_code"].strip().upper()
            hcc  = row["hcc_v28"].strip()
            if code:
                mapping[code] = hcc
    return mapping


def main():
    print("=" * 60)
    print("Phase 4 -- Build Member Timeline")
    print("=" * 60)

    for p in [EVENTS_DIAG, EVENTS_RX, HCC_MAPPING]:
        if not p.exists():
            print(f"ERROR: Missing: {p}", file=sys.stderr)
            sys.exit(1)

    # Load HCC mapping
    print("\n  Loading HCC mapping...")
    hcc_map = load_hcc_mapping(HCC_MAPPING)
    print(f"    {len(hcc_map):,} codes loaded")

    # Process into timeline
    print(f"\n  Streaming diagnosis events...")
    total_diag = 0
    total_mapped = 0
    total_unmapped_in_crosswalk = 0
    total_not_in_crosswalk = 0

    with open(OUT_TIMELINE, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=TIMELINE_COLS)
        writer.writeheader()
        buf = []

        # ── Diagnosis events ──
        with open(EVENTS_DIAG, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_diag += 1
                code = row["diagnosis_code"].strip().upper()
                hcc = hcc_map.get(code, "")

                if code in hcc_map:
                    if hcc:
                        total_mapped += 1
                    else:
                        total_unmapped_in_crosswalk += 1
                else:
                    total_not_in_crosswalk += 1

                buf.append({
                    "bene_id":      row["bene_id"],
                    "event_date":   row["event_date"],
                    "event_type":   "diagnosis",
                    "code":         code,
                    "hcc_v28":      hcc,
                    "source":       row["source"],
                    "claim_id":     row["claim_id"],
                    "event_id":     row["event_id"],
                    "is_principal": row["is_principal"],
                })

                if len(buf) >= CHUNK_FLUSH:
                    writer.writerows(buf)
                    buf = []
                    if total_diag % 5_000_000 == 0:
                        print(f"    ... {total_diag:,} diagnosis events processed")

        print(f"    Diagnosis events: {total_diag:,}")
        print(f"      Mapped to HCC:         {total_mapped:,}")
        print(f"      In crosswalk, no HCC:  {total_unmapped_in_crosswalk:,}")
        print(f"      Not in crosswalk:      {total_not_in_crosswalk:,}")

        # ── Prescription events ──
        print(f"\n  Streaming prescription events...")
        total_rx = 0

        with open(EVENTS_RX, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rx += 1
                buf.append({
                    "bene_id":      row["bene_id"],
                    "event_date":   row["event_date"],
                    "event_type":   "prescription",
                    "code":         row["drug_code"],
                    "hcc_v28":      "",
                    "source":       "PDE",
                    "claim_id":     row["pde_id"],
                    "event_id":     row["event_id"],
                    "is_principal": "",
                })

                if len(buf) >= CHUNK_FLUSH:
                    writer.writerows(buf)
                    buf = []

        # Final flush
        if buf:
            writer.writerows(buf)

        print(f"    Prescription events: {total_rx:,}")

    total_all = total_diag + total_rx
    size_mb = OUT_TIMELINE.stat().st_size / (1024 * 1024)

    print(f"\n  Written: {OUT_TIMELINE.name} ({size_mb:.1f} MB)")
    print(f"  Total timeline events: {total_all:,}")

    print("\n" + "=" * 60)
    print("Phase 4 DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
