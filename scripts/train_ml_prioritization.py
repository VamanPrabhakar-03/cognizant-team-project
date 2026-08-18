"""Train and compare independent ML models for suspect prioritization."""

from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data/ml_training/suspects_clean_ready_for_augmentation_with_severity.csv"
SCORE_PATH = ROOT / "data/suspects_with_evidence_final.csv"
OUT_DIR = ROOT / "models/ml_prioritization"
REPORT_PATH = ROOT / "data/ml_prioritization_model_report.md"

# Features are available in both the labeled training file and final scoring file.
# Direct target columns and the already-calculated severity value are excluded.
FEATURES = [
    "diagnosis_count", "unique_claim_count", "unique_event_count",
    "distinct_evidence_dates", "distinct_evidence_months", "distinct_sources",
    "principal_diagnosis_count", "prescription_support_count",
    "frequency_score", "recency_score", "persistence_score",
    "repeated_claim_score", "repeated_date_score", "source_diversity_score",
    "principal_score", "prescription_score",
]
LABELS = ["LOW", "MEDIUM", "HIGH"]


def make_pipeline(model, scale=False):
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", model))
    return Pipeline(steps)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train = pd.read_csv(TRAIN_PATH)
    score = pd.read_csv(SCORE_PATH)
    missing = [c for c in FEATURES + ["disease_priority"] if c not in train.columns]
    if missing:
        raise ValueError(f"Missing training columns: {missing}")
    missing_score = [c for c in FEATURES if c not in score.columns]
    if missing_score:
        raise ValueError(f"Missing scoring columns: {missing_score}")

    X = train[FEATURES].apply(pd.to_numeric, errors="coerce")
    y = train["disease_priority"].astype(str).str.upper()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    models = {
        "Logistic Regression": make_pipeline(
            LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42), True
        ),
        "Random Forest": make_pipeline(
            RandomForestClassifier(n_estimators=400, class_weight="balanced", random_state=42, n_jobs=-1), False
        ),
        "Extra Trees": make_pipeline(
            ExtraTreesClassifier(n_estimators=400, class_weight="balanced", random_state=42, n_jobs=-1), False
        ),
        "HistGradientBoosting": make_pipeline(
            HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, max_leaf_nodes=15, random_state=42), False
        ),
    }

    rows = []
    details = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        cm = confusion_matrix(y_test, pred, labels=LABELS)
        report = classification_report(y_test, pred, labels=LABELS, output_dict=True, zero_division=0)
        row = {
            "model": name,
            "accuracy": accuracy_score(y_test, pred),
            "macro_precision": precision_score(y_test, pred, labels=LABELS, average="macro", zero_division=0),
            "weighted_precision": precision_score(y_test, pred, labels=LABELS, average="weighted", zero_division=0),
            "macro_f1": report["macro avg"]["f1-score"],
            "high_precision": report.get("HIGH", {}).get("precision", 0.0),
            "high_recall": report.get("HIGH", {}).get("recall", 0.0),
        }
        rows.append(row)
        details[name] = {"confusion_matrix_labels": LABELS, "confusion_matrix": cm.tolist(), "classification_report": report}
        joblib.dump(model, OUT_DIR / (name.lower().replace(" ", "_") + ".joblib"))

    comparison = pd.DataFrame(rows).sort_values(["macro_f1", "high_precision"], ascending=False)
    best_name = comparison.iloc[0]["model"]
    best_model = models[best_name]
    best_model.fit(X, y)
    score_X = score[FEATURES].apply(pd.to_numeric, errors="coerce")
    score_pred = best_model.predict(score_X)
    if hasattr(best_model, "predict_proba"):
        proba = best_model.predict_proba(score_X)
        classes = list(best_model.classes_)
        score["priority_confidence"] = proba.max(axis=1)
        score["high_priority_probability"] = proba[:, classes.index("HIGH")] if "HIGH" in classes else 0.0
    else:
        score["priority_confidence"] = np.nan
        score["high_priority_probability"] = (score_pred == "HIGH").astype(float)
    score["ml_priority"] = score_pred
    score["ml_priority_rank"] = score["ml_priority"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}).fillna(3)
    score = score.sort_values(["ml_priority_rank", "high_priority_probability", "priority_confidence"], ascending=[True, False, False])
    score.to_csv(OUT_DIR / "final_suspects_ml_prioritized.csv", index=False)
    joblib.dump(best_model, OUT_DIR / "best_model.joblib")

    comparison.to_csv(OUT_DIR / "model_comparison.csv", index=False)
    (OUT_DIR / "model_details.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    (OUT_DIR / "training_summary.json").write_text(json.dumps({
        "training_file": str(TRAIN_PATH.relative_to(ROOT)),
        "scoring_file": str(SCORE_PATH.relative_to(ROOT)),
        "rows": len(train), "test_rows": len(y_test),
        "class_distribution": y.value_counts().to_dict(),
        "features": FEATURES, "best_model": best_name,
        "scored_rows": len(score),
        "scored_priority_distribution": score["ml_priority"].value_counts().to_dict(),
    }, indent=2), encoding="utf-8")

    lines = [
        "# ML Suspect Prioritization Model Comparison", "",
        f"Training data: `{TRAIN_PATH.relative_to(ROOT)}` ({len(train):,} rows).",
        f"Scoring data: `{SCORE_PATH.relative_to(ROOT)}` ({len(score):,} rows).",
        "The target is the existing `disease_priority` label. Direct target columns and `disease_severity_score` were excluded from features.",
        "Evaluation uses a stratified 80/20 holdout split with random seed 42.", "",
        f"Best model by macro F1: **{best_name}**.", "",
        "## Comparison", "",
        "| Model | Accuracy | Macro precision | Weighted precision | High precision | High recall | Macro F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in comparison.to_dict("records"):
        lines.append(f"| {r['model']} | {r['accuracy']:.4f} | {r['macro_precision']:.4f} | {r['weighted_precision']:.4f} | {r['high_precision']:.4f} | {r['high_recall']:.4f} | {r['macro_f1']:.4f} |")
    lines += ["", "## Confusion matrices", "", "Rows are actual classes and columns are predicted classes; class order is LOW, MEDIUM, HIGH.", ""]
    for name in comparison["model"]:
        cm = details[name]["confusion_matrix"]
        lines += [f"### {name}", "", "| Actual \\ Predicted | LOW | MEDIUM | HIGH |", "|---|---:|---:|---:|"]
        for label, values in zip(LABELS, cm):
            lines.append(f"| {label} | {values[0]} | {values[1]} | {values[2]} |")
        lines.append("")
    lines += ["## Output files", "", f"- Prioritized final queue: `{(OUT_DIR / 'final_suspects_ml_prioritized.csv').relative_to(ROOT)}`", f"- Model comparison CSV: `{(OUT_DIR / 'model_comparison.csv').relative_to(ROOT)}`", f"- Saved models: `{OUT_DIR.relative_to(ROOT)}`"]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(comparison.to_string(index=False))
    print(f"Best model: {best_name}")
    print(score["ml_priority"].value_counts().to_string())


if __name__ == "__main__":
    main()
