"""
Phase 1 -- Ingest Members from CMS Beneficiary Files

Reads (pipe-separated, all IDs as strings):
    new data/beneficiary_2023(1).csv
    new data/beneficiary_2024.csv
    new data/beneficiary_2025.csv

Produces:
    data/members.csv

Deduplicates on BENE_ID, tracks enrollment years per member.
"""

import csv
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "new data"
OUT_DIR      = PROJECT_ROOT / "data"

BENE_FILES = [
    (RAW_DIR / "beneficiary_2023(1).csv", "2023"),
    (RAW_DIR / "beneficiary_2024.csv",    "2024"),
    (RAW_DIR / "beneficiary_2025.csv",    "2025"),
]

OUT_MEMBERS = OUT_DIR / "members.csv"


def clean_date(raw: str) -> str:
    """Convert 'DD-Mon-YYYY' or 'DD-Mon-YY' to 'YYYY-MM-DD'. Returns '' if invalid."""
    s = raw.strip() if raw else ""
    if not s:
        return ""

    MONTHS = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }

    parts = s.split("-")
    if len(parts) == 3:
        day, mon, year = parts
        mon_num = MONTHS.get(mon.lower(), "")
        if mon_num and year:
            day = day.zfill(2)
            if len(year) == 2:
                year = "19" + year if int(year) > 50 else "20" + year
            return f"{year}-{mon_num}-{day}"
    return s  # return as-is if we can't parse


def main():
    print("=" * 60)
    print("Phase 1 -- Ingest Members")
    print("=" * 60)

    for path, _ in BENE_FILES:
        if not path.exists():
            print(f"ERROR: Missing file: {path}", file=sys.stderr)
            sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Accumulate members: bene_id -> member dict
    members: dict = {}

    for path, year in BENE_FILES:
        print(f"\n  Reading {path.name} (year={year})...")
        count = 0
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter="|")
            for row in reader:
                bene_id = row.get("BENE_ID", "").strip()
                if not bene_id:
                    continue

                count += 1

                if bene_id in members:
                    # Add enrollment year
                    existing_years = set(members[bene_id]["enrollment_years"].split("|"))
                    existing_years.add(year)
                    members[bene_id]["enrollment_years"] = "|".join(sorted(existing_years))
                else:
                    members[bene_id] = {
                        "bene_id":           bene_id,
                        "birth_date":        clean_date(row.get("BENE_BIRTH_DT", "")),
                        "sex":               row.get("SEX_IDENT_CD", "").strip(),
                        "race":              row.get("BENE_RACE_CD", "").strip(),
                        "state":             row.get("STATE_CODE", "").strip(),
                        "county":            row.get("COUNTY_CD", "").strip(),
                        "zip":               row.get("ZIP_CD", "").strip(),
                        "esrd_indicator":    row.get("ESRD_IND", "").strip(),
                        "death_date":        clean_date(row.get("BENE_DEATH_DT", "")),
                        "enrollment_years":  year,
                    }

        print(f"    Rows read: {count:,}")

    # Write output
    cols = [
        "bene_id", "birth_date", "sex", "race", "state",
        "county", "zip", "esrd_indicator", "death_date", "enrollment_years",
    ]

    with open(OUT_MEMBERS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for bene_id in sorted(members.keys()):
            writer.writerow(members[bene_id])

    print(f"\n  Written: {OUT_MEMBERS.name}")
    print(f"  Total unique members: {len(members):,}")

    # Enrollment stats
    year_counts = {"2023": 0, "2024": 0, "2025": 0}
    multi_year = 0
    for m in members.values():
        years = m["enrollment_years"].split("|")
        for y in years:
            if y in year_counts:
                year_counts[y] += 1
        if len(years) > 1:
            multi_year += 1

    print(f"\n  Enrollment distribution:")
    for y, c in sorted(year_counts.items()):
        print(f"    {y}: {c:,}")
    print(f"    Members in 2+ years: {multi_year:,}")
    print(f"    Members in all 3 years: "
          f"{sum(1 for m in members.values() if len(m['enrollment_years'].split('|')) == 3):,}")

    print("\n" + "=" * 60)
    print("Phase 1 DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
