import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
import ml_model
import sqlite3, json, os, time, html

# --- Shared database (SQLite). All roles read and write the same file, so data persists across refresh and sign-out. ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jal_rakshak.db")
SEED_ALERTS = [  # oldest first
    {"level":"WATER CAUTION", "title":"Water source needs retesting", "place":"Ward 3 handpump · Nagaon", "time":"Yesterday, 04:15 PM", "detail":"Turbidity reading is above the suggested threshold."},
    {"level":"HIGH RISK", "title":"Possible diarrhoeal cluster detected", "place":"Barkola village · Sonitpur", "time":"Today, 09:40 AM", "detail":"8 symptom reports recorded in the last 48 hours."},
]

def _conn():
    return sqlite3.connect(DB_PATH, timeout=10)

def _create_tables(c):
    for t in ("reports", "water_tests", "concerns", "alerts"):
        c.execute(f"CREATE TABLE IF NOT EXISTS {t} (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS actions (village TEXT PRIMARY KEY, data TEXT NOT NULL)")

def _seed(c):
    for a in SEED_ALERTS:
        c.execute("INSERT INTO alerts (data) VALUES (?)", (json.dumps(a, ensure_ascii=False),))

def init_db():
    is_new = not os.path.exists(DB_PATH)
    c = _conn()
    try:
        _create_tables(c)
        if is_new:
            _seed(c)
        c.commit()
    finally:
        c.close()

def _insert(table, rec):
    c = _conn()
    try:
        cur = c.execute(f"INSERT INTO {table} (data) VALUES (?)", (json.dumps(rec, ensure_ascii=False),))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()

