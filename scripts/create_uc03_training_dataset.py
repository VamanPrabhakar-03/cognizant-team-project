"""Create the UC03 temporal recapture ML dataset.

Features are calculated only from 2019-2021 diagnosis evidence.
TARGET is calculated only from whether the same member/HCC appears in 2022.
2023 is emitted separately as a temporal holdout and never contributes to
training features or the training target.
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "ml_training"

HISTORICAL_START = "2019-01-01"
HISTORICAL_END = "2021-12-31"
TARGET_START = "2022-01-01"
TARGET_END = "2022-12-31"
HOLDOUT_START = "2023-01-01"
HOLDOUT_END = "2023-12-31"

FEATURE_COLUMNS = [
    "bene_id",
    "hcc_v28",
    "diagnosis_count",
    "unique_icd_count",
    "active_years",
    "days_since_last_diagnosis",
    "unique_claim_count",
    "source_count",
    "inpatient_count",
    "outpatient_count",
    "carrier_count",
    "principal_diagnosis_count",
    "TARGET",
]


def normalize_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and filter one timeline chunk."""
    df["bene_id"] = df["bene_id"].str.strip()
    df["event_type"] = df["event_type"].str.strip().str.lower()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["hcc_v28"] = pd.to_numeric(df["hcc_v28"], errors="coerce")
    df["code"] = df["code"].str.strip()
    df["source"] = df["source"].str.strip().str.upper()
    df["claim_id"] = df["claim_id"].str.strip()
    df["event_id"] = df["event_id"].str.strip()
    df["is_principal"] = df["is_principal"].fillna("").str.lower().isin({"true", "1", "yes", "y"})
    df = df[
        (df["event_type"] == "diagnosis")
        & df["event_date"].notna()
        & df["hcc_v28"].notna()
        & df["bene_id"].notna()
    ].copy()
    df["hcc_v28"] = df["hcc_v28"].astype(int)
    with_event_id = df["event_id"].notna() & df["event_id"].ne("")
    return pd.concat(
        [
            df[with_event_id].drop_duplicates(subset=["event_id"]),
            df[~with_event_id].drop_duplicates(
                subset=["bene_id", "event_date", "hcc_v28", "code", "claim_id", "source", "is_principal"]
            ),
        ],
        ignore_index=True,
    )


def load_diagnosis_timeline() -> pd.DataFrame:
    columns = [
        "bene_id",
        "event_date",
        "event_type",
        "code",
        "hcc_v28",
        "source",
        "claim_id",
        "event_id",
        "is_principal",
    ]
    return pd.concat(
        [normalize_chunk(chunk) for chunk in pd.read_csv(
            DATA_DIR / "member_timeline.csv",
            usecols=columns,
            dtype={column: "string" for column in columns},
            chunksize=250_000,
            low_memory=False,
        )],
        ignore_index=True,
    )


