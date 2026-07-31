"""
JAL-RAKSHAK: Outbreak Risk Prediction Model
Trains a Random Forest classifier to predict water-borne disease outbreak
risk (next 7 days) using water quality, weather, and community health features.

Run after generate_data.py.
Saves trained model -> models/outbreak_model.pkl
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, accuracy_score
)
import joblib
import os

os.makedirs("models", exist_ok=True)

FEATURES = [
    "rainfall_mm",
    "days_since_last_rain",
    "turbidity_ntu",
    "ph_level",
    "dissolved_oxygen_mgL",
    "bacterial_count_cfu",
    "reported_symptom_cases",
    "population_at_risk",
]
TARGET = "outbreak_next_7days"


def train():
    df = pd.read_csv("data/jal_rakshak_dataset.csv")

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print("=" * 50)
    print("JAL-RAKSHAK Outbreak Prediction Model — Evaluation")
    print("=" * 50)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print(f"ROC-AUC:  {roc_auc_score(y_test, y_proba):.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["No Outbreak", "Outbreak Risk"]))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # Feature importance
    importance = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print("\nFeature Importance:")
    print(importance)

    joblib.dump(model, "models/outbreak_model.pkl")
    print("\nModel saved -> models/outbreak_model.pkl")


if __name__ == "__main__":
    train()
