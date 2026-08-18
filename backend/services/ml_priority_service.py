"""Load the trained HCC priority SVM and score deterministic candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "ml_prioritization" / "hcc_svm_model.pkl"
FEATURES = [
    "hcc_v28", "gap_type", "suspect_type", "status", "latest_context",
    "diagnosis_count", "unique_claim_count", "unique_event_count",
    "distinct_evidence_dates", "distinct_evidence_months", "distinct_sources",
    "principal_diagnosis_count", "prescription_support_count",
]
LABELS = ["LOW", "MEDIUM", "HIGH"]
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        import warnings
        import joblib
        from sklearn.exceptions import InconsistentVersionWarning

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            _MODEL = joblib.load(MODEL_PATH)
    return _MODEL


def score_candidates(candidates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return ML priority fields aligned to the candidate input order."""
    if not candidates or not MODEL_PATH.exists():
        return [{} for _ in candidates]
    frame = pd.DataFrame(candidates)
    for column in FEATURES:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[FEATURES]
    model = _model()
    probabilities = model.predict_proba(frame)
    # Keep the displayed class aligned with the probability-based ranking.
    predictions = probabilities.argmax(axis=1).astype(int)
    output = []
    for index, prediction in enumerate(predictions):
        probs = probabilities[index]
        score = float(probs @ [0.0, 0.5, 1.0])
        output.append({
            "ml_priority": LABELS[int(prediction)],
            "ml_priority_score": round(score, 4),
            "ml_low_probability": round(float(probs[0]), 4),
            "ml_medium_probability": round(float(probs[1]), 4),
            "ml_high_probability": round(float(probs[2]), 4),
            "ml_model_version": "hcc_svm_priority_v1",
        })
    order = sorted(range(len(output)), key=lambda i: output[i]["ml_priority_score"], reverse=True)
    ranks = {index: rank + 1 for rank, index in enumerate(order)}
    for index, row in enumerate(output):
        row["ml_review_rank"] = ranks[index]
        row["ml_top_100"] = ranks[index] <= 100
    return output
