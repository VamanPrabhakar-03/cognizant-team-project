"""Explainable post-detection ranking for the human reviewer queue.

This module never creates or removes suspects. It only orders candidates that
already passed deterministic gap detection. Severity is read from an explicit
reference table; HCC numeric values are never treated as severity ranks.
"""

from __future__ import annotations

import pandas as pd


BASE_EVIDENCE_WEIGHTS = {
    "frequency_score": 0.18,
    "persistence_score": 0.18,
    "recency_score": 0.15,
    "repeated_claim_score": 0.15,
    "repeated_date_score": 0.15,
    "source_diversity_score": 0.08,
    "principal_score": 0.08,
    "prescription_score": 0.03,
}


def load_severity_reference(path) -> pd.DataFrame:
    """Load optional CMS/clinical severity metadata keyed by HCC V28."""
    reference = pd.read_csv(path, dtype={"hcc_v28": "string"})
    required = {"hcc_v28", "severity_level"}
    missing = required - set(reference.columns)
    if missing:
        raise ValueError(f"Severity reference is missing columns: {sorted(missing)}")
    reference["hcc_v28"] = reference["hcc_v28"].astype("string").str.strip()
    reference["severity_level"] = pd.to_numeric(reference["severity_level"], errors="coerce")
    if reference["severity_level"].isna().any():
        raise ValueError("severity_level must be numeric for every HCC reference row")
    if reference["hcc_v28"].duplicated().any():
        raise ValueError("Severity reference must contain one row per HCC V28")
    return reference


def rank_candidates(candidates: pd.DataFrame, severity_reference: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rank deterministic candidates for review, preserving all source fields."""
    if candidates.empty:
        return candidates.copy()

    ranked = candidates.copy()
    for column in BASE_EVIDENCE_WEIGHTS:
        ranked[column] = pd.to_numeric(ranked.get(column, 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)

    ranked["evidence_strength_score"] = sum(
        ranked[column] * weight for column, weight in BASE_EVIDENCE_WEIGHTS.items()
    ).round(4)
    ranked["gap_urgency_score"] = ranked.apply(
        lambda row: 1.0 if str(row.get("gap_type", "")).upper() == "EMERGING"
        else (0.85 if str(row.get("latest_context", "")).upper() == "STILL_ABSENT" else 0.65),
        axis=1,
    )

    # Severity is deliberately neutral until an authoritative reference is supplied.
    ranked["severity_score"] = 0.0
    ranked["severity_delta_score"] = 0.0
    ranked["severity_reference_status"] = "NOT_AVAILABLE"
    if severity_reference is not None and not severity_reference.empty:
        ref = severity_reference[["hcc_v28", "severity_level"]].copy()
        ref["hcc_v28"] = ref["hcc_v28"].astype("string").str.strip()
        ranked["_hcc_key"] = ranked["hcc_v28"].astype("string").str.strip()
        ranked = ranked.merge(ref.rename(columns={"severity_level": "severity_score"}),
                              left_on="_hcc_key", right_on="hcc_v28", how="left", suffixes=("", "_ref"))
        ranked["severity_score"] = pd.to_numeric(ranked["severity_score"], errors="coerce")
        max_severity = ranked["severity_score"].max()
        if pd.notna(max_severity) and max_severity > 0:
            ranked["severity_score"] = (ranked["severity_score"] / max_severity).fillna(0.0).clip(0.0, 1.0)
        ranked["severity_reference_status"] = ranked["severity_score"].apply(
            lambda value: "AVAILABLE" if value > 0 else "MISSING_HCC_REFERENCE"
        )
        ranked = ranked.drop(columns=["_hcc_key", "hcc_v28_ref"], errors="ignore")

    # Evidence remains dominant. Severity is a prioritization signal, never a gap decision.
    severity_weight = 0.20 if (ranked["severity_reference_status"] == "AVAILABLE").any() else 0.0
    evidence_weight = 0.65 if severity_weight else 0.78
    urgency_weight = 1.0 - evidence_weight - severity_weight
    ranked["review_priority_score"] = (
        evidence_weight * ranked["evidence_strength_score"]
        + urgency_weight * ranked["gap_urgency_score"]
        + severity_weight * ranked["severity_score"]
    ).round(4)
    ranked["ranking_model"] = "evidence_urgency_severity_v1"
    ranked = ranked.sort_values(
        ["review_priority_score", "evidence_strength_score", "diagnosis_count"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["review_rank"] = ranked.index + 1
    ranked["review_queue"] = ranked["review_rank"] <= 100
    return ranked
