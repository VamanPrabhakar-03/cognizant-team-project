"""Train the augmented HCC priority SVM and score deterministic suspects."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_FILE = PROJECT_ROOT / "data" / "ml_training" / "hcc_augmented_3500_full_dataset.csv"
SCORING_FILE = PROJECT_ROOT / "data" / "suspects_with_evidence_final.csv"
MODEL_DIR = PROJECT_ROOT / "models" / "ml_prioritization"
MODEL_PATH = MODEL_DIR / "hcc_svm_model.pkl"
INFERENCE_PATH = MODEL_DIR / "suspects_ml_inference.csv"
METRICS_PATH = MODEL_DIR / "hcc_svm_training_metrics.json"

TARGET_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
LABELS = ["LOW", "MEDIUM", "HIGH"]
FEATURES = [
    "hcc_v28", "gap_type", "suspect_type", "status", "latest_context",
    "diagnosis_count", "unique_claim_count", "unique_event_count",
    "distinct_evidence_dates", "distinct_evidence_months", "distinct_sources",
    "principal_diagnosis_count", "prescription_support_count",
]


def make_model(features: list[str], frame: pd.DataFrame) -> Pipeline:
    categorical = [column for column in features if not is_numeric_dtype(frame[column])]
    numeric = [column for column in features if column not in categorical]
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipeline, numeric),
        ("categorical", categorical_pipeline, categorical),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", SVC(
            C=2.0, kernel="rbf", gamma="scale", class_weight="balanced",
            probability=True, random_state=42,
        )),
    ])


def prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    prepared = frame.copy()
    for column in features:
        if column not in prepared.columns:
            prepared[column] = None
    return prepared[features]


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    train = pd.read_csv(TRAINING_FILE, low_memory=False)
    train["disease_priority"] = train["disease_priority"].astype(str).str.upper().str.strip()
    train = train[train["disease_priority"].isin(TARGET_MAP)].copy()
    features = [feature for feature in FEATURES if feature in train.columns]
    train["target"] = train["disease_priority"].map(TARGET_MAP).astype(int)

    patient_target = train.groupby("bene_id")["target"].agg(lambda values: values.mode().iloc[0])
    patients = patient_target.index
    train_patients, temp_patients = train_test_split(
        patients, test_size=0.30, random_state=42, stratify=patient_target.values
    )
    val_patients, test_patients = train_test_split(
        temp_patients, test_size=0.50, random_state=42,
        stratify=patient_target.loc[temp_patients].values,
    )
    train_df = train[train["bene_id"].isin(set(train_patients))]
    val_df = train[train["bene_id"].isin(set(val_patients))]
    test_df = train[train["bene_id"].isin(set(test_patients))]

    model = make_model(features, train_df)
    model.fit(prepare(train_df, features), train_df["target"])
    val_pred = model.predict(prepare(val_df, features))
    test_pred = model.predict(prepare(test_df, features))

    scoring = pd.read_csv(SCORING_FILE, low_memory=False)
    scoring_features = prepare(scoring, features)
    probabilities = model.predict_proba(scoring_features)
    # Use the calibrated probability argmax so the displayed label agrees with
    # the probability columns and the expected-value ranking score.
    predicted = probabilities.argmax(axis=1).astype(int)
    scored = scoring[["bene_id", "hcc_v28", "gap_type", "suspect_type", "status"]].copy()
    scored["ml_priority"] = [LABELS[value] for value in predicted]
    scored["ml_priority_score"] = (probabilities @ pd.Series([0.0, 0.5, 1.0]).to_numpy()).round(4)
    scored["ml_low_probability"] = probabilities[:, 0].round(4)
    scored["ml_medium_probability"] = probabilities[:, 1].round(4)
    scored["ml_high_probability"] = probabilities[:, 2].round(4)
    scored["ml_model_version"] = "hcc_svm_priority_v1"
    scored = scored.sort_values(
        ["ml_priority_score", "ml_high_probability"], ascending=[False, False]
    ).reset_index(drop=True)
    scored["ml_review_rank"] = scored.index + 1
    scored["ml_top_100"] = scored["ml_review_rank"] <= 100
    scored.to_csv(INFERENCE_PATH, index=False)
    joblib.dump(model, MODEL_PATH)

    metrics = {
        "training_file": str(TRAINING_FILE.relative_to(PROJECT_ROOT)),
        "scoring_file": str(SCORING_FILE.relative_to(PROJECT_ROOT)),
        "model_file": str(MODEL_PATH.relative_to(PROJECT_ROOT)),
        "model": "SVC RBF",
        "class_weight": "balanced",
        "features": features,
        "training_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "class_distribution": train["disease_priority"].value_counts().to_dict(),
        "validation": {
            "accuracy": float(accuracy_score(val_df["target"], val_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(val_df["target"], val_pred)),
            "macro_f1": float(f1_score(val_df["target"], val_pred, average="macro", zero_division=0)),
        },
        "test": {
            "accuracy": float(accuracy_score(test_df["target"], test_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(test_df["target"], test_pred)),
            "macro_f1": float(f1_score(test_df["target"], test_pred, average="macro", zero_division=0)),
            "classification_report": classification_report(test_df["target"], test_pred, target_names=LABELS, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(test_df["target"], test_pred).tolist(),
        },
        "inference_rows": int(len(scored)),
        "inference_priority_distribution": scored["ml_priority"].value_counts().to_dict(),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