def build_from_chunks() -> tuple[pd.DataFrame, set[tuple[str, int]], set[tuple[str, int]], int]:
    """Build compact aggregates without loading the multi-GB timeline at once."""
    columns = ["bene_id", "event_date", "event_type", "code", "hcc_v28", "source", "claim_id", "event_id", "is_principal"]
    aggregates = defaultdict(lambda: {"diagnosis_count": 0, "codes": set(), "years": set(), "last_date": None,
                                      "claims": set(), "sources": set(), "inpatient": 0, "outpatient": 0,
                                      "carrier": 0, "principal": 0})
    target_pairs: set[tuple[str, int]] = set()
    holdout_pairs: set[tuple[str, int]] = set()
    seen_event_ids: set[str] = set()
    source_rows = 0
    for chunk in pd.read_csv(DATA_DIR / "member_timeline.csv", usecols=columns,
                             dtype={column: "string" for column in columns}, chunksize=250_000, low_memory=False):
        chunk = normalize_chunk(chunk)
        if chunk.empty:
            continue
        valid_ids = chunk["event_id"].notna() & chunk["event_id"].ne("")
        if valid_ids.any():
            chunk = pd.concat([
                chunk[~valid_ids],
                chunk[valid_ids & ~chunk["event_id"].isin(seen_event_ids)],
            ], ignore_index=True)
            seen_event_ids.update(chunk.loc[chunk["event_id"].notna() & chunk["event_id"].ne(""), "event_id"].tolist())
        source_rows += len(chunk)
        for row in chunk.itertuples(index=False):
            pair = (str(row.bene_id), int(row.hcc_v28))
            date = row.event_date
            if date >= pd.Timestamp(TARGET_START) and date <= pd.Timestamp(TARGET_END):
                target_pairs.add(pair)
            if date >= pd.Timestamp(HOLDOUT_START) and date <= pd.Timestamp(HOLDOUT_END):
                holdout_pairs.add(pair)
            if date < pd.Timestamp(HISTORICAL_START) or date > pd.Timestamp(HISTORICAL_END):
                continue
            item = aggregates[pair]
            item["diagnosis_count"] += 1
            if pd.notna(row.code) and row.code != "": item["codes"].add(str(row.code))
            item["years"].add(date.year)
            if item["last_date"] is None or date > item["last_date"]: item["last_date"] = date
            if pd.notna(row.claim_id) and row.claim_id != "": item["claims"].add(str(row.claim_id))
            if pd.notna(row.source) and row.source != "": item["sources"].add(str(row.source))
            if row.source == "INPATIENT": item["inpatient"] += 1
            if row.source == "OUTPATIENT": item["outpatient"] += 1
            if row.source == "CARRIER": item["carrier"] += 1
            if row.is_principal: item["principal"] += 1
    rows = []
    anchor = pd.Timestamp(HISTORICAL_END)
    for (bene_id, hcc_v28), item in sorted(aggregates.items()):
        rows.append({"bene_id": bene_id, "hcc_v28": hcc_v28, "diagnosis_count": item["diagnosis_count"],
                     "unique_icd_count": len(item["codes"]), "active_years": len(item["years"]),
                     "days_since_last_diagnosis": int((anchor - item["last_date"]).days),
                     "unique_claim_count": len(item["claims"]), "source_count": len(item["sources"]),
                     "inpatient_count": item["inpatient"], "outpatient_count": item["outpatient"],
                     "carrier_count": item["carrier"], "principal_diagnosis_count": item["principal"]})
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS[:-1]), target_pairs, holdout_pairs, source_rows


def build_features(historical: pd.DataFrame) -> pd.DataFrame:
    if historical.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS[:-1])

    rows = []
    for (bene_id, hcc_v28), group in historical.groupby(["bene_id", "hcc_v28"], sort=True):
        non_null_claims = group["claim_id"].dropna()
        rows.append(
            {
                "bene_id": str(bene_id),
                "hcc_v28": int(hcc_v28),
                "diagnosis_count": int(len(group)),
                "unique_icd_count": int(group["code"].dropna().nunique()),
                "active_years": int(group["event_date"].dt.year.nunique()),
                "days_since_last_diagnosis": int((pd.Timestamp("2021-12-31") - group["event_date"].max()).days),
                "unique_claim_count": int(non_null_claims.nunique()),
                "source_count": int(group["source"].dropna().nunique()),
                "inpatient_count": int((group["source"] == "INPATIENT").sum()),
                "outpatient_count": int((group["source"] == "OUTPATIENT").sum()),
                "carrier_count": int((group["source"] == "CARRIER").sum()),
                "principal_diagnosis_count": int(group["is_principal"].sum()),
            }
        )
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS[:-1])


