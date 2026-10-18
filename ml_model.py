
"""
JAL RAKSHAK ML Module - Water Quality Risk Prediction Model.

What it does
------------
1. Generates a SYNTHETIC training dataset (fictional, not real-world water
   quality or disease surveillance data).
2. Trains a Random Forest classifier on the synthetic dataset.
3. Provides a predict_risk() function that returns a predicted water-risk
   probability for the application.

Run this file directly to (re)train the model and view its evaluation:

    python ml_model.py

The app (app.py) also calls load_or_train() automatically. If the saved model
file is missing or was created with an incompatible scikit-learn version,
the application retrains it automatically.

IMPORTANT
---------
The model is trained on synthetic data and is intended for demonstration
and educational purposes only. Its predictions and evaluation metrics do
not establish real-world water contamination or disease outbreak accuracy.
Real-world use requires appropriate field data, independent validation,
and expert assessment.
"""


import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "outbreak_model.pkl")
DATA_PATH = os.path.join(BASE_DIR, "data", "sanket_training_data.csv")

# These 4 inputs match the fields an ASHA worker already fills in the app.
FEATURES = ["turbidity_ntu", "chlorine_mgL", "ph_level", "symptom_cases"]
TARGET = "outbreak_risk"

# Risk labels used everywhere in the app (same words as before: Normal / Caution / High)
CAUTION_THRESHOLD = 0.30
HIGH_THRESHOLD = 0.60


def generate_dataset(n_rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Create fictional training data.

    IMPORTANT: the outbreak label is produced from a simple rule-of-thumb formula
    (higher turbidity, low chlorine, abnormal pH and more symptom cases mean higher
    risk) plus random noise. The model therefore learns this synthetic pattern, NOT
    real-world disease behaviour. Its accuracy must not be read as real-world accuracy.
    """
    rng = np.random.default_rng(seed)

    turbidity = np.clip(rng.gamma(shape=2.0, scale=1.6, size=n_rows), 0.1, 40)
    # cloudy water usually has less free chlorine left
    chlorine = np.clip(rng.normal(0.5 - 0.04 * turbidity, 0.18, size=n_rows), 0.0, 2.0)
    ph = np.clip(rng.normal(7.2, 0.7, size=n_rows), 5.0, 9.5)
    symptoms = rng.poisson(1.5 + 0.35 * turbidity, size=n_rows).clip(0, 60)

    score = (
        -2.2
        + 0.35 * np.maximum(0, turbidity - 1)
        + 2.5 * np.maximum(0, 0.5 - chlorine)
        + 0.9 * np.abs(ph - 7.2)
        + 0.25 * symptoms
    )
    probability = 1 / (1 + np.exp(-score))
    label = rng.binomial(1, probability)  # random draw, so labels are noisy like real life

    return pd.DataFrame(
        {
            "turbidity_ntu": turbidity.round(2),
            "chlorine_mgL": chlorine.round(2),
            "ph_level": ph.round(2),
            "symptom_cases": symptoms,
            TARGET: label,
        }
    )


def train_and_save(verbose: bool = False):
    """Generate data, train the Random Forest, save model + dataset. Returns the model."""
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)

    df = generate_dataset()
    df.to_csv(DATA_PATH, index=False)

    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURES], df[TARGET], test_size=0.2, random_state=42, stratify=df[TARGET]
    )
    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42
    )
    model.fit(X_train, y_train)

    if verbose:
        pred = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        print("=" * 56)
        print("SANKET outbreak-risk model - evaluation (synthetic data)")
        print("=" * 56)
        print(f"Training rows : {len(X_train)}   Test rows: {len(X_test)}")
        print(f"Accuracy      : {accuracy_score(y_test, pred):.3f}")
        print(f"ROC-AUC       : {roc_auc_score(y_test, proba):.3f}")
        print("\nClassification report:")
        print(classification_report(y_test, pred, target_names=["No outbreak", "Outbreak risk"]))
        print("Confusion matrix:")
        print(confusion_matrix(y_test, pred))
        print("\nFeature importance:")
        print(pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False).round(3))
        print(f"\nModel saved -> {MODEL_PATH}")
        print(f"Dataset saved -> {DATA_PATH}")

    joblib.dump(model, MODEL_PATH)
    return model


def load_or_train():
    """Load the saved model. If it is missing or incompatible, retrain automatically."""
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            pass  # e.g. saved with a different scikit-learn version -> retrain below
    return train_and_save()


def predict_risk(model, turbidity: float, chlorine: float, ph: float, symptom_cases: int):
    """Return (probability 0-1, label 'Normal' / 'Caution' / 'High')."""
    row = pd.DataFrame(
        [{"turbidity_ntu": turbidity, "chlorine_mgL": chlorine, "ph_level": ph, "symptom_cases": symptom_cases}]
    )[FEATURES]
    prob = float(model.predict_proba(row)[0][1])
    if prob >= HIGH_THRESHOLD:
        label = "High"
    elif prob >= CAUTION_THRESHOLD:
        label = "Caution"
    else:
        label = "Normal"
    return prob, label


if __name__ == "__main__":
    train_and_save(verbose=True)
