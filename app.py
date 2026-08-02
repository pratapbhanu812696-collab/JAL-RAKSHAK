"""
JAL-RAKSHAK Dashboard
AI-Driven Smart Community Health Surveillance and Early Warning System
for Water-Borne Disease Outbreaks in Rural Northeast India

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
import plotly.express as px
import plotly.graph_objects as go
import alerts

st.set_page_config(
    page_title="JAL-RAKSHAK | Early Warning Dashboard",
    page_icon="💧",
    layout="wide",
)


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

# ---------------------------------------------------------------------
# Data & model loading
# ---------------------------------------------------------------------
@st.cache_data
def load_data():
    path = "data/jal_rakshak_dataset.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_resource
def load_model():
    path = "models/outbreak_model.pkl"
    if not os.path.exists(path):
        return None
    return joblib.load(path)


df = load_data()
model = load_model()

# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
st.markdown(
    """
    <div style="background:linear-gradient(90deg,#0b5394,#1c7ed6);padding:20px 30px;border-radius:10px;">
    <h1 style="color:white;margin:0;">💧 JAL-RAKSHAK</h1>
    <p style="color:#dbeeff;margin:0;font-size:16px;">
    AI-Driven Smart Community Health Surveillance & Early Warning System for
    Water-Borne Disease Outbreaks — Rural Northeast India
    </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

if df is None or model is None:
    st.error(
        "⚠️ Data or model not found. Please make sure these files exist:\n\n"
        "`data/jal_rakshak_dataset.csv` and `models/outbreak_model.pkl`\n\n"
        "If missing, the Render Build Command should be:\n\n"
        "`pip install -r requirements.txt && python src/generate_data.py && python src/train_model.py`"
    )
    st.stop()

# ---------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------
st.sidebar.header("🔎 Filters")
villages = sorted(df["village"].unique())
selected_village = st.sidebar.selectbox("Select Village", ["All"] + villages)

date_min, date_max = df["date"].min(), df["date"].max()
date_range = st.sidebar.date_input(
    "Date range", [date_min, date_max], min_value=date_min, max_value=date_max
)

filtered = df.copy()
if selected_village != "All":
    filtered = filtered[filtered["village"] == selected_village]
if len(date_range) == 2:
    filtered = filtered[
        (filtered["date"] >= pd.to_datetime(date_range[0]))
        & (filtered["date"] <= pd.to_datetime(date_range[1]))
    ]

# ---------------------------------------------------------------------
# Live risk prediction on latest data per village
# ---------------------------------------------------------------------
latest = df.sort_values("date").groupby("village").tail(1).copy()
latest["predicted_risk"] = model.predict_proba(latest[FEATURES])[:, 1]
latest["alert_level"] = pd.cut(
    latest["predicted_risk"],
    bins=[-0.01, 0.3, 0.55, 1.01],
    labels=["🟢 Low", "🟡 Moderate", "🔴 High"],
)

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
high_risk_count = (latest["predicted_risk"] > 0.55).sum()
col1.metric("Villages Monitored", len(latest))
col2.metric("🔴 High Risk Villages", int(high_risk_count))
col3.metric("Avg Turbidity (NTU)", f"{filtered['turbidity_ntu'].mean():.1f}")
col4.metric("Total Symptom Reports", int(filtered["reported_symptom_cases"].sum()))

st.write("")

