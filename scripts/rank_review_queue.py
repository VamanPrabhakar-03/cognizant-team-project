"""Rank deterministic HCC suspects for the human reviewer queue."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from suspect_engine.reviewer_ranker import load_severity_reference, rank_candidates  # noqa: E402


INPUT = PROJECT_ROOT / "data" / "suspects_with_evidence_final.csv"
SEVERITY_REFERENCE = PROJECT_ROOT / "data" / "hcc_severity_reference.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "review_queue"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(INPUT, low_memory=False)
    severity = None
    if SEVERITY_REFERENCE.exists() and SEVERITY_REFERENCE.stat().st_size > 80:
        severity = load_severity_reference(SEVERITY_REFERENCE)
    ranked = rank_candidates(candidates, severity)
    ranked.to_csv(OUTPUT_DIR / "ranked_suspects.csv", index=False)
    ranked[ranked["review_queue"]].to_csv(OUTPUT_DIR / "top_100_review_queue.csv", index=False)

    report = {
        "input": str(INPUT.relative_to(PROJECT_ROOT)),
        "total_deterministic_candidates": int(len(ranked)),
        "top_100_candidates": int(ranked["review_queue"].sum()),
        "severity_reference": str(SEVERITY_REFERENCE.relative_to(PROJECT_ROOT)) if severity is not None else None,
        "severity_status_counts": ranked["severity_reference_status"].value_counts().to_dict(),
        "ranking_model": "evidence_urgency_severity_v1",
        "note": "This layer ranks deterministic candidates; it does not determine whether a gap exists.",
    }
    (OUTPUT_DIR / "ranking_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(ranked[["review_rank", "bene_id", "hcc_v28", "gap_type", "review_priority_score", "severity_reference_status"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
