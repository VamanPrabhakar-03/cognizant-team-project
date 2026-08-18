"""Combined production-oriented HCC suspect engine.

This is the single frozen algorithm for the local CSV-backed MVP.
It combines the validated V2 score with modular evidence aggregation,
deduplication, latest-period context, deterministic reason flags, and a
structured JSON payload for the downstream LLM reviewer.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
BASELINE_FILE = DATA_DIR / "member_hcc_baseline_2020_2021.csv"
TIMELINE_FILE = DATA_DIR / "member_timeline.csv"
PRESCRIPTION_FILE = DATA_DIR / "events_prescription.csv"
HCC_MAPPING_FILE = DATA_DIR / "hcc_mapping.csv"
OUTPUT_FILE = DATA_DIR / "suspects_with_evidence_final.csv"
LLM_INPUT_FILE = DATA_DIR / "suspect_llm_input.json"

HISTORICAL_YEARS = {2020, 2021}
CURRENT_YEAR = 2022
LATEST_YEAR = 2023
REFERENCE_DATE = pd.Timestamp("2022-12-31")
PRESCRIPTION_WINDOW_DAYS = 30


def clean_ids(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def assign_priority(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    elif score >= 0.50:
        return "MEDIUM"
    return "LOW"



def load_hcc_descriptions() -> dict[int, str]:
    df = pd.read_csv(HCC_MAPPING_FILE, usecols=["hcc_v28", "description"])
    df["hcc_v28"] = pd.to_numeric(df["hcc_v28"], errors="coerce")
    df = df.dropna(subset=["hcc_v28", "description"]).copy()
    df["hcc_v28"] = df["hcc_v28"].astype(int)
    return df.groupby("hcc_v28")["description"].first().to_dict()


def load_baseline() -> pd.DataFrame:
    df = pd.read_csv(BASELINE_FILE, usecols=["bene_id", "hcc_v28"], dtype={"bene_id": "string"})
    df["bene_id"] = clean_ids(df["bene_id"])
    df["hcc_v28"] = pd.to_numeric(df["hcc_v28"], errors="coerce")
    df = df.dropna(subset=["bene_id", "hcc_v28"]).copy()
    df["hcc_v28"] = df["hcc_v28"].astype(int)
    return df.drop_duplicates(["bene_id", "hcc_v28"])


def load_timeline() -> pd.DataFrame:
    columns = [
        "bene_id", "event_date", "event_type", "code", "hcc_v28",
        "source", "claim_id", "event_id", "is_principal",
    ]
    df = pd.read_csv(
        TIMELINE_FILE,
        usecols=columns,
        dtype={
            "bene_id": "string", "event_date": "string", "event_type": "string",
            "code": "string", "source": "string", "claim_id": "string",
            "event_id": "string", "is_principal": "string",
        },
        low_memory=False,
    )
    df["bene_id"] = clean_ids(df["bene_id"])
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["event_type"] = df["event_type"].astype("string").str.strip().str.lower()
    df["source"] = df["source"].astype("string").str.strip().str.upper()
    df["hcc_v28"] = pd.to_numeric(df["hcc_v28"], errors="coerce")
    df["is_principal"] = (
        df["is_principal"].fillna("").astype("string").str.strip().str.lower()
        .isin(["true", "1", "yes", "y"])
    )
    return df[
        (df["event_type"] == "diagnosis")
        & df["event_date"].notna()
        & df["hcc_v28"].notna()
        & df["event_date"].dt.year.isin(HISTORICAL_YEARS | {CURRENT_YEAR, LATEST_YEAR})
    ].assign(hcc_v28=lambda x: x["hcc_v28"].astype(int))


def load_prescriptions() -> pd.DataFrame:
    df = pd.read_csv(
        PRESCRIPTION_FILE,
        usecols=["bene_id", "event_id", "event_date", "drug_code"],
        dtype={"bene_id": "string", "event_id": "string", "event_date": "string", "drug_code": "string"},
    )
    df["bene_id"] = clean_ids(df["bene_id"])
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    return df[df["event_date"].dt.year.isin(HISTORICAL_YEARS | {CURRENT_YEAR, LATEST_YEAR})].copy()


def build_hcc_sets(df: pd.DataFrame) -> dict[str, set[int]]:
    return {bene_id: set(group["hcc_v28"].astype(int)) for bene_id, group in df.groupby("bene_id")}


def detect_gaps(baseline_hccs: dict[str, set[int]], current_hccs: dict[str, set[int]]) -> list[dict]:
    """Create candidates only for members with a valid baseline."""
    suspects = []
    for bene_id in sorted(baseline_hccs):
        historical = baseline_hccs[bene_id]
        current = current_hccs.get(bene_id, set())
        for hcc in sorted(current - historical):
            suspects.append({"bene_id": bene_id, "hcc_v28": hcc, "gap_type": "EMERGING", "status": "PENDING_REVIEW"})
        for hcc in sorted(historical - current):
            suspects.append({"bene_id": bene_id, "hcc_v28": hcc, "gap_type": "RECAPTURE", "status": "PENDING_REVIEW"})
    return suspects


def deduplicate_events(events: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate copies of the same clinical evidence record."""
    if events.empty:
        return events.copy()
    columns = ["bene_id", "event_date", "hcc_v28"]
    for candidate in ["claim_id", "code", "event_id"]:
        if candidate in events.columns:
            columns.append(candidate)
    return events.drop_duplicates(columns).copy()


