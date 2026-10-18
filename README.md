# JAL RAKSHAK — AI-Based Water Quality Monitoring System

JAL RAKSHAK is a Python-based water quality monitoring and risk prediction prototype designed to support community-level water safety monitoring.

## Features

- **Water Quality Monitoring:** Record turbidity, pH, and free residual chlorine levels.
- **AI-Based Risk Prediction:** Uses a Random Forest model to estimate water contamination risk.
- **Risk Classification:** Displays Normal, Caution, and High risk categories with estimated probabilities.
- **Water Quality Dashboard:** Visualizes water testing results and monitoring locations.
- **Community Health Reporting:** Records nearby symptom reports to support risk assessment.
- **Alert Centre:** Generates simulated alerts for elevated water risk.
- **Geographic Monitoring:** Demonstrates water quality monitoring across locations in Northeast India.
- **Streamlit Interface:** Provides an interactive web dashboard for demonstrations.

## Technology Stack

- Python
- Streamlit
- Scikit-learn
- Pandas
- NumPy
- Matplotlib / Plotly (if used in the implementation)

## Installation

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd jal-rakshak

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Important Limitations

This project is a prototype for educational and demonstration purposes. If synthetic training data is used, model predictions and accuracy do not represent validated real-world performance. Sample monitoring locations and readings are illustrative. The application is not a substitute for laboratory water testing or professional public-health assessment. Notifications are simulated unless connected to actual messaging services.

## Project Objective

To demonstrate how machine learning, digital water
