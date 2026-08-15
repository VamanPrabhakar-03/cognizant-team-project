"""Validate Evidence Engine V2 on the primary 2019-2020 -> 2021 -> 2022 split."""

import csv
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TIMELINE = DATA / "member_timeline.csv"
PRESCRIPTIONS = DATA / "events_prescription.csv"
OUTPUT = DATA / "suspects_with_evidence_v2_primary.csv"
REPORT = DATA / "validation_report_v2_primary.md"

HIST_YEARS = {"2019", "2020"}
CURRENT_YEAR = "2021"
VALIDATION_YEAR = "2022"
REFERENCE_DATE = pd.Timestamp("2021-12-31")


def empty_feature():
    return {
        "diagnosis_count": 0,
        "claims": set(),
        "events": set(),
        "dates": set(),
        "months": set(),
        "sources": set(),
        "principal_count": 0,
        "codes": set(),
        "last_date": None,
        "rx_support_count": 0,
    }


def v2_score(feature):
    count = feature["diagnosis_count"]
    claims = len(feature["claims"])
    dates = len(feature["dates"])
    months = len(feature["months"])
    sources = len(feature["sources"])
    principal = feature["principal_count"]
    last_date = feature["last_date"]

    if not count:
        return 0.0

    days_since = max(0, (REFERENCE_DATE - pd.Timestamp(last_date)).days)
    frequency = 1 - math.exp(-count / 15.0)
    persistence = min(months / 4.0, 1.0)
    repeated_claim = min(claims / 3.0, 1.0)
    repeated_date = min(dates / 5.0, 1.0)
    recency = math.exp(-days_since / 365.0)
    source_diversity = min(sources / 2.0, 1.0)
    principal_score = min(principal / 2.0, 1.0)
    prescription_score = min(feature["rx_support_count"] / 2.0, 1.0)

    return round(
        0.18 * frequency
        + 0.18 * persistence
        + 0.15 * repeated_claim
        + 0.15 * repeated_date
        + 0.15 * recency
        + 0.08 * source_diversity
        + 0.08 * principal_score
        + 0.03 * prescription_score,
        4,
    )


def priority(score):
    if score >= 0.75:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