def pair_set(frame: pd.DataFrame) -> set[tuple[str, int]]:
    if frame.empty:
        return set()
    return set(zip(frame["bene_id"].astype(str), frame["hcc_v28"].astype(int)))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, target_pairs, holdout_pairs, source_rows = build_from_chunks()

    training = features.copy()
    training["TARGET"] = [
        int((str(row.bene_id), int(row.hcc_v28)) in target_pairs)
        for row in training.itertuples(index=False)
    ]
    training = training[FEATURE_COLUMNS].sort_values(["bene_id", "hcc_v28"]).reset_index(drop=True)

    holdout = features.copy()
    holdout["HOLDOUT_TARGET_2023"] = [
        int((str(row.bene_id), int(row.hcc_v28)) in holdout_pairs)
        for row in holdout.itertuples(index=False)
    ]
    holdout = holdout.rename(columns={"TARGET": "unused"}) if "TARGET" in holdout.columns else holdout
    holdout = holdout[FEATURE_COLUMNS[:-1] + ["HOLDOUT_TARGET_2023"]].sort_values(["bene_id", "hcc_v28"]).reset_index(drop=True)

    training_path = OUTPUT_DIR / "uc03_recapture_training_dataset.csv"
    holdout_path = OUTPUT_DIR / "uc03_recapture_holdout_2023.csv"
    metadata_path = OUTPUT_DIR / "uc03_dataset_metadata.json"
    report_path = OUTPUT_DIR / "uc03_dataset_quality_report.md"
    training.to_csv(training_path, index=False)
    holdout.to_csv(holdout_path, index=False)

    metadata = {
        "dataset": "UC03 temporal recapture training dataset",
        "prediction_unit": "bene_id + hcc_v28",
        "feature_period": {"start": HISTORICAL_START, "end": HISTORICAL_END},
        "target_period": {"start": TARGET_START, "end": TARGET_END},
        "holdout_period": {"start": HOLDOUT_START, "end": HOLDOUT_END},
        "target_definition": "1 when the historical member-HCC pair is observed again during 2022; otherwise 0",
        "training_rows": int(len(training)),
        "positive_rows": int(training["TARGET"].sum()),
        "negative_rows": int((training["TARGET"] == 0).sum()),
        "holdout_rows": int(len(holdout)),
        "holdout_positive_rows": int(holdout["HOLDOUT_TARGET_2023"].sum()),
        "source_rows_after_deduplication": int(source_rows),
        "source_file": "data/member_timeline.csv",
        "excluded_from_features": ["2022 diagnosis events", "2023 diagnosis events", "suspects.csv priority_score/status/suspect_type"],
        "feature_columns": FEATURE_COLUMNS[:-1],
        "target_column": "TARGET",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    positive_rate = training["TARGET"].mean() if len(training) else 0
    report = f"""# UC03 Dataset Quality Report

## Definition

- Unit: one `bene_id + hcc_v28` pair.
- Features: diagnosis evidence from 2019–2021 only.
- `TARGET`: same member-HCC pair observed in 2022.
- 2023 is held out for temporal evaluation and is not used in training features or `TARGET`.

## Counts

| Measure | Value |
|---|---:|
| Source diagnosis rows after deduplication | {source_rows:,} |
| Historical feature rows | {len(training):,} |
| Positive training targets | {int(training['TARGET'].sum()):,} |
| Negative training targets | {int((training['TARGET'] == 0).sum()):,} |
| Positive target rate | {positive_rate:.2%} |
| 2023 holdout rows | {len(holdout):,} |
| 2023 holdout positives | {int(holdout['HOLDOUT_TARGET_2023'].sum()):,} |

## Leakage checks

- No 2022 or 2023 dates are used in training feature calculations.
- The target is derived from pair presence in 2022, not from `suspects.csv` scores or status.
- All training rows have historical evidence by construction.
- New/emerging HCCs that first appear only in 2022 are not included because they have no 2019–2021 feature row.
"""
    report_path.write_text(report, encoding="utf-8")

    print(json.dumps({
        "training_path": str(training_path),
        "holdout_path": str(holdout_path),
        "metadata_path": str(metadata_path),
        "training_rows": len(training),
        "positive_rows": int(training["TARGET"].sum()),
        "negative_rows": int((training["TARGET"] == 0).sum()),
        "holdout_rows": len(holdout),
        "holdout_positive_rows": int(holdout["HOLDOUT_TARGET_2023"].sum()),
    }, indent=2))


if __name__ == "__main__":
    main()
