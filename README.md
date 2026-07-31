💧 JAL-RAKSHAK

AI-Driven Smart Community Health Surveillance and Early Warning System for Water-Borne Disease Outbreaks in Rural Northeast India

A prototype system that combines water quality sensor data, weather/rainfall patterns, and community-reported symptoms to predict water-borne disease outbreak risk (cholera, typhoid, diarrhea, etc.) using machine learning, and presents it via an interactive dashboard.

📁 Project Structure
jal-rakshak/
├── app.py                  # Streamlit dashboard (main app)
├── requirements.txt        # Python dependencies
├── data/
│   └── jal_rakshak_dataset.csv   # generated synthetic dataset
├── models/
│   └── outbreak_model.pkl        # trained ML model
└── src/
    ├── generate_data.py    # creates synthetic dataset
    └── train_model.py      # trains the Random Forest model
🚀 Setup Instructions (VS Code)
1. Open the folder in VS Code

Unzip the project and open the jal-rakshak folder in VS Code (File > Open Folder).

2. Create a virtual environment (recommended)
bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
3. Install dependencies
bash
pip install -r requirements.txt
4. Generate the synthetic dataset
bash
python src/generate_data.py

This creates data/jal_rakshak_dataset.csv — 180 days of simulated water quality, weather, and symptom data across 7 villages in NE India.

5. Train the ML model
bash
python src/train_model.py

This trains a Random Forest classifier and saves it to models/outbreak_model.pkl. You'll see accuracy, ROC-AUC, and feature importance printed in the terminal.

6. Launch the dashboard
bash
streamlit run app.py

This opens the dashboard in your browser at http://localhost:8501.

🧠 How It Works
Data Layer — Simulated inputs: turbidity, pH, dissolved oxygen, bacterial count, rainfall, days since rain, reported symptom cases, population at risk.
ML Model — A Random Forest classifier predicts outbreak_next_7days (0/1) and risk probability from these features.
Dashboard — Shows:
Village-wise risk table with 🟢🟡🔴 alert levels
Geographic risk map
Turbidity/rainfall and symptom trend charts
A manual "what-if" form so a field health worker (ASHA/ANM) can type in readings and get an instant risk prediction
🔧 Extending This Prototype
Replace src/generate_data.py output with real IoT sensor feeds (e.g., MQTT from turbidity/pH probes)
Connect to real rainfall APIs (IMD, OpenWeatherMap)
Add an SMS/WhatsApp bot (Twilio API) for symptom self-reporting and alert dispatch
Swap Random Forest for XGBoost/LSTM if you have real historical outbreak data
Add authentication + role-based views (District Health Officer vs ASHA worker)
Deploy on a cloud VM or Streamlit Community Cloud for public access
⚠️ Disclaimer

This is a prototype using synthetic data for demonstration, hackathon, or academic purposes. It is not validated for real clinical or public health decision-making.