def prescription_support(events: pd.DataFrame, prescriptions: pd.DataFrame) -> pd.DataFrame:
    if events.empty or prescriptions.empty:
        return prescriptions.iloc[0:0].copy()
    member_rx = prescriptions[prescriptions["bene_id"] == events["bene_id"].iloc[0]]
    matches = []
    for date in events["event_date"].dropna().unique():
        delta = (member_rx["event_date"] - date).abs()
        matches.append(member_rx[delta <= pd.Timedelta(days=PRESCRIPTION_WINDOW_DAYS)])
    if not matches:
        return member_rx.iloc[0:0].copy()
    return pd.concat(matches, ignore_index=True).drop_duplicates(subset=["event_id"])


def evidence_refs(events: pd.DataFrame) -> list[dict]:
    refs = []
    for _, row in events.sort_values("event_date").iterrows():
        refs.append({
            "event_id": None if pd.isna(row.get("event_id")) else str(row.get("event_id")),
            "claim_id": None if pd.isna(row.get("claim_id")) else str(row.get("claim_id")),
            "date": row["event_date"].strftime("%Y-%m-%d"),
            "diagnosis_code": None if pd.isna(row.get("code")) else str(row.get("code")),
            "source": None if pd.isna(row.get("source")) else str(row.get("source")),
            "is_principal": bool(row.get("is_principal", False)),
        })
    return refs


def score_features(events: pd.DataFrame, rx: pd.DataFrame, reference_date: pd.Timestamp = REFERENCE_DATE) -> dict:
    empty = {
        "diagnosis_count": 0, "unique_claim_count": 0, "unique_event_count": 0,
        "first_evidence_date": None, "last_evidence_date": None,
        "distinct_evidence_dates": 0, "distinct_evidence_months": 0,
        "distinct_sources": 0, "principal_diagnosis_count": 0,
        "supporting_diagnosis_codes": [], "supporting_claim_ids": [],
        "prescription_support_count": 0, "prescription_drug_codes": [],
        "frequency_score": 0.0, "recency_score": 0.0, "persistence_score": 0.0,
        "repeated_claim_score": 0.0, "repeated_date_score": 0.0,
        "source_diversity_score": 0.0, "principal_score": 0.0,
        "prescription_score": 0.0,
        "evidence_references": [],
    }
    if events.empty:
        return empty

    events = deduplicate_events(events)
    count = len(events)
    claims = events["claim_id"].nunique(dropna=True)
    event_count = events["event_id"].nunique(dropna=True)
    dates = events["event_date"].dt.normalize().nunique()
    months = events["event_date"].dt.to_period("M").nunique()
    sources = events["source"].dropna().nunique()
    principal = int(events["is_principal"].sum())
    last_date = events["event_date"].max()
    days_since = max(0, (reference_date - last_date).days)

    frequency = 1 - math.exp(-count / 15.0)
    persistence = min(months / 4.0, 1.0)
    repeated_claim = min(claims / 3.0, 1.0)
    repeated_date = min(dates / 5.0, 1.0)
    recency = math.exp(-days_since / 365.0)
    source_diversity = min(sources / 2.0, 1.0)
    principal_score = min(principal / 2.0, 1.0)
    prescription_score = min(len(rx) / 2.0, 1.0)

    return {
        "diagnosis_count": count, "unique_claim_count": claims, "unique_event_count": event_count,
        "first_evidence_date": events["event_date"].min().strftime("%Y-%m-%d"),
        "last_evidence_date": last_date.strftime("%Y-%m-%d"),
        "distinct_evidence_dates": dates, "distinct_evidence_months": months,
        "distinct_sources": sources, "principal_diagnosis_count": principal,
        "supporting_diagnosis_codes": sorted(events["code"].dropna().astype(str).unique()),
        "supporting_claim_ids": sorted(events["claim_id"].dropna().astype(str).unique()),
        "prescription_support_count": len(rx),
        "prescription_drug_codes": sorted(rx["drug_code"].dropna().astype(str).unique()),
        "frequency_score": round(frequency, 4), "recency_score": round(recency, 4),
        "persistence_score": round(persistence, 4), "repeated_claim_score": round(repeated_claim, 4),
        "repeated_date_score": round(repeated_date, 4), "source_diversity_score": round(source_diversity, 4),
        "principal_score": round(principal_score, 4), "prescription_score": round(prescription_score, 4),
        "evidence_references": evidence_refs(events),
    }


