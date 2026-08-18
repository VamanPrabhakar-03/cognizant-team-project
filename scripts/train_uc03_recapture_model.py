"""Train and evaluate a leakage-safe UC03 recapture model.

Training uses only the 2019-2021 feature window. Stratified cross-validation is
used for development metrics, while the 2023 file is reserved for temporal
holdout evaluation. Logistic regression uses class_weight='balanced'.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "ml_training"
MODEL_DIR = PROJECT_ROOT / "models"
REPORT_DIR = PROJECT_ROOT / "docs" / "ml"
FEATURE_COLUMNS = [
    "diagnosis_count", "unique_icd_count", "active_years",
    "days_since_last_diagnosis", "unique_claim_count", "source_count",
    "inpatient_count", "outpatient_count", "carrier_count",
    "principal_diagnosis_count",
]


def metrics(y_true: pd.Series, probabilities: np.ndarray, threshold: float = 0.5) -> dict:
    predictions = (probabilities >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(average_precision_score(y_true, probabilities)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "positive_rate_at_threshold": float(predictions.mean()),
    }


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(DATA_DIR / "uc03_recapture_training_dataset.csv")
    holdout = pd.read_csv(DATA_DIR / "uc03_recapture_holdout_2023.csv")
    X = train[FEATURE_COLUMNS]
    y = train["TARGET"].astype(int)
    X_holdout = holdout[FEATURE_COLUMNS]
    y_holdout = holdout["HOLDOUT_TARGET_2023"].astype(int)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            class_weight="balanced", max_iter=2000, solver="liblinear", random_state=42
        )),
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_probabilities = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    cv_metrics = metrics(y, cv_probabilities)

    model.fit(X, y)
    holdout_probabilities = model.predict_proba(X_holdout)[:, 1]
    holdout_metrics = metrics(y_holdout, holdout_probabilities)

    # Save the fitted pipeline and a scored holdout for downstream ranking/UI work.
    joblib.dump(model, MODEL_DIR / "uc03_recapture_logistic_balanced.joblib")
    scored = holdout[["bene_id", "hcc_v28"]].copy()
    scored["holdout_target_2023"] = y_holdout
    scored["recapture_probability"] = holdout_probabilities
    scored.sort_values("recapture_probability", ascending=False).to_csv(
        MODEL_DIR / "uc03_recapture_holdout_scored.csv", index=False
    )

    summary = {
        "model": "standardized logistic regression",
        "class_weight": "balanced",
        "cross_validation": {"method": "5-fold StratifiedKFold", "shuffle": True, "random_state": 42},
        "feature_period": "2019-01-01 through 2021-12-31",
        "training_target_period": "2022-01-01 through 2022-12-31",
        "temporal_holdout_period": "2023-01-01 through 2023-12-31",
        "training_rows": int(len(train)),
        "training_positive_rate": float(y.mean()),
        "cv_metrics": cv_metrics,
        "holdout_metrics": holdout_metrics,
        "features": FEATURE_COLUMNS,
    }
    (MODEL_DIR / "uc03_recapture_training_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    report = f"""# UC03 Recapture Model Training Report

## Model

- Standardized logistic regression
- `class_weight=balanced`
- 5-fold shuffled `StratifiedKFold` cross-validation
- Model fit uses only 2019–2021 features and the 2022 target.
- 2023 is a temporal holdout and is not used for fitting or model selection.

## Cross-validation metrics

| Metric | Value |
|---|---:|
| ROC-AUC | {cv_metrics['roc_auc']:.4f} |
| Average precision (PR-AUC) | {cv_metrics['average_precision']:.4f} |
| Balanced accuracy | {cv_metrics['balanced_accuracy']:.4f} |
| Precision | {cv_metrics['precision']:.4f} |
| Recall | {cv_metrics['recall']:.4f} |
| F1 | {cv_metrics['f1']:.4f} |

## 2023 temporal holdout metrics

| Metric | Value |
|---|---:|
| ROC-AUC | {holdout_metrics['roc_auc']:.4f} |
| Average precision (PR-AUC) | {holdout_metrics['average_precision']:.4f} |
| Balanced accuracy | {holdout_metrics['balanced_accuracy']:.4f} |
| Precision | {holdout_metrics['precision']:.4f} |
| Recall | {holdout_metrics['recall']:.4f} |
| F1 | {holdout_metrics['f1']:.4f} |

These metrics evaluate temporal recapture behavior, not confirmed documentation gaps.
"""
    (REPORT_DIR / "uc03_recapture_model_training_report.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