def parse_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def main():
    print("=" * 72)
    print("PRIMARY VALIDATION: EVIDENCE ENGINE V2")
    print("Baseline: 2019-2020 | Evidence: 2021 | Validation: 2022")
    print("=" * 72)

    historical = defaultdict(set)
    current = defaultdict(set)
    validation = defaultdict(set)
    features = defaultdict(empty_feature)
    total_rows = 0

    with TIMELINE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            if str(row.get("event_type", "")).strip().lower() != "diagnosis":
                continue
            hcc = str(row.get("hcc_v28", "")).strip()
            if not hcc:
                continue
            bene = str(row.get("bene_id", "")).strip()
            date_text = str(row.get("event_date", "")).strip()
            year = date_text[:4]
            if year in HIST_YEARS:
                historical[bene].add(hcc)
            elif year == CURRENT_YEAR:
                current[bene].add(hcc)
                key = (bene, hcc)
                f = features[key]
                f["diagnosis_count"] += 1
                f["claims"].add(str(row.get("claim_id", "")).strip())
                f["events"].add(str(row.get("event_id", "")).strip())
                f["dates"].add(date_text[:10])
                f["months"].add(date_text[:7])
                f["sources"].add(str(row.get("source", "")).strip().upper())
                f["codes"].add(str(row.get("code", "")).strip())
                if parse_bool(row.get("is_principal", "")):
                    f["principal_count"] += 1
                if f["last_date"] is None or date_text > f["last_date"]:
                    f["last_date"] = date_text
            elif year == VALIDATION_YEAR:
                validation[bene].add(hcc)

    rx_by_member = defaultdict(list)
    with PRESCRIPTIONS.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            date_text = str(row.get("event_date", "")).strip()
            if date_text[:4] == CURRENT_YEAR:
                rx_by_member[str(row.get("bene_id", "")).strip()].append(pd.Timestamp(date_text))

    for (bene, _hcc), feature in features.items():
        diagnosis_dates = [pd.Timestamp(value) for value in feature["dates"]]
        feature["rx_support_count"] = sum(
            any(abs((rx_date - diagnosis_date).days) <= 30 for diagnosis_date in diagnosis_dates)
            for rx_date in rx_by_member.get(bene, [])
        )

    emerging = []
    recapture = []
    for bene in sorted(set(historical) | set(current) | set(validation)):
        hist = historical.get(bene, set())
        curr = current.get(bene, set())
        val = validation.get(bene, set())
        for hcc in sorted(curr - hist):
            score = v2_score(features[(bene, hcc)])
            emerging.append({
                "bene_id": bene,
                "hcc_v28": int(float(hcc)),
                "suspect_type": "EMERGING",
                "priority_score": score,
                "priority": priority(score),
                "diagnosis_count": features[(bene, hcc)]["diagnosis_count"],
                "distinct_evidence_dates": len(features[(bene, hcc)]["dates"]),
                "distinct_evidence_months": len(features[(bene, hcc)]["months"]),
                "distinct_sources": len(features[(bene, hcc)]["sources"]),
                "principal_diagnosis_count": features[(bene, hcc)]["principal_count"],
                "confirmed_in_2022": hcc in val,
            })
        for hcc in sorted(hist - curr):
            recapture.append({
                "bene_id": bene,
                "hcc_v28": int(float(hcc)),
                "suspect_type": "RECAPTURE",
                "priority_score": 0.0,
                "priority": "LOW",
                "diagnosis_count": 0,
                "distinct_evidence_dates": 0,
                "distinct_evidence_months": 0,
                "distinct_sources": 0,
                "principal_diagnosis_count": 0,
                "returned_in_2022": hcc in val,
            })

    emerging_df = pd.DataFrame(emerging)
    recapture_df = pd.DataFrame(recapture)
    output = pd.concat([emerging_df, recapture_df], ignore_index=True)
    output.to_csv(OUTPUT, index=False)

    new_2022 = sum(len(validation.get(b, set()) - historical.get(b, set())) for b in validation)
    caught = sum(len((validation.get(b, set()) - historical.get(b, set())) & (current.get(b, set()) - historical.get(b, set()))) for b in validation)

    def tier_table(frame, result_column):
        rows = []
        for tier in ["HIGH", "MEDIUM", "LOW"]:
            subset = frame[frame["priority"] == tier]
            confirmed = int(subset[result_column].sum()) if len(subset) else 0
            rows.append((tier, len(subset), confirmed, confirmed / len(subset) if len(subset) else 0.0))
        return rows

    emerging_tiers = tier_table(emerging_df, "confirmed_in_2022")
    recapture_tiers = tier_table(recapture_df, "returned_in_2022")
    confirmed = int(emerging_df["confirmed_in_2022"].sum())
    total_emerging = len(emerging_df)
    precision = confirmed / total_emerging if total_emerging else 0
    recall = caught / new_2022 if new_2022 else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    lines = [
        "# Primary Validation Report — Evidence Engine V2",
        "",
        "| Parameter | Value |",
        "|---|---:|",
        f"| Timeline rows processed | {total_rows:,} |",
        "| Historical baseline | 2019–2020 |",
        "| Current evidence | 2021 |",
        "| Validation year | 2022 |",
        "",
        "## Emerging performance",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Suspects flagged | {total_emerging:,} |",
        f"| Confirmed in 2022 | {confirmed:,} |",
        f"| Future confirmation rate | {precision:.1%} |",
        f"| New HCCs in 2022 | {new_2022:,} |",
        f"| Caught by 2021 evidence | {caught:,} |",
        f"| Early-detection recall | {recall:.1%} |",
        f"| F1 score | {f1:.3f} |",
        "",
        "## V2 tier calibration",
        "",
        "| Tier | Suspects | Confirmed | Rate |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(f"| {tier} | {count:,} | {confirmed_count:,} | {rate:.1%} |" for tier, count, confirmed_count, rate in emerging_tiers)
    lines.extend(["", "## Recapture calibration", "", "| Tier | Suspects | Returned | Rate |", "|---|---:|---:|---:|"])
    lines.extend(f"| {tier} | {count:,} | {confirmed_count:,} | {rate:.1%} |" for tier, count, confirmed_count, rate in recapture_tiers)
    lines.extend(["", "> These measures use claims documentation in 2022 as a proxy for future confirmation, not clinical truth.", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Timeline rows processed: {total_rows:,}")
    print(f"Emerging suspects: {total_emerging:,}")
    print(f"Confirmed in 2022: {confirmed:,}")
    print(f"Future confirmation rate: {precision:.1%}")
    print(f"Early-detection recall: {recall:.1%}")
    print(f"F1 score: {f1:.3f}")
    print("\nV2 tier calibration:")
    for tier, count, confirmed_count, rate in emerging_tiers:
        print(f"  {tier:6} {count:4,} suspects | {confirmed_count:4,} confirmed | {rate:.1%}")
    print(f"\nSaved: {OUTPUT}")
    print(f"Saved: {REPORT}")


if __name__ == "__main__":
    main()