def latest_context(gap_type: str, hcc: int, latest_hccs: dict[str, set[int]], bene_id: str) -> str:
    present = hcc in latest_hccs.get(bene_id, set())
    if gap_type == "RECAPTURE":
        return "REAPPEARED" if present else "STILL_ABSENT"
    return "CONTINUED" if present else "NOT_SEEN_LATEST"


def reason_flags(row: dict) -> list[str]:
    flags = []
    if row["recency_score"] >= 0.75:
        flags.append("RECENT_EVIDENCE")
    if row["frequency_score"] >= 0.75:
        flags.append("FREQUENT_EVIDENCE")
    if row["persistence_score"] >= 0.75:
        flags.append("PERSISTENT_EVIDENCE")
    if row["source_diversity_score"] >= 1.0:
        flags.append("MULTIPLE_SOURCE_TYPES")
    if row["principal_diagnosis_count"] > 0:
        flags.append("PRINCIPAL_DIAGNOSIS_PRESENT")
    if row["prescription_support_count"] > 0:
        flags.append("PRESCRIPTION_SUPPORTED")
    flags.append(row["latest_context"])
    return flags


def evidence_summary(row: dict) -> str:
    parts = []
    if row["diagnosis_count"]:
        parts.append(f'{row["diagnosis_count"]} supporting diagnosis event(s)')
    if row["distinct_sources"]:
        parts.append(f'{row["distinct_sources"]} source type(s)')
    if row["distinct_evidence_months"]:
        parts.append(f'evidence across {row["distinct_evidence_months"]} month(s)')
    if row["unique_claim_count"]:
        parts.append(f'{row["unique_claim_count"]} claim(s)')
    if row["principal_diagnosis_count"]:
        parts.append("includes principal diagnosis evidence")
    if row["prescription_support_count"]:
        parts.append(f'{row["prescription_support_count"]} prescription event(s) within +/-30 days')
    if row["last_evidence_date"]:
        parts.append(f'latest diagnosis evidence {row["last_evidence_date"]}')
    return "; ".join(parts) if parts else "No current evidence; review data completeness before acting"


def build_llm_record(row: dict) -> dict:
    return {
        "bene_id": str(row["bene_id"]),
        "hcc_v28": int(row["hcc_v28"]),
        "hcc_description": str(row.get("hcc_description", "")),
        "gap_type": row["gap_type"],
        "latest_context": row["latest_context"],
        "evidence_flags": row["reason_flags"],
        "evidence": {
            "diagnosis_count": int(row["diagnosis_count"]),
            "unique_claim_count": int(row["unique_claim_count"]),
            "unique_evidence_dates": int(row["distinct_evidence_dates"]),
            "evidence_months": int(row["distinct_evidence_months"]),
            "distinct_sources": int(row["distinct_sources"]),
            "principal_diagnosis_count": int(row["principal_diagnosis_count"]),
            "prescription_support_count": int(row["prescription_support_count"]),
            "first_evidence_date": row["first_evidence_date"],
            "last_evidence_date": row["last_evidence_date"],
            "diagnosis_codes": row["supporting_diagnosis_codes"],
            "claim_ids": row["supporting_claim_ids"],
            "references": row["evidence_references"],
        },
        "summary": row["evidence_summary"],
        "review_instruction": "Review the associated medical record and encounter documentation. This is not an automated diagnosis or submission decision.",
    }


