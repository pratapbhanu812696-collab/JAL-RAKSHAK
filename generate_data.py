"""
JAL-RAKSHAK: Synthetic Data Generator
Generates realistic sample data for:
- Water quality sensor readings
- Weather/rainfall data
- Community health (symptom) reports
for villages in Rural Northeast India (simulated).

Run this first to create data/jal_rakshak_dataset.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Simulated villages across NE India (Assam, Meghalaya, Manipur, etc.)
VILLAGES = [
    {"name": "Majuli", "state": "Assam", "lat": 26.95, "lon": 94.17},
    {"name": "Shillong Rural", "state": "Meghalaya", "lat": 25.57, "lon": 91.88},
    {"name": "Imphal East", "state": "Manipur", "lat": 24.82, "lon": 93.95},
    {"name": "Dimapur", "state": "Nagaland", "lat": 25.90, "lon": 93.72},
    {"name": "Agartala Rural", "state": "Tripura", "lat": 23.83, "lon": 91.28},
    {"name": "Aizawl Rural", "state": "Mizoram", "lat": 23.73, "lon": 92.72},
    {"name": "Itanagar Rural", "state": "Arunachal Pradesh", "lat": 27.10, "lon": 93.62},
]

N_DAYS = 180  # ~6 months of daily data
START_DATE = datetime(2026, 1, 1)


def simulate_outbreak_risk(turbidity, ph, rainfall_mm, days_since_rain, reported_symptoms):
    """
    Ground-truth risk simulation logic (used only to LABEL synthetic data,
    the ML model will later learn to predict this from features).
    Higher turbidity + extreme pH + heavy rainfall + more symptoms -> higher outbreak probability.
    """
    risk_score = 0.0
    risk_score += max(0, (turbidity - 5)) * 0.12           # NTU above safe limit (5 NTU)
    risk_score += abs(ph - 7.0) * 0.15                      # deviation from neutral pH
    risk_score += min(rainfall_mm / 25, 2.5)                 # heavy rain -> contamination risk
    risk_score += max(0, (5 - days_since_rain)) * 0.10       # recent rain = stagnant water risk
    risk_score += reported_symptoms * 0.20                   # actual symptom clustering

    prob = 1 / (1 + np.exp(-(risk_score - 2.0)))  # sigmoid squashing
    return np.clip(prob + np.random.normal(0, 0.05), 0, 1)


rows = []
for village in VILLAGES:
    days_since_rain = 0
    for day in range(N_DAYS):
        date = START_DATE + timedelta(days=day)

        # Seasonal rainfall pattern (monsoon-heavy for NE India, peaks Jun-Sep)
        month = date.month
        seasonal_factor = 3.0 if month in [6, 7, 8, 9] else 1.0
        rainfall = max(0, np.random.exponential(8 * seasonal_factor))
        days_since_rain = 0 if rainfall > 2 else days_since_rain + 1

        # Water quality sensor readings
        turbidity = np.clip(np.random.normal(4 + (rainfall / 10), 2), 0.5, 60)  # NTU
        ph = np.clip(np.random.normal(7.0, 0.6), 5.0, 9.5)
        dissolved_oxygen = np.clip(np.random.normal(6.5, 1.2), 1.0, 10.0)  # mg/L
        bacterial_count = np.clip(
            np.random.normal(50 + turbidity * 8, 30), 0, None
        )  # CFU/100ml (E. coli proxy)

        # Community-reported symptoms (diarrhea, vomiting, fever cases per 1000 pop)
        base_symptoms = np.random.poisson(2)
        symptom_boost = int(turbidity > 15) * np.random.poisson(3)
        reported_symptoms = base_symptoms + symptom_boost

        # Ground truth outbreak risk probability -> binary label
        risk_prob = simulate_outbreak_risk(
            turbidity, ph, rainfall, days_since_rain, reported_symptoms
        )
        outbreak_next_7days = 1 if risk_prob > 0.45 else 0

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "village": village["name"],
            "state": village["state"],
            "latitude": village["lat"],
            "longitude": village["lon"],
            "rainfall_mm": round(rainfall, 2),
            "days_since_last_rain": days_since_rain,
            "turbidity_ntu": round(turbidity, 2),
            "ph_level": round(ph, 2),
            "dissolved_oxygen_mgL": round(dissolved_oxygen, 2),
            "bacterial_count_cfu": round(bacterial_count, 1),
            "reported_symptom_cases": reported_symptoms,
            "population_at_risk": np.random.randint(300, 3000),
            "outbreak_risk_probability": round(risk_prob, 3),
            "outbreak_next_7days": outbreak_next_7days,
        })

df = pd.DataFrame(rows)
df.to_csv("data/jal_rakshak_dataset.csv", index=False)
print(f"Generated {len(df)} rows -> data/jal_rakshak_dataset.csv")
print(f"Outbreak-positive rate: {df['outbreak_next_7days'].mean():.2%}")
print(df.head())
