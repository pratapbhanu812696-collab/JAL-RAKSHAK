# SmartHealthNE / SANKET — Python Demo

A Python + Streamlit prototype for community health reporting and water-quality monitoring across Northeast India.

## Run locally (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## AI risk model (new)

Water risk is now predicted by a **Random Forest** model instead of fixed if-else rules.

- **Inputs:** turbidity (NTU), free residual chlorine (mg/L), pH, and symptom cases nearby in the last 7 days.
- **Output:** a risk probability, shown as **Normal / Caution / High** plus a percentage (for example "High, 96%").
- Used in: **Water Testing** (on save), **Alert Centre** (auto alert for Caution/High), **Water Quality Map** and **Overview** (village risk).
- Code is in `ml_model.py`. Train and see accuracy, ROC-AUC and feature importance with:

```bash
python ml_model.py
```

This creates `models/outbreak_model.pkl` and `data/sanket_training_data.csv`. If the model file is missing or was made with a different scikit-learn version, the app retrains it automatically (about a second).

**Important:** the training data is **synthetic**. Outbreak labels are generated from a rule-of-thumb formula plus random noise, so the model learns that pattern, not real disease behaviour. Its accuracy is not real-world accuracy and it must not be used for real public-health decisions. Real validation needs real surveillance data.

## Demo map data

The Water Quality Map contains **25 illustrative monitoring locations across all eight Northeast states**: Assam, Arunachal Pradesh, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, and Tripura. Each row includes state, district, risk category, symptom-report count, turbidity, and chlorine values. Map coordinates are approximate. Water readings, risk categories, and report counts are fictional sample data and must not be treated as live public-health information.

The map supports filtering by state, district, and risk level. Symptom reporting and water-testing forms include state and district fields.

## Important prototype limitations

- Login is a role selector, not real authentication.
- Reports, water tests, and alerts are stored only in the current Streamlit session.
- The AI model is trained on synthetic data (see above).
- SMS, WhatsApp, and IVR alerts are simulated/not connected.
- Demo locations and water readings are illustrative, not official surveillance data.