# ---------------------------------------------------------------------
# Alert panel
# ---------------------------------------------------------------------
st.subheader("🚨 Current Early Warning Status by Village")
alert_display = latest[
    ["village", "state", "predicted_risk", "alert_level", "turbidity_ntu", "reported_symptom_cases"]
].sort_values("predicted_risk", ascending=False)
alert_display["predicted_risk"] = (alert_display["predicted_risk"] * 100).round(1).astype(str) + "%"
st.dataframe(
    alert_display.rename(columns={
        "village": "Village",
        "state": "State",
        "predicted_risk": "Outbreak Risk (7-day)",
        "alert_level": "Alert Level",
        "turbidity_ntu": "Turbidity (NTU)",
        "reported_symptom_cases": "Symptom Cases",
    }),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------
st.subheader("🗺️ Geographic Risk Map")
fig_map = px.scatter_mapbox(
    latest,
    lat="latitude",
    lon="longitude",
    size="population_at_risk",
    color="predicted_risk",
    color_continuous_scale="RdYlGn_r",
    hover_name="village",
    hover_data={"state": True, "predicted_risk": ":.2f", "latitude": False, "longitude": False},
    zoom=5.2,
    height=450,
)
fig_map.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.plotly_chart(fig_map, use_container_width=True)

# ---------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("📈 Turbidity & Rainfall Trend")
    trend = filtered.groupby("date")[["turbidity_ntu", "rainfall_mm"]].mean().reset_index()
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=trend["date"], y=trend["turbidity_ntu"], name="Turbidity (NTU)", line=dict(color="#e8590c")))
    fig1.add_trace(go.Scatter(x=trend["date"], y=trend["rainfall_mm"], name="Rainfall (mm)", yaxis="y2", line=dict(color="#1c7ed6")))
    fig1.update_layout(
        yaxis=dict(title="Turbidity (NTU)"),
        yaxis2=dict(title="Rainfall (mm)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(t=30),
    )
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    st.subheader("🤒 Reported Symptom Cases Over Time")
    trend2 = filtered.groupby("date")["reported_symptom_cases"].sum().reset_index()
    fig2 = px.area(trend2, x="date", y="reported_symptom_cases", color_discrete_sequence=["#c92a2a"])
    fig2.update_layout(margin=dict(t=30), yaxis_title="Symptom Cases")
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------
# SMS / WhatsApp alert dispatch for high-risk villages
# ---------------------------------------------------------------------
st.subheader("📲 Send Outbreak Alerts")

high_risk_villages = latest[latest["predicted_risk"] > 0.55][["village", "state", "predicted_risk"]].copy()
high_risk_villages["risk"] = (high_risk_villages["predicted_risk"] * 100).round(1)
high_risk_list = high_risk_villages[["village", "state", "risk"]].to_dict("records")

if not alerts.is_configured():
    st.info(
        "SMS/WhatsApp alerts are not configured yet. Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
        "and TWILIO_FROM_NUMBER as environment variables to enable this (see README.md)."
    )
else:
    if len(high_risk_list) == 0:
        st.success("No villages currently above the high-risk threshold — no alerts needed.")
    else:
        st.warning(f"{len(high_risk_list)} village(s) are at high risk: " + ", ".join(v["village"] for v in high_risk_list))

        ac1, ac2 = st.columns([2, 1])
        with ac1:
            contact_input = st.text_input(
                "Health worker phone number(s), comma-separated (E.164 format, e.g. +919876543210)",
                placeholder="+919876543210, +919812345678",
            )
        with ac2:
            channel = st.selectbox("Channel", ["sms", "whatsapp"])

        if st.button("🚨 Send alert now"):
            contacts = [c.strip() for c in contact_input.split(",") if c.strip()]
            if not contacts:
                st.error("Enter at least one phone number.")
            else:
                results = alerts.send_bulk_alerts(high_risk_list, contacts, channel=channel)
                for r in results:
                    if r["success"]:
                        st.success(f"{r['village']} → {r['to']}: {r['message']}")
                    else:
                        st.error(f"{r['village']} → {r['to']}: {r['message']}")

# ---------------------------------------------------------------------
# Manual "What-if" risk checker (for health worker field entry)
# ---------------------------------------------------------------------
st.subheader("🧪 Manual Risk Check (Field Data Entry)")
st.caption("Enter live sensor / field readings to get an instant AI risk prediction — useful for ASHA/ANM workers without dashboard access.")

with st.form("manual_check"):
    mc1, mc2, mc3, mc4 = st.columns(4)
    rainfall_in = mc1.number_input("Rainfall (mm, last 24h)", 0.0, 300.0, 10.0)
    days_since_rain_in = mc1.number_input("Days since last rain", 0, 30, 2)
    turbidity_in = mc2.number_input("Turbidity (NTU)", 0.0, 100.0, 5.0)
    ph_in = mc2.number_input("pH Level", 4.0, 10.0, 7.0)
    do_in = mc3.number_input("Dissolved Oxygen (mg/L)", 0.0, 12.0, 6.5)
    bacteria_in = mc3.number_input("Bacterial Count (CFU/100ml)", 0.0, 1000.0, 50.0)
    symptoms_in = mc4.number_input("Reported symptom cases (last 7 days)", 0, 200, 2)
    pop_in = mc4.number_input("Population at risk", 0, 10000, 1000)

    submitted = st.form_submit_button("🔍 Predict Outbreak Risk")

if submitted:
    input_df = pd.DataFrame([{
        "rainfall_mm": rainfall_in,
        "days_since_last_rain": days_since_rain_in,
        "turbidity_ntu": turbidity_in,
        "ph_level": ph_in,
        "dissolved_oxygen_mgL": do_in,
        "bacterial_count_cfu": bacteria_in,
        "reported_symptom_cases": symptoms_in,
        "population_at_risk": pop_in,
    }])
    risk = model.predict_proba(input_df[FEATURES])[0][1]

    if risk > 0.55:
        st.error(f"🔴 HIGH RISK — {risk*100:.1f}% probability of outbreak in next 7 days. Immediate action recommended: water testing, chlorination, community alert.")
    elif risk > 0.3:
        st.warning(f"🟡 MODERATE RISK — {risk*100:.1f}% probability. Increase monitoring frequency and advise boiling water.")
    else:
        st.success(f"🟢 LOW RISK — {risk*100:.1f}% probability. Continue routine monitoring.")

st.markdown("---")
st.caption("JAL-RAKSHAK Prototype • Built for demonstration — synthetic data used for training. Not for real clinical/public health decisions without validation.")