def main() -> None:
    print("=" * 72)
    print("UPDATED HCC SUSPECT ENGINE")
    print("=" * 72)

    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
        print(f"Deleted existing file: {OUTPUT_FILE}")

    fallback_file = DATA_DIR / "suspects_with_evidence_final_updated.csv"
    if fallback_file.exists():
        fallback_file.unlink()

    hcc_descriptions = load_hcc_descriptions()
    baseline = load_baseline()
    timeline = load_timeline()
    prescriptions = load_prescriptions()
    baseline_hccs = build_hcc_sets(baseline)
    current_events = timeline[timeline["event_date"].dt.year == CURRENT_YEAR]
    latest_events = timeline[timeline["event_date"].dt.year == LATEST_YEAR]
    historical_events = timeline[timeline["event_date"].dt.year.isin(HISTORICAL_YEARS)]
    current_hccs = build_hcc_sets(current_events)
    latest_hccs = build_hcc_sets(latest_events)
    historical_index = {(b, h): g for (b, h), g in historical_events.groupby(["bene_id", "hcc_v28"], sort=False)}
    current_index = {(b, h): g for (b, h), g in current_events.groupby(["bene_id", "hcc_v28"], sort=False)}

    suspects = detect_gaps(baseline_hccs, current_hccs)
    rows = []
    empty_events = timeline.iloc[0:0]
    for suspect in suspects:
        key = (suspect["bene_id"], suspect["hcc_v28"])
        events = current_index.get(key) if suspect["gap_type"] == "EMERGING" else historical_index.get(key)
        events = events if events is not None else empty_events
        rx = prescription_support(events, prescriptions)
        row = {**suspect, **score_features(events, rx)}
        row["hcc_description"] = hcc_descriptions.get(int(row["hcc_v28"]), "Unknown")
        row["suspect_type"] = row["gap_type"]
        row["latest_context"] = latest_context(row["gap_type"], row["hcc_v28"], latest_hccs, row["bene_id"])
        row["reason_flags"] = reason_flags(row)
        row["evidence_summary"] = evidence_summary(row)
        rows.append(row)

    output = pd.DataFrame(rows).sort_values(["bene_id", "hcc_v28"]).reset_index(drop=True)
    column_order = [
        "bene_id", "hcc_v28", "hcc_description", "gap_type", "suspect_type", "status", "latest_context",
        "diagnosis_count", "unique_claim_count", "unique_event_count", "first_evidence_date", "last_evidence_date",
        "distinct_evidence_dates", "distinct_evidence_months", "distinct_sources", "principal_diagnosis_count",
        "supporting_diagnosis_codes", "supporting_claim_ids", "prescription_support_count", "prescription_drug_codes",
        "frequency_score", "recency_score", "persistence_score", "repeated_claim_score", "repeated_date_score",
        "source_diversity_score", "principal_score", "prescription_score", "reason_flags", "evidence_summary",
        "evidence_references"
    ]
    output = output[column_order]

    csv_output = output.copy()
    for column in ["supporting_diagnosis_codes", "supporting_claim_ids", "prescription_drug_codes", "evidence_references", "reason_flags"]:
        csv_output[column] = csv_output[column].apply(json.dumps)

    csv_output.to_csv(OUTPUT_FILE, index=False)

    llm_payload = {
        "schema_version": "1.0",
        "purpose": "Evidence-grounded reviewer explanation input",
        "instructions": "Summarize only the supplied evidence. Do not invent diagnoses, evidence, or clinical conclusions. Recommend human record review.",
        "candidates": [build_llm_record(row) for row in rows],
    }
    LLM_INPUT_FILE.write_text(json.dumps(llm_payload, indent=2), encoding="utf-8")

    print(f"Baseline members: {len(baseline_hccs):,}")
    print(f"Current mapped-diagnosis members: {len(current_hccs):,}")
    print(f"Total suspects: {len(output):,}")
    print(output["suspect_type"].value_counts().to_string())
    print(f"CSV output: {OUTPUT_FILE}")
    print(f"LLM input: {LLM_INPUT_FILE}")


if __name__ == "__main__":
    main()