def db_add(table, rec):
    rec = dict(rec)
    rec["Submitted"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
    rec["_ts"] = time.time()
    return _insert(table, rec)

def db_all(table, with_meta=False):
    """Newest first. with_meta=True keeps the hidden _id and _ts fields."""
    c = _conn()
    try:
        rows = c.execute(f"SELECT id, data FROM {table} ORDER BY id DESC").fetchall()
    finally:
        c.close()
    out = []
    for rid, data in rows:
        d = json.loads(data)
        if with_meta:
            d["_id"] = rid
        else:
            d = {k: v for k, v in d.items() if not k.startswith("_")}
        out.append(d)
    return out

def get_alerts():
    return db_all("alerts", True)

def add_alert(alert, src=None):
    safe = {k: (html.escape(v) if isinstance(v, str) else v) for k, v in alert.items()}
    safe["_ts"] = time.time()
    if src:
        safe["_src"] = src  # links the alert to the record that created it, e.g. "reports:12"
    _insert("alerts", safe)

def delete_alerts_for(table, rid):
    src = f"{table}:{rid}"
    c = _conn()
    try:
        for aid, data in c.execute("SELECT id, data FROM alerts").fetchall():
            if json.loads(data).get("_src") == src:
                c.execute("DELETE FROM alerts WHERE id = ?", (aid,))
        c.commit()
    finally:
        c.close()

def db_update(table, rid, rec):
    c = _conn()
    try:
        row = c.execute(f"SELECT data FROM {table} WHERE id = ?", (rid,)).fetchone()
        if row is None:
            return False
        old = json.loads(row[0])
        new = dict(rec)
        for k in ("_ts", "Submitted"):
            if k in old:
                new[k] = old[k]
        new["Edited"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
        c.execute(f"UPDATE {table} SET data = ? WHERE id = ?", (json.dumps(new, ensure_ascii=False), rid))
        c.commit()
        return True
    finally:
        c.close()

def db_delete(table, rid):
    c = _conn()
    try:
        c.execute(f"DELETE FROM {table} WHERE id = ?", (rid,))
        c.commit()
    finally:
        c.close()
    delete_alerts_for(table, rid)

def flash(msg):
    st.session_state["_flash"] = msg

def report_alerts(rid, rec):
    delete_alerts_for("reports", rid)
    cases, sev, place = int(rec["Cases"]), rec["Urgency"], f"{rec['Village']} · {rec['District']}"
    when = datetime.now().strftime("Today, %I:%M %p")
    if sev == "Urgent" or cases >= 5:
        add_alert({"level":"HIGH RISK","title":"Symptom report requires review","place":place,"time":when,"detail":f"{cases} people reported; symptoms: {rec['Symptoms']}."}, src=f"reports:{rid}")
    else:
        add_alert({"level":"FIELD REPORT","title":"Symptom report received","place":place,"time":when,"detail":f"{cases} person(s) reported; symptoms: {rec['Symptoms']}. Urgency: {sev}."}, src=f"reports:{rid}")

def water_alerts(rid, rec, risk_text):
    delete_alerts_for("water_tests", rid)
    if rec["Risk"] != "Normal":
        add_alert({"level":"WATER CAUTION" if rec["Risk"]=="Caution" else "HIGH RISK","title":"Water quality reading flagged for follow-up","place":f"{rec['Village']} · {rec['District']}","time":datetime.now().strftime("Today, %I:%M %p"),"detail":f"Turbidity {rec['Turbidity (NTU)']} NTU, chlorine {rec['Chlorine (mg/L)']} mg/L, pH {rec['pH']}, {int(rec['Symptom cases (7d)'])} nearby symptom case(s). AI risk: {risk_text}. Verify readings and follow local guidance."}, src=f"water_tests:{rid}")

def concern_alerts(rid, rec):
    delete_alerts_for("concerns", rid)
    add_alert({"level":"PUBLIC REPORT","title":f"Public concern: {rec['Concern']}","place":f"{rec['Village']} · {rec['District']}","time":datetime.now().strftime("Today, %I:%M %p"),"detail":rec.get("Details") or "No extra details provided."}, src=f"concerns:{rid}")

def delete_alert(alert_id):
    c = _conn()
    try:
        c.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        c.commit()
    finally:
        c.close()

def get_actions():
    c = _conn()
    try:
        rows = c.execute("SELECT village, data FROM actions").fetchall()
    finally:
        c.close()
    return {v: json.loads(d) for v, d in rows}

def set_action(village, rec):
    c = _conn()
    try:
        c.execute("INSERT OR REPLACE INTO actions (village, data) VALUES (?, ?)", (village, json.dumps(rec, ensure_ascii=False)))
        c.commit()
    finally:
        c.close()

def reset_db():
    c = _conn()
    try:
        for t in ("reports", "water_tests", "concerns", "alerts", "actions"):
            c.execute(f"DELETE FROM {t}")
        _seed(c)
        c.commit()
    finally:
        c.close()

init_db()

st.set_page_config(page_title="JAL-rakshak", page_icon="💧", layout="wide", initial_sidebar_state="expanded")

# --- AI model (Random Forest). Loads the saved model, or retrains automatically if needed. ---
@st.cache_resource(show_spinner=False)
def get_model():
    try:
        return ml_model.load_or_train()
    except Exception:
        return None  # app still works with the simple rule-based fallback below

risk_model = get_model()

# --- Theme and session state ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f4f8f7; color: #173b3b; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#103f3d 0%,#0b292d 100%); }
[data-testid="stSidebar"] * { color: #effcf8 !important; }
.hero { background: linear-gradient(115deg,#0d4541,#167a70); padding: 25px 28px; border-radius: 20px; color: white; margin-bottom: 18px; box-shadow: 0 10px 30px #174e4215; }
.hero h1 { font-family: 'Manrope',sans-serif; font-size: 30px; line-height: 1.2; margin: 0 0 7px 0; color: white; }
.hero p { margin: 0; color: #d5f4ec; font-size: 14px; }
.kpi { background: white; border: 1px solid #e0ece8; border-radius: 16px; padding: 18px 19px; min-height: 125px; box-shadow: 0 5px 20px #163c3510; }
.kpi .label { color: #68817c; font-size: 13px; font-weight: 600; }
.kpi .value { font-size: 30px; font-weight: 800; color: #153f3c; margin-top: 7px; font-family: 'Manrope',sans-serif; }
.kpi .note { color: #278b71; font-size: 12px; margin-top: 4px; }
.section-title { font-family: 'Manrope',sans-serif; color: #173f3b; font-weight: 800; font-size: 20px; margin: 12px 0 4px 0; }
.muted { color: #6c8580; font-size: 13px; }
.pill { display:inline-block; padding:4px 9px; border-radius:99px; font-size:11px; font-weight:700; background:#e4f7ef; color:#16765e; }
.risk-card { background:white; border:1px solid #e0ece8; border-radius:14px; padding:14px 16px; margin-bottom:10px; }
.stButton>button { border-radius: 10px; font-weight: 700; transition: background-color .15s ease, color .15s ease, border-color .15s ease; }
/* Keep secondary actions such as “Mark reviewed” readable on the light page. */
div[data-testid="stButton"] button[kind="secondary"],
div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {
    background: #e8f5f0 !important;
    color: #15594d !important;
    border: 1px solid #b9d9ce !important;
}
div[data-testid="stButton"] button[kind="secondary"] p,
div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] p {
    color: #15594d !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover,
div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:hover {
    background: #d5eee5 !important;
    color: #0d4339 !important;
    border-color: #8fc7b5 !important;
}
div[data-testid="stButton"] button[kind="secondary"]:focus:not(:active),
div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:focus:not(:active) {
    box-shadow: 0 0 0 3px #b9e3d5 !important;
    color: #15594d !important;
}
/* Keep every Streamlit form label visible above its field */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stTextInput label,
.stSelectbox label,
.stNumberInput label,
.stTextArea label,
.stDateInput label,
.stMultiSelect label,
.stRadio label,
.stCheckbox label {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #16352f !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    line-height: 1.4 !important;
    margin-bottom: 7px !important;
}

/* Prevent field labels from being collapsed or hidden by inherited styles */
[data-testid="stWidgetLabel"] *,
[data-testid="stWidgetLabel"] p {
    color: #16352f !important;
    opacity: 1 !important;
}

/* Give form fields enough vertical space between label and input */
[data-testid="stTextInput"],
[data-testid="stSelectbox"],
[data-testid="stNumberInput"],
[data-testid="stTextArea"],
[data-testid="stDateInput"],
[data-testid="stMultiSelect"] {
    margin-top: 2px !important;
    margin-bottom: 12px !important;
}

/* Tabs, expanders and download buttons readable on the light page */
button[data-baseweb="tab"], button[data-baseweb="tab"] p { color: #16352f !important; font-weight: 700 !important; }
[data-testid="stExpander"] { background: #ffffff !important; border: 1px solid #e0ece8 !important; border-radius: 12px !important; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: #16352f !important; font-weight: 700 !important; }
div[data-testid="stDownloadButton"] button {
    background: #e8f5f0 !important; color: #15594d !important; border: 1px solid #b9d9ce !important;
}
div[data-testid="stDownloadButton"] button p { color: #15594d !important; }
div[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"],
div[data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
    background: #fbe7e5 !important; color: #8f2f29 !important; border: 1px solid #e3b3af !important;
}
div[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] p,
div[data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondaryFormSubmit"] p { color: #8f2f29 !important; }

/* Light input fields with dark text so typed text is always visible */
[data-baseweb="input"],
[data-baseweb="base-input"],
[data-baseweb="textarea"],
[data-baseweb="select"] > div,
[data-baseweb="datepicker"] [data-baseweb="input"] {
    background-color: #ffffff !important;
    border-color: #b9d9ce !important;
}
[data-baseweb="input"] input,
[data-baseweb="base-input"] input,
[data-baseweb="textarea"] textarea,
[data-baseweb="select"] input,
[data-baseweb="select"] div,
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input {
    color: #0f2a26 !important;
    -webkit-text-fill-color: #0f2a26 !important;
    background-color: #ffffff !important;
    caret-color: #0f2a26 !important;
}
[data-baseweb="input"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder {
    color: #7a918c !important;
    -webkit-text-fill-color: #7a918c !important;
}
[data-baseweb="select"] svg,
.stNumberInput button,
.stNumberInput button svg {
    color: #15594d !important;
    fill: #15594d !important;
}
.stNumberInput button { background-color: #e8f5f0 !important; }
/* Dropdown lists */
[data-baseweb="popover"] ul,
[data-baseweb="popover"] li,
[data-baseweb="popover"] [role="option"] {
    background-color: #ffffff !important;
    color: #0f2a26 !important;
}
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] [role="option"]:hover {
    background-color: #e8f5f0 !important;
}
/* Multiselect tags */
[data-baseweb="tag"] { background-color: #d5eee5 !important; }
[data-baseweb="tag"] span { color: #0f2a26 !important; -webkit-text-fill-color: #0f2a26 !important; }

/* Dark, readable text inside success / warning / info / error boxes */
[data-testid="stAlert"],
[data-testid="stAlert"] *,
[data-testid="stAlertContainer"],
[data-testid="stAlertContainer"] * {
    color: #0f2a26 !important;
    opacity: 1 !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlertContainer"] p {
    font-weight: 600 !important;
    font-size: 15px !important;
}
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = "District Health Officer"
ACTIONS = get_actions()

# --- Login screen ---
if not st.session_state.logged_in:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown("<div style='padding:40px 15px 20px 5px'><div style='font-size:15px;font-weight:800;letter-spacing:2px;color:#1b8a79'>💧 JAL-RAKSHAK</div><h1 style='font-family:Manrope,sans-serif;font-size:45px;line-height:1.12;color:#133f3b;margin-top:24px'>Healthier villages.<br>Safer water.<br><span style='color:#168978'>Earlier action.</span></h1><p style='font-size:17px;color:#66817a;max-width:490px'>A community health monitoring and water-borne disease early-warning platform for Northeast India.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='background:linear-gradient(135deg,#d9f0e8,#f0f9f5);border-radius:22px;padding:28px;margin-top:10px'><div style='font-size:42px'>🏞️　💧　🩺</div><h3 style='color:#174e45'>From village reports to timely response</h3><p style='color:#55766e'>Connect ASHA workers, water testing teams and district health officers in one simple workspace—even in low-bandwidth areas.</p><span class='pill'>LOW-BANDWIDTH READY</span>　<span class='pill'>MULTILINGUAL</span></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div style='background:white;border:1px solid #e0ece8;border-radius:22px;padding:28px 30px;margin-top:24px;box-shadow:0 15px 45px #174e4212'><h2 style='color:#173f3b;margin:0'>Welcome back</h2><p style='color:#78908a;margin-top:5px'>Choose your role to enter the demo workspace.</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            role = st.selectbox("Sign in as", ["District Health Officer", "ASHA Worker", "Public User"])
            lang = st.selectbox("Language / भाषा", ["English", "हिन्दी", "অসমীয়া", "বাংলা"])
            user = st.text_input("Username (demo)", placeholder="Enter any demo username")
            password = st.text_input("Password (demo)", type="password", placeholder="Demo only — authentication not enabled")
            submitted = st.form_submit_button("Enter dashboard  →", use_container_width=True, type="primary")
            if submitted:
                st.session_state.logged_in = True
                st.session_state.role = role
                st.session_state.language = lang
                st.rerun()
        st.caption("Prototype only: this role selector is not real authentication. Do not enter a real password.")
    st.stop()

# --- Sidebar navigation ---
with st.sidebar:
    st.markdown("<div style='padding:12px 5px 22px'><div style='font-size:13px;letter-spacing:2px;font-weight:800;color:#a6e7d6'>💧 EARLY WARNING</div><div style='font-size:21px;font-weight:800;margin-top:6px'>JAL-rakshak</div><div style='font-size:12px;color:#a4c6bf'>Community health intelligence</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#ffffff16;padding:11px;border-radius:12px;margin-bottom:16px'><div style='font-size:11px;color:#a8d9cf'>SIGNED IN AS</div><b>{st.session_state.role}</b></div>", unsafe_allow_html=True)
    NAV = {
        "District Health Officer": ["District Dashboard", "Water Quality Map", "Outbreak Response", "Field Reports", "Alert Centre", "Settings"],
        "ASHA Worker": ["Overview", "Water Quality Map", "Symptom Reporting", "Water Testing", "Alert Centre", "Settings"],
        "Public User": ["Public Home", "Water Safety Tips", "When to Seek Help", "Report a Concern", "Settings"],
    }
    page = st.radio("NAVIGATION", NAV.get(st.session_state.role, NAV["ASHA Worker"]), key=f"nav_{st.session_state.role}", label_visibility="visible")
    st.markdown("---")
    st.markdown("<div style='font-size:12px;color:#a4c6bf'>SYSTEM STATUS</div><div style='margin-top:8px'>🟢 Demo workspace active</div><div style='font-size:12px;color:#a4c6bf;margin-top:5px'>Sample data · not live surveillance</div>", unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# Header banner (text changes with the signed-in role)
HERO_SUB = {
    "District Health Officer": "Track risk across your district, coordinate response and review field reports.",
    "ASHA Worker": "Record symptom reports and water tests from your villages and see local alerts.",
    "Public User": "Check your village's water safety, learn simple precautions and report concerns.",
}
st.markdown(f"<div class='hero'><div style='font-size:12px;letter-spacing:1.6px;font-weight:700;color:#aee8dc'>COMMUNITY HEALTH MONITORING</div><h1>{'Good morning' if datetime.now().hour < 12 else 'Welcome back'}, {st.session_state.role}</h1><p>{HERO_SUB.get(st.session_state.role, '')}</p></div>", unsafe_allow_html=True)
if "_flash" in st.session_state:
    st.success(st.session_state.pop("_flash"))

# Data used for charts and maps (illustrative demo data)
trend = pd.DataFrame({"Day":["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],"Reports":[12,16,13,21,18,27,22],"Water tests":[7,9,8,12,10,15,13]})
villages = pd.DataFrame([
    # Illustrative monitoring locations across all eight Northeast states.
    # Names/coordinates are demo examples; readings and risk values are fictional.
    {"Village":"Barkola","District":"Sonitpur","State":"Assam","Risk":"High","Reports":8,"Turbidity (NTU)":5.8,"Chlorine (mg/L)":0.1,"Latitude":26.63,"Longitude":92.80},
    {"Village":"Rangajan","District":"Golaghat","State":"Assam","Risk":"Caution","Reports":4,"Turbidity (NTU)":3.2,"Chlorine (mg/L)":0.3,"Latitude":26.53,"Longitude":93.97},
    {"Village":"Borpathar","District":"Karbi Anglong","State":"Assam","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.1,"Chlorine (mg/L)":0.5,"Latitude":26.28,"Longitude":93.82},
    {"Village":"Ward 3","District":"Nagaon","State":"Assam","Risk":"Caution","Reports":3,"Turbidity (NTU)":4.7,"Chlorine (mg/L)":0.2,"Latitude":26.35,"Longitude":92.68},
    {"Village":"Lakhimi","District":"Dhemaji","State":"Assam","Risk":"Normal","Reports":0,"Turbidity (NTU)":1.4,"Chlorine (mg/L)":0.4,"Latitude":27.48,"Longitude":94.58},
    {"Village":"Kamalabari","District":"Majuli","State":"Assam","Risk":"Normal","Reports":2,"Turbidity (NTU)":1.8,"Chlorine (mg/L)":0.4,"Latitude":26.95,"Longitude":94.17},
    {"Village":"Chabua","District":"Dibrugarh","State":"Assam","Risk":"Caution","Reports":3,"Turbidity (NTU)":3.6,"Chlorine (mg/L)":0.2,"Latitude":27.48,"Longitude":95.17},
    {"Village":"Hajo","District":"Kamrup","State":"Assam","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.5,"Chlorine (mg/L)":0.5,"Latitude":26.25,"Longitude":91.53},
    {"Village":"Mawlynnong","District":"East Khasi Hills","State":"Meghalaya","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.2,"Chlorine (mg/L)":0.5,"Latitude":25.20,"Longitude":91.91},
    {"Village":"Nongpoh","District":"Ri-Bhoi","State":"Meghalaya","Risk":"Caution","Reports":3,"Turbidity (NTU)":3.4,"Chlorine (mg/L)":0.2,"Latitude":25.90,"Longitude":91.88},
    {"Village":"Tura","District":"West Garo Hills","State":"Meghalaya","Risk":"High","Reports":6,"Turbidity (NTU)":5.4,"Chlorine (mg/L)":0.1,"Latitude":25.51,"Longitude":90.22},
    {"Village":"Moirang","District":"Bishnupur","State":"Manipur","Risk":"Caution","Reports":4,"Turbidity (NTU)":3.8,"Chlorine (mg/L)":0.2,"Latitude":24.50,"Longitude":93.77},
    {"Village":"Kakching","District":"Kakching","State":"Manipur","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.6,"Chlorine (mg/L)":0.4,"Latitude":24.50,"Longitude":93.98},
    {"Village":"Nambol","District":"Bishnupur","State":"Manipur","Risk":"High","Reports":7,"Turbidity (NTU)":5.6,"Chlorine (mg/L)":0.1,"Latitude":24.72,"Longitude":93.83},
    {"Village":"Melaghar","District":"Sepahijala","State":"Tripura","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.3,"Chlorine (mg/L)":0.5,"Latitude":23.49,"Longitude":91.33},
    {"Village":"Udaipur","District":"Gomati","State":"Tripura","Risk":"Caution","Reports":3,"Turbidity (NTU)":3.7,"Chlorine (mg/L)":0.2,"Latitude":23.53,"Longitude":91.48},
    {"Village":"Kumarghat","District":"Unakoti","State":"Tripura","Risk":"Normal","Reports":0,"Turbidity (NTU)":1.4,"Chlorine (mg/L)":0.4,"Latitude":24.13,"Longitude":91.98},
    {"Village":"Ziro","District":"Lower Subansiri","State":"Arunachal Pradesh","Risk":"Caution","Reports":2,"Turbidity (NTU)":3.1,"Chlorine (mg/L)":0.3,"Latitude":27.54,"Longitude":93.83},
    {"Village":"Pasighat","District":"East Siang","State":"Arunachal Pradesh","Risk":"High","Reports":5,"Turbidity (NTU)":5.2,"Chlorine (mg/L)":0.1,"Latitude":28.07,"Longitude":95.33},
    {"Village":"Kigwema","District":"Kohima","State":"Nagaland","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.5,"Chlorine (mg/L)":0.5,"Latitude":25.60,"Longitude":94.11},
    {"Village":"Chumoukedima","District":"Chumoukedima","State":"Nagaland","Risk":"Caution","Reports":3,"Turbidity (NTU)":3.5,"Chlorine (mg/L)":0.2,"Latitude":25.86,"Longitude":93.72},
    {"Village":"Sairang","District":"Aizawl","State":"Mizoram","Risk":"Caution","Reports":2,"Turbidity (NTU)":3.3,"Chlorine (mg/L)":0.2,"Latitude":23.80,"Longitude":92.67},
    {"Village":"Lunglei","District":"Lunglei","State":"Mizoram","Risk":"Normal","Reports":1,"Turbidity (NTU)":1.4,"Chlorine (mg/L)":0.5,"Latitude":22.89,"Longitude":92.73},
    {"Village":"Yuksom","District":"Gyalshing","State":"Sikkim","Risk":"Normal","Reports":0,"Turbidity (NTU)":1.1,"Chlorine (mg/L)":0.5,"Latitude":27.37,"Longitude":88.22},
    {"Village":"Rangpo","District":"Pakyong","State":"Sikkim","Risk":"High","Reports":5,"Turbidity (NTU)":5.1,"Chlorine (mg/L)":0.1,"Latitude":27.18,"Longitude":88.53},
])

# Village risk is predicted by the ML model from turbidity, chlorine and report count (pH assumed 7.0 for the demo list).
if risk_model is not None:
    _preds = [ml_model.predict_risk(risk_model, r["Turbidity (NTU)"], r["Chlorine (mg/L)"], 7.0, int(r["Reports"])) for _, r in villages.iterrows()]
    villages["Risk %"] = [round(p * 100) for p, _ in _preds]
    villages["Risk"] = [label for _, label in _preds]
else:
    villages["Risk %"] = np.nan

# --- Water risk assessment (shared by the water test form and the edit form) ---
def assess_water(turbidity, chlorine, ph, cases):
    if risk_model is not None:
        prob, risk = ml_model.predict_risk(risk_model, turbidity, chlorine, ph, int(cases))
        return prob, risk, f"{risk} ({prob*100:.0f}% predicted risk)"
    risk = "Normal"  # fallback rules, used only if the AI model could not load
    if turbidity > 5 or chlorine < 0.2 or ph < 6.5 or ph > 8.5: risk = "High"
    elif turbidity > 3 or chlorine < 0.3: risk = "Caution"
    return None, risk, risk

# --- Edit / delete helpers ---
STATE_OPTS = sorted(villages["State"].unique().tolist())
DISTRICT_OPTS = sorted(villages["District"].unique().tolist()) + ["Other / not listed"]
SYMPTOM_OPTS = ["Diarrhoea", "Vomiting", "Fever", "Stomach pain", "Dehydration", "Other"]
AGE_OPTS = ["Under 5", "5–17", "18–59", "60+"]
URGENCY_OPTS = ["Routine", "Needs follow-up", "Urgent"]
SOURCE_OPTS = ["Handpump", "Community tap", "Well", "Piped supply", "River / stream", "Other"]
CONCERN_OPTS = ["Water looks dirty or smells bad", "Many people are sick", "Handpump, tap or pipe is broken", "Other"]

def _sel(label, options, current, key):
    options = list(options)
    current = current if current else options[0]
    if current not in options:
        options.append(current)
    return st.selectbox(label, options, index=options.index(current), key=key)

def _manage_header(title):
    st.markdown(f"<div class='section-title'>{title}</div><div class='muted'>Made a mistake? Pick the record, correct it and save, or delete it. Linked alerts are updated automatically.</div>", unsafe_allow_html=True)

def _pick(rows, label_fn, key, label):
    labels = {r["_id"]: label_fn(r) for r in rows}
    token = abs(hash(tuple(labels.keys())))
    rid = st.selectbox(label, list(labels.keys()), format_func=lambda i: labels[i], key=f"{key}_pick_{token}")
    return rid, next(r for r in rows if r["_id"] == rid)

def _form_buttons(key, rid):
    confirm = st.checkbox("I confirm I want to delete this record", key=f"{key}_{rid}_confirm")
    b1, b2 = st.columns(2)
    with b1:
        save = st.form_submit_button("Save changes", type="primary", use_container_width=True)
    with b2:
        delete = st.form_submit_button("Delete record", use_container_width=True)
    return save, delete, confirm

def manage_reports(only_ids=None):
    rows = db_all("reports", True)
    if only_ids is not None:
        rows = [r for r in rows if r["_id"] in only_ids]
    if not rows:
        return
    _manage_header("Edit or delete a symptom report")
    rid, r = _pick(rows, lambda x: f"#{x['_id']} · {x.get('Village','')} · {x.get('Date','')} · {x.get('Cases','')} case(s)", "rep", "Select a report")
    cur_sym = [x.strip() for x in str(r.get("Symptoms", "")).split(",") if x.strip() in SYMPTOM_OPTS]
    try: cur_date = date.fromisoformat(str(r.get("Date")))
    except Exception: cur_date = date.today()
    k = f"rep_{rid}"
    with st.form(f"rep_edit_{rid}"):
        c1, c2 = st.columns(2)
        with c1:
            e_reporter = st.text_input("ASHA Worker Name", value=r.get("Reporter", ""), key=f"{k}_reporter")
            e_state = _sel("State", STATE_OPTS, r.get("State"), f"{k}_state")
            e_district = _sel("District", DISTRICT_OPTS, r.get("District"), f"{k}_district")
            e_village = st.text_input("Village / Ward Name", value=r.get("Village", ""), key=f"{k}_village")
            e_date = st.date_input("Date Observed", value=cur_date, key=f"{k}_date")
        with c2:
            e_age = _sel("Age Group", AGE_OPTS, r.get("Age group"), f"{k}_age")
            e_sym = st.multiselect("Symptoms Seen or Reported", SYMPTOM_OPTS, default=cur_sym, key=f"{k}_sym")
            e_cases = st.number_input("Number of People Affected", min_value=1, max_value=500, value=max(1, min(500, int(r.get("Cases", 1)))), key=f"{k}_cases")
            e_urg = _sel("Urgency Level", URGENCY_OPTS, r.get("Urgency"), f"{k}_urg")
        e_notes = st.text_area("Additional Notes (no patient names)", value=r.get("Notes", ""), key=f"{k}_notes")
        save, delete, confirm = _form_buttons("rep", rid)
    if save:
        if not e_village.strip() or not e_sym:
            st.error("Please enter a village and select at least one symptom.")
        else:
            new = {"Reporter": e_reporter or "Demo ASHA", "State": e_state, "District": e_district, "Village": e_village, "Date": str(e_date), "Age group": e_age, "Symptoms": ", ".join(e_sym), "Cases": int(e_cases), "Urgency": e_urg, "Notes": e_notes}
            db_update("reports", rid, new)
            report_alerts(rid, new)
            flash(f"Report #{rid} updated.")
            st.rerun()
    if delete:
        if not confirm:
            st.warning("Tick the confirmation box first, then press Delete record.")
        else:
            db_delete("reports", rid)
            flash(f"Report #{rid} deleted.")
            st.rerun()

def manage_water_tests():
    rows = db_all("water_tests", True)
    if not rows:
        return
    _manage_header("Edit or delete a water test")
    rid, r = _pick(rows, lambda x: f"#{x['_id']} · {x.get('Village','')} · {x.get('Date','')} · {x.get('Risk','')}", "wt", "Select a water test")
    try: cur_date = date.fromisoformat(str(r.get("Date")))
    except Exception: cur_date = date.today()
    k = f"wt_{rid}"
    with st.form(f"wt_edit_{rid}"):
        c1, c2 = st.columns(2)
        with c1:
            e_tester = st.text_input("Field worker name", value=r.get("Tester", ""), key=f"{k}_tester")
            e_state = _sel("State", STATE_OPTS, r.get("State"), f"{k}_state")
            e_district = _sel("District", DISTRICT_OPTS, r.get("District"), f"{k}_district")
            e_village = st.text_input("Village / ward", value=r.get("Village", ""), key=f"{k}_village")
            e_source = _sel("Water source", SOURCE_OPTS, r.get("Source"), f"{k}_source")
        with c2:
            e_turb = st.number_input("Turbidity (NTU)", min_value=0.0, max_value=100.0, value=float(r.get("Turbidity (NTU)", 1.0)), step=0.1, key=f"{k}_turb")
            e_chl = st.number_input("Free residual chlorine (mg/L)", min_value=0.0, max_value=10.0, value=float(r.get("Chlorine (mg/L)", 0.5)), step=0.1, key=f"{k}_chl")
            e_ph = st.number_input("pH reading", min_value=0.0, max_value=14.0, value=float(r.get("pH", 7.0)), step=0.1, key=f"{k}_ph")
            e_cases = st.number_input("Symptom cases nearby (last 7 days)", min_value=0, max_value=500, value=max(0, min(500, int(r.get("Symptom cases (7d)", 0)))), step=1, key=f"{k}_cases")
            e_date = st.date_input("Test date", value=cur_date, key=f"{k}_date")
        e_remarks = st.text_area("Field observations", value=r.get("Remarks", ""), key=f"{k}_remarks")
        save, delete, confirm = _form_buttons("wt", rid)
    if save:
        if not e_village.strip():
            st.error("Please enter the village or ward.")
        else:
            prob, risk, risk_text = assess_water(e_turb, e_chl, e_ph, e_cases)
            new = {"Date": str(e_date), "State": e_state, "District": e_district, "Village": e_village, "Source": e_source, "Turbidity (NTU)": e_turb, "Chlorine (mg/L)": e_chl, "pH": e_ph, "Symptom cases (7d)": int(e_cases), "Risk": risk, "Risk %": None if prob is None else round(prob * 100), "Tester": e_tester or "Demo tester", "Remarks": e_remarks}
            db_update("water_tests", rid, new)
            water_alerts(rid, new, risk_text)
            flash(f"Water test #{rid} updated. New AI risk assessment: {risk_text}.")
            st.rerun()
    if delete:
        if not confirm:
            st.warning("Tick the confirmation box first, then press Delete record.")
        else:
            db_delete("water_tests", rid)
            flash(f"Water test #{rid} deleted.")
            st.rerun()

def manage_concerns(only_ids=None):
    rows = db_all("concerns", True)
    if only_ids is not None:
        rows = [r for r in rows if r["_id"] in only_ids]
    if not rows:
        return
    _manage_header("Edit or delete a public concern")
    rid, r = _pick(rows, lambda x: f"#{x['_id']} · {x.get('Village','')} · {x.get('Concern','')}", "con", "Select a concern")
    k = f"con_{rid}"
    with st.form(f"con_edit_{rid}"):
        c1, c2 = st.columns(2)
        with c1:
            e_state = _sel("State", STATE_OPTS, r.get("State"), f"{k}_state")
            e_district = _sel("District", DISTRICT_OPTS, r.get("District"), f"{k}_district")
            e_village = st.text_input("Village / ward", value=r.get("Village", ""), key=f"{k}_village")
        with c2:
            e_type = _sel("What is the concern?", CONCERN_OPTS, r.get("Concern"), f"{k}_type")
            e_details = st.text_area("Details (optional)", value=r.get("Details", ""), key=f"{k}_details")
        save, delete, confirm = _form_buttons("con", rid)
    if save:
        if not e_village.strip():
            st.error("Please enter the village or ward.")
        else:
            new = {"State": e_state, "District": e_district, "Village": e_village, "Concern": e_type, "Details": e_details}
            db_update("concerns", rid, new)
            concern_alerts(rid, new)
            flash(f"Concern #{rid} updated.")
            st.rerun()
    if delete:
        if not confirm:
            st.warning("Tick the confirmation box first, then press Delete record.")
        else:
            db_delete("concerns", rid)
            flash(f"Concern #{rid} deleted.")
            st.rerun()

if page == "Overview":
    k1,k2,k3,k4 = st.columns(4)
    cards = [("SYMPTOM REPORTS","128","↑ 12% vs last week"),("WATER SOURCES TESTED","46","8 tests need follow-up"),("ACTIVE ALERTS",str(len(get_alerts())),"Needs district review"),("VILLAGES MONITORED",str(len(villages)),"Across all 8 Northeast states")]
    for col,(label,value,note) in zip([k1,k2,k3,k4],cards):
        with col: st.markdown(f"<div class='kpi'><div class='label'>{label}</div><div class='value'>{value}</div><div class='note'>{note}</div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Health signals at a glance</div><div class='muted'>Illustrative sample data for prototype demonstration</div>",unsafe_allow_html=True)
    c1,c2 = st.columns([1.3,1])
    with c1:
        st.markdown("<div class='risk-card'><b>Weekly reporting activity</b></div>",unsafe_allow_html=True)
        st.line_chart(trend.set_index("Day"), height=270)
    with c2:
        st.markdown("<div class='risk-card'><b>Village risk overview</b><div class='muted'>Risk categories predicted by the AI model from sample readings</div></div>",unsafe_allow_html=True)
        risk_counts = villages["Risk"].value_counts().reindex(["High","Caution","Normal"],fill_value=0)
        st.bar_chart(risk_counts, height=230)
    st.markdown("<div class='section-title'>Priority follow-ups</div>",unsafe_allow_html=True)
    for a in get_alerts()[:3]:
        color = "#b94a43" if "HIGH" in a["level"] else "#b77a21"
        st.markdown(f"<div class='risk-card'><span style='color:{color};font-weight:800;font-size:11px'>{a['level']}</span><br><b>{a['title']}</b><div class='muted'>{a['place']} · {a['time']}</div><div style='margin-top:6px'>{a['detail']}</div></div>",unsafe_allow_html=True)

elif page == "Water Quality Map":
    st.markdown("<div class='section-title'>Northeast India · water quality & village risk map</div><div class='muted'>25 illustrative monitoring locations across all 8 states. Risk readings are fictional demo data, not live surveillance.</div>",unsafe_allow_html=True)
    state_options = ["All states"] + sorted(villages["State"].unique().tolist())
    f1, f2, f3 = st.columns(3)
    with f1:
        state_filter = st.selectbox("Filter by state", state_options)
    state_rows = villages if state_filter == "All states" else villages[villages["State"] == state_filter]
    district_options = ["All districts"] + sorted(state_rows["District"].unique().tolist())
    with f2:
        district_filter = st.selectbox("Filter by district", district_options)
    with f3:
        risk_filter = st.selectbox("Filter by risk", ["All risks", "High", "Caution", "Normal"])
    shown = state_rows.copy()
    if district_filter != "All districts":
        shown = shown[shown["District"] == district_filter]
    if risk_filter != "All risks":
        shown = shown[shown["Risk"] == risk_filter]

    colmap, coltable = st.columns([0.9, 1.3], gap="large")
    with colmap:
        st.markdown("<div class='risk-card'><b>Monitoring locations across Northeast India</b><div class='muted'>Map pins are approximate location points; select a state or district to narrow the list.</div></div>", unsafe_allow_html=True)
        if not shown.empty:
            map_points = shown.rename(columns={"Latitude":"latitude", "Longitude":"longitude"})[["latitude", "longitude", "Risk"]].copy()
            map_points["Point colour"] = map_points["Risk"].map({"High":"#d9534f", "Caution":"#e9a23b", "Normal":"#2d9d78"})
            st.map(map_points, latitude="latitude", longitude="longitude", color="Point colour", size=120)
        else:
            st.info("No locations match these filters.")
        st.markdown("🔴 High risk　 🟠 Caution　 🟢 Normal")
        st.caption("Map coordinates are approximate and intended for demonstration only.")
    with coltable:
        st.markdown(f"<div class='risk-card'><b>Village monitoring list</b><div class='muted'>Showing {len(shown)} of {len(villages)} locations</div></div>", unsafe_allow_html=True)
        display_cols = ["Village", "District", "State", "Risk", "Risk %", "Reports", "Turbidity (NTU)", "Chlorine (mg/L)"]
        st.dataframe(shown[display_cols], hide_index=True, use_container_width=True)
        if not shown.empty:
            chosen = st.selectbox("View village details", shown["Village"].tolist())
            v = shown[shown["Village"] == chosen].iloc[0]
            risk_pct = "" if pd.isna(v["Risk %"]) else f" ({int(v['Risk %'])}%)"
            st.info(f"{v['Village']} · {v['District']} district, {v['State']} · Risk: {v['Risk']}{risk_pct} · {int(v['Reports'])} symptom reports · Turbidity {v['Turbidity (NTU)']} NTU · Chlorine {v['Chlorine (mg/L)']} mg/L")


elif page == "Symptom Reporting":
    st.markdown("<div class='section-title'>Community symptom report</div><div class='muted'>For ASHA workers and authorized health staff. Use fictional data for this demo.</div>",unsafe_allow_html=True)
    with st.form("symptom_form",clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            reporter = st.text_input("1. ASHA Worker Name (Who is filling this form?)", placeholder="Enter your name", help="Write the name of the ASHA worker or health staff member entering this report.")
            state = st.selectbox("2. State (Which Northeast state?)", sorted(villages["State"].unique().tolist()), help="Choose the state where the village is located.")
            district = st.selectbox("3. District (Which district is the report from?)",sorted(villages["District"].unique().tolist()) + ["Other / not listed"], help="Choose the district where the village is located.")
            village = st.text_input("4. Village / Ward Name (Where was the person observed?)", placeholder="Enter village or ward name", help="Write the name of the village or ward. Do not enter a patient name.")
            report_date = st.date_input("5. Date Observed (When were symptoms noticed?)",value=date.today(), help="Select the date the symptoms were observed or reported.")
        with c2:
            age_group = st.selectbox("6. Age Group (How old is the person?)",["Under 5","5–17","18–59","60+"], help="Choose the age group of the person being reported. For multiple people, select the main/most affected group if known.")
            symptoms = st.multiselect("7. Symptoms Seen or Reported (Select all that apply)",["Diarrhoea","Vomiting","Fever","Stomach pain","Dehydration","Other"], help="Select only symptoms that were actually observed or reported.")
            cases = st.number_input("8. Number of People Affected (How many have similar symptoms?)",min_value=1,max_value=500,value=1, help="Enter the number of people with similar symptoms in this village or group.")
            severity = st.selectbox("9. Urgency Level (How quickly is follow-up needed?)",["Routine","Needs follow-up","Urgent"], help="Routine: normal reporting. Needs follow-up: health staff should check. Urgent: promptly contact the appropriate health officer and follow local protocol.")
        notes = st.text_area("10. Additional Notes (Any useful details—no patient names)", placeholder="Example: Several residents reported fever since yesterday.", help="Add brief relevant details. Do not include patient names, phone numbers, or other personal identifiers.")
        ok = st.form_submit_button("Submit symptom report",type="primary",use_container_width=True)
        if ok:
            if not village.strip() or not symptoms:
                st.error("Please enter a village and select at least one symptom.")
            else:
                rec={"Reporter":reporter or "Demo ASHA","State":state,"District":district,"Village":village,"Date":str(report_date),"Age group":age_group,"Symptoms":", ".join(symptoms),"Cases":int(cases),"Urgency":severity,"Notes":notes}
                rid = db_add("reports", rec)
                report_alerts(rid, rec)
                st.success("Report saved. The district officer can now see it.")
    if db_all("reports"):
        st.markdown("<div class='section-title'>Recent symptom reports</div>",unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(db_all("reports")),hide_index=True,use_container_width=True)
        manage_reports()

elif page == "Water Testing":
    st.markdown("<div class='section-title'>Water quality field test</div><div class='muted'>Enter sample readings to flag possible follow-up needs.</div>",unsafe_allow_html=True)
    with st.form("water_form",clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            tester=st.text_input("Field worker name")
            state=st.selectbox("State",sorted(villages["State"].unique().tolist()),key="waterstate")
            district=st.selectbox("District",sorted(villages["District"].unique().tolist()) + ["Other / not listed"],key="waterdistrict")
            village=st.text_input("Village / ward",key="watervillage")
            source=st.selectbox("Water source",["Handpump","Community tap","Well","Piped supply","River / stream","Other"])
        with c2:
            turbidity=st.number_input("Turbidity (NTU)",min_value=0.0,max_value=100.0,value=1.0,step=0.1)
            chlorine=st.number_input("Free residual chlorine (mg/L)",min_value=0.0,max_value=10.0,value=0.5,step=0.1)
            ph=st.number_input("pH reading",min_value=0.0,max_value=14.0,value=7.0,step=0.1)
            symptom_cases=st.number_input("Symptom cases nearby (last 7 days)",min_value=0,max_value=500,value=0,step=1,help="How many people near this water source had diarrhoea, vomiting or fever in the last 7 days. Use 0 if none.")
            testdate=st.date_input("Test date",value=date.today(),key="waterdate")
        remarks=st.text_area("Field observations")
        save=st.form_submit_button("Save water test",type="primary",use_container_width=True)
        if save:
            if not village.strip(): st.error("Please enter the village or ward.")
            else:
                prob, risk, risk_text = assess_water(turbidity, chlorine, ph, symptom_cases)
                rec={"Date":str(testdate),"State":state,"District":district,"Village":village,"Source":source,"Turbidity (NTU)":turbidity,"Chlorine (mg/L)":chlorine,"pH":ph,"Symptom cases (7d)":int(symptom_cases),"Risk":risk,"Risk %":None if prob is None else round(prob*100),"Tester":tester or "Demo tester","Remarks":remarks}
                wid = db_add("water_tests", rec)
                water_alerts(wid, rec, risk_text)
                st.success(f"Water test saved. AI risk assessment: {risk_text}.")
                if risk != "Normal": st.warning("This prediction comes from a model trained on synthetic data. It is not a laboratory result or official public-health determination. Follow local testing and reporting procedures.")
    if db_all("water_tests"):
        st.markdown("<div class='section-title'>Recent water tests</div>",unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(db_all("water_tests")),hide_index=True,use_container_width=True)
        manage_water_tests()

# =====================  DISTRICT HEALTH OFFICER PAGES  =====================
elif page == "District Dashboard":
    st.markdown("<div class='section-title'>District command dashboard</div><div class='muted'>Risk across monitored villages, response status and priority follow-ups. Sample data for demonstration.</div>",unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        dash_state = st.selectbox("State", ["All states"] + sorted(villages["State"].unique().tolist()))
    scope = villages if dash_state == "All states" else villages[villages["State"] == dash_state]
    with d2:
        dash_district = st.selectbox("District", ["All districts"] + sorted(scope["District"].unique().tolist()))
    if dash_district != "All districts":
        scope = scope[scope["District"] == dash_district]

    high_n = int((scope["Risk"] == "High").sum())
    caution_n = int((scope["Risk"] == "Caution").sum())
    done_n = sum(1 for vname in scope[scope["Risk"] == "High"]["Village"] if ACTIONS.get(vname, {}).get("status") == "Completed")
    kcols = st.columns(5)
    kcards = [
        ("VILLAGES IN VIEW", str(len(scope)), "Monitoring locations"),
        ("HIGH RISK", str(high_n), "Needs immediate response"),
        ("CAUTION", str(caution_n), "Retest / keep watching"),
        ("NEW FIELD SUBMISSIONS", str(len(db_all("reports")) + len(db_all("water_tests")) + len(db_all("concerns"))), "ASHA, field testers, public"),
        ("RESPONSE PENDING", str(high_n - done_n), "High-risk villages not completed"),
    ]
    for col, (label, value, note) in zip(kcols, kcards):
        with col: st.markdown(f"<div class='kpi'><div class='label'>{label}</div><div class='value'>{value}</div><div class='note'>{note}</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Latest field activity</div><div class='muted'>Newest submissions from ASHA workers, field testers and the public (all districts).</div>", unsafe_allow_html=True)
    feed = []
    for r in db_all("reports", True):
        feed.append((r.get("_ts", 0), "🩺 Symptom report", f"{r.get('Village','')} · {r.get('District','')} · {r.get('Cases','')} case(s) · {r.get('Urgency','')}", r.get("Submitted", "")))
    for r in db_all("water_tests", True):
        feed.append((r.get("_ts", 0), "💧 Water test", f"{r.get('Village','')} · {r.get('District','')} · {r.get('Risk','')} risk · turbidity {r.get('Turbidity (NTU)','')} NTU", r.get("Submitted", "")))
    for r in db_all("concerns", True):
        feed.append((r.get("_ts", 0), "📢 Public concern", f"{r.get('Village','')} · {r.get('District','')} · {r.get('Concern','')}", r.get("Submitted", "")))
    feed.sort(key=lambda x: x[0], reverse=True)
    if not feed:
        st.info("No new submissions yet. Reports from ASHA workers and the public will appear here.")
    for _ts, kind, text, when in feed[:6]:
        st.markdown(f"<div class='risk-card'><b>{kind}</b> <span class='muted'>· {html.escape(str(when))}</span><div style='margin-top:4px'>{html.escape(text)}</div></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("<div class='risk-card'><b>Risk by district</b><div class='muted'>Number of villages in each risk category</div></div>", unsafe_allow_html=True)
        by_district = pd.crosstab(scope["District"], scope["Risk"]).reindex(columns=["High", "Caution", "Normal"], fill_value=0)
        st.bar_chart(by_district, height=260)
    with c2:
        st.markdown("<div class='risk-card'><b>Weekly reporting activity</b><div class='muted'>Illustrative sample data</div></div>", unsafe_allow_html=True)
        st.line_chart(trend.set_index("Day"), height=260)

    st.markdown("<div class='section-title'>Priority villages</div><div class='muted'>High risk first, then caution. Highest predicted risk at the top.</div>", unsafe_allow_html=True)
    prio = scope[scope["Risk"].isin(["High", "Caution"])].copy()
    prio["_order"] = prio["Risk"].map({"High": 0, "Caution": 1})
    if prio["Risk %"].notna().any():
        prio = prio.sort_values(["_order", "Risk %"], ascending=[True, False])
    else:
        prio = prio.sort_values(["_order", "Reports"], ascending=[True, False])
    if prio.empty:
        st.success("No high-risk or caution villages in this view.")
    for _, r in prio.head(8).iterrows():
        status = ACTIONS.get(r["Village"], {}).get("status", "Not started")
        color = "#b94a43" if r["Risk"] == "High" else "#b77a21"
        pct = "" if pd.isna(r["Risk %"]) else f" · {int(r['Risk %'])}% predicted risk"
        st.markdown(f"<div class='risk-card'><span style='color:{color};font-weight:800;font-size:11px'>{r['Risk'].upper()}</span><br><b>{r['Village']}</b> <span class='muted'>· {r['District']}, {r['State']}</span><div class='muted'>{int(r['Reports'])} symptom reports · turbidity {r['Turbidity (NTU)']} NTU · chlorine {r['Chlorine (mg/L)']} mg/L{pct}</div><div style='margin-top:6px'>Response status: <b>{status}</b></div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>All villages in view</div>", unsafe_allow_html=True)
    table_cols = ["Village", "District", "State", "Risk", "Risk %", "Reports", "Turbidity (NTU)", "Chlorine (mg/L)"]
    st.dataframe(scope[table_cols], hide_index=True, use_container_width=True)
    st.download_button("Download this list (CSV)", scope[table_cols].to_csv(index=False).encode("utf-8"), file_name="jal_rakshak_district_risk.csv", mime="text/csv")

elif page == "Outbreak Response":
    st.markdown("<div class='section-title'>Outbreak response tracker</div><div class='muted'>Assign a response action to each at-risk village and track its status. Saved in the shared database.</div>",unsafe_allow_html=True)
    action_options = ["Dispatch medical / ORS team", "Retest and chlorinate water source", "Community awareness visit", "Escalate to state health office", "No action needed"]
    status_options = ["Not started", "In progress", "Completed"]
    show_mode = st.selectbox("Show villages", ["High risk only", "High risk and Caution"])
    targets = villages[villages["Risk"].isin(["High"] if show_mode == "High risk only" else ["High", "Caution"])].copy()
    targets["_order"] = targets["Risk"].map({"High": 0, "Caution": 1})
    targets = targets.sort_values(["_order", "State", "Village"])
    if targets.empty:
        st.success("No villages need a response right now.")
    for _, r in targets.iterrows():
        name = r["Village"]
        saved = ACTIONS.get(name, {})
        icon = "🔴" if r["Risk"] == "High" else "🟠"
        with st.expander(f"{icon} {name} · {r['District']}, {r['State']} · {saved.get('status', 'Not started')}"):
            pct = "" if pd.isna(r["Risk %"]) else f" · predicted risk {int(r['Risk %'])}%"
            st.markdown(f"<div class='muted'>{int(r['Reports'])} symptom reports · turbidity {r['Turbidity (NTU)']} NTU · chlorine {r['Chlorine (mg/L)']} mg/L{pct}</div>", unsafe_allow_html=True)
            a1, a2, a3 = st.columns([1.4, 1, 0.6])
            with a1:
                act = st.selectbox("Response action", action_options, index=action_options.index(saved.get("action", action_options[0])), key=f"act_{name}")
            with a2:
                stat = st.selectbox("Status", status_options, index=status_options.index(saved.get("status", "Not started")), key=f"stat_{name}")
            with a3:
                st.write("")
                st.write("")
                if st.button("Save", key=f"save_{name}"):
                    set_action(name, {"action": act, "status": stat, "updated": datetime.now().strftime("%d %b, %I:%M %p")})
                    st.rerun()
    if ACTIONS:
        st.markdown("<div class='section-title'>Response log</div>", unsafe_allow_html=True)
        log = [{"Village": k, "Action": v["action"], "Status": v["status"], "Updated": v["updated"]} for k, v in ACTIONS.items()]
        st.dataframe(pd.DataFrame(log), hide_index=True, use_container_width=True)

elif page == "Field Reports":
    st.markdown("<div class='section-title'>Field reports</div><div class='muted'>Everything entered by ASHA workers, field testers and the public. Data is saved in a shared database file.</div>",unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["Symptom reports", "Water tests", "Public concerns"])
    with tab1:
        if db_all("reports"):
            df_rep = pd.DataFrame(db_all("reports"))
            st.dataframe(df_rep, hide_index=True, use_container_width=True)
            st.download_button("Download symptom reports (CSV)", df_rep.to_csv(index=False).encode("utf-8"), file_name="symptom_reports.csv", mime="text/csv")
            manage_reports()
        else:
            st.info("No symptom reports yet. Sign in as an ASHA Worker and submit one from Symptom Reporting.")
    with tab2:
        if db_all("water_tests"):
            df_wt = pd.DataFrame(db_all("water_tests"))
            st.dataframe(df_wt, hide_index=True, use_container_width=True)
            st.download_button("Download water tests (CSV)", df_wt.to_csv(index=False).encode("utf-8"), file_name="water_tests.csv", mime="text/csv")
            manage_water_tests()
        else:
            st.info("No water tests yet. Sign in as an ASHA Worker and save one from Water Testing.")
    with tab3:
        if db_all("concerns"):
            st.dataframe(pd.DataFrame(db_all("concerns")), hide_index=True, use_container_width=True)
            manage_concerns()
        else:
            st.info("No public concerns yet. Sign in as a Public User and submit one from Report a Concern.")

# =====================  PUBLIC USER PAGES  =====================
elif page == "Public Home":
    st.markdown("<div class='section-title'>Is my village's water safe?</div><div class='muted'>Choose your location to see a simple water safety status. Demonstration data only.</div>",unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    with p1:
        pub_state = st.selectbox("Your state", sorted(villages["State"].unique().tolist()))
    pub_rows = villages[villages["State"] == pub_state]
    with p2:
        pub_district = st.selectbox("Your district", sorted(pub_rows["District"].unique().tolist()))
    pub_rows = pub_rows[pub_rows["District"] == pub_district]
    with p3:
        pub_village = st.selectbox("Your village / ward", pub_rows["Village"].tolist())
    pv = pub_rows[pub_rows["Village"] == pub_village].iloc[0]
    status_info = {
        "Normal": ("#1f7a5c", "#e4f7ef", "🟢 Water looks OK", "Readings in the sample data are within the expected range. Keep drinking water in a clean, covered container and wash hands with soap before eating."),
        "Caution": ("#9a6410", "#fdf3df", "🟠 Use with care", "Boil drinking water (a rolling boil for at least 1 minute) or treat it with chlorine tablets until it is retested. Tell your ASHA worker if anyone has diarrhoea or vomiting."),
        "High": ("#a83a33", "#fbe7e5", "🔴 Treat water before drinking", "Do not drink untreated water from this area. Boil it (a rolling boil for at least 1 minute) or treat it with chlorine tablets from your health centre. If anyone has diarrhoea, vomiting or fever, contact your ASHA worker or the nearest health centre."),
    }
    fg, bg, headline, advice = status_info[pv["Risk"]]
    st.markdown(f"<div style='background:{bg};border:1px solid {fg}55;border-radius:18px;padding:22px 24px;margin-top:6px'><div class='muted'>{pv['Village']} · {pv['District']}, {pv['State']}</div><div style='font-family:Manrope,sans-serif;font-size:28px;font-weight:800;color:{fg};margin:6px 0'>{headline}</div><div style='color:#173b3b;font-size:15px;line-height:1.5'>{advice}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='risk-card' style='margin-top:12px'><b>Latest sample reading</b><div class='muted'>Turbidity (cloudiness): {pv['Turbidity (NTU)']} NTU · Free chlorine: {pv['Chlorine (mg/L)']} mg/L</div></div>", unsafe_allow_html=True)
    st.caption("Demonstration data, not an official water-quality notice. Always follow guidance from your local health department.")

elif page == "Water Safety Tips":
    st.markdown("<div class='section-title'>Keep your water and family safe</div><div class='muted'>Simple steps that help prevent water-borne illness.</div>",unsafe_allow_html=True)
    tips = [
        ("💧 Boil drinking water", "Bring water to a rolling boil for at least 1 minute, then let it cool in a clean, covered container."),
        ("🧪 Use chlorine tablets", "Ask your ASHA worker or health centre for chlorine tablets and follow the instructions on the packet."),
        ("🫙 Store water safely", "Use a clean container with a lid. Take water out with a clean ladle or tap, not with your hands."),
        ("🧼 Wash hands with soap", "Wash before cooking, eating or feeding children, and after using the toilet."),
        ("🚰 Protect the source", "Keep handpumps, wells and taps clean and away from toilets, drains and animal waste."),
        ("🌧️ After floods or heavy rain", "Treat all drinking water as unsafe until it is boiled, treated or tested."),
        ("🥤 For loose stools", "Give oral rehydration solution (ORS) made as directed on the packet, in clean water. Keep feeding children and keep drinking fluids."),
    ]
    for t_title, t_body in tips:
        st.markdown(f"<div class='risk-card'><b>{t_title}</b><div style='margin-top:5px;color:#173b3b'>{t_body}</div></div>", unsafe_allow_html=True)

elif page == "When to Seek Help":
    st.markdown("<div class='section-title'>When to get medical help</div><div class='muted'>General guidance only. This is not a diagnosis. If you are worried, go to a health worker or doctor.</div>",unsafe_allow_html=True)
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("<div class='risk-card'><b style='color:#9a6410'>Go to the nearest health centre soon if</b><ul style='margin:8px 0 0 18px;color:#173b3b;line-height:1.7'><li>Diarrhoea or vomiting lasts more than a day</li><li>There is blood in the stool</li><li>There is a high fever</li><li>The person is very thirsty or passing little urine</li><li>It affects a baby, young child, pregnant woman or older person</li><li>Several people in your home or village are ill</li></ul></div>", unsafe_allow_html=True)
    with h2:
        st.markdown("<div class='risk-card'><b style='color:#a83a33'>Get emergency help immediately if</b><ul style='margin:8px 0 0 18px;color:#173b3b;line-height:1.7'><li>The person is very sleepy, hard to wake or confused</li><li>They cannot drink or keep any fluids down</li><li>Eyes look sunken, mouth is very dry, or no urine for many hours</li><li>There are fits (seizures) or the person collapses</li></ul><div style='margin-top:10px;color:#173b3b'>Call <b>112</b> (emergency) or <b>108</b> (ambulance in most states). Check the numbers used in your area.</div></div>", unsafe_allow_html=True)
    st.caption("While arranging help, give ORS or clean boiled water in small, frequent sips if the person can drink.")

elif page == "Report a Concern":
    st.markdown("<div class='section-title'>Report a water or health concern</div><div class='muted'>Your report goes to the district team for review. Do not include names or phone numbers.</div>",unsafe_allow_html=True)
    with st.form("concern_form", clear_on_submit=True):
        r1, r2 = st.columns(2)
        with r1:
            c_state = st.selectbox("State", sorted(villages["State"].unique().tolist()))
            c_district = st.selectbox("District", sorted(villages["District"].unique().tolist()) + ["Other / not listed"])
            c_village = st.text_input("Village / ward", placeholder="Enter village or ward name")
        with r2:
            c_type = st.selectbox("What is the concern?", ["Water looks dirty or smells bad", "Many people are sick", "Handpump, tap or pipe is broken", "Other"])
            c_details = st.text_area("Details (optional)", placeholder="Example: Water from the village handpump has been brown since yesterday.")
        c_submit = st.form_submit_button("Submit concern", type="primary", use_container_width=True)
        if c_submit:
            if not c_village.strip():
                st.error("Please enter your village or ward.")
            else:
                crec = {"State": c_state, "District": c_district, "Village": c_village, "Concern": c_type, "Details": c_details}
                cid = db_add("concerns", crec)
                st.session_state.setdefault("my_concerns", []).append(cid)
                concern_alerts(cid, crec)
                st.success("Thank you. Your concern was sent to the district team for review.")
    if st.session_state.get("my_concerns"):
        st.caption("You can edit or delete concerns you submitted from this browser session.")
        manage_concerns(only_ids=st.session_state["my_concerns"])
    st.caption("This is not an emergency service. If someone is seriously ill, go to the nearest health centre or call 112.")

elif page == "Alert Centre":
    st.markdown("<div class='section-title'>Alert centre</div><div class='muted'>Review risk signals and simulate an escalation for the demo.</div>",unsafe_allow_html=True)
    if st.button("＋ Simulate district-wide alert",type="primary"):
        add_alert({"level":"DISTRICT NOTICE","title":"Demo alert: verify village reports and water sources","place":"Selected monitoring area · Assam","time":datetime.now().strftime("Today, %I:%M %p"),"detail":"Simulated notice only. No SMS, WhatsApp or IVR message was sent."})
        st.rerun()
    st.caption("SMS / WhatsApp / IVR integrations are not connected. Alerts are stored in the shared database.")
    _alerts = get_alerts()
    if not _alerts: st.success("No active alerts.")
    for idx,a in enumerate(_alerts):
        color="#b94a43" if "HIGH" in a["level"] else ("#b77a21" if "CAUTION" in a["level"] else "#227e69")
        st.markdown(f"<div class='risk-card'><span style='font-size:11px;font-weight:800;color:{color}'>{a['level']}</span><h4 style='margin:6px 0;color:#183f3b'>{a['title']}</h4><div class='muted'>{a['place']} · {a['time']}</div><p style='margin:8px 0 0'>{a['detail']}</p></div>",unsafe_allow_html=True)
        if st.button("Mark reviewed",key=f"review_{a['_id']}"):
            delete_alert(a["_id"])
            st.rerun()

elif page == "Settings":
    st.markdown("<div class='section-title'>Workspace settings</div><div class='muted'>Prototype preferences and implementation status.</div>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        st.markdown("<div class='risk-card'><b>Language</b><p class='muted'>Choose the preferred interface language.</p></div>",unsafe_allow_html=True)
        st.selectbox("Interface language",["English","हिन्दी","অসমীয়া","বাংলা"])
        st.toggle("Low-bandwidth mode",value=True)
        st.toggle("Dark mode (preview setting)",value=False)
    with c2:
        st.markdown("<div class='risk-card'><b>Prototype status</b><p class='muted'>What is and is not connected</p></div>",unsafe_allow_html=True)
        st.write("✅ Python + Streamlit interface")
        st.write("✅ Random Forest risk model (trained on synthetic data)")
        st.write("✅ Shared SQLite database (data persists across sessions)")
        st.write("⚠️ Demo data; no real patient records")
        st.write("⚠️ Login is role selection only")
        st.write("⚠️ SMS/WhatsApp/IVR not connected")
    st.markdown("<div class='section-title'>Demo data</div><div class='muted'>Clear all saved reports, tests, concerns, alerts and response actions, and start fresh.</div>", unsafe_allow_html=True)
    if st.button("Reset demo data"):
        reset_db()
        st.rerun()

st.markdown("<div style='border-top:1px solid #dce9e5;margin-top:35px;padding-top:14px;color:#78908a;font-size:11px'>JAL-RAKSHAK · Prototype for demonstration only · Use fictional data · Not a diagnostic or emergency-response system</div>",unsafe_allow_html=True)