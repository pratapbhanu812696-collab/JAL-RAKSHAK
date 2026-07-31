"""
JAL-RAKSHAK: SMS / WhatsApp Alert Module
Sends outbreak risk alerts to health workers using Twilio.

Setup:
1. Create a free Twilio account: https://www.twilio.com/try-twilio
2. Get your Account SID, Auth Token, and a Twilio phone number
   (for WhatsApp: use Twilio's WhatsApp Sandbox number)
3. Set these as environment variables (see README for Render/Streamlit Cloud setup):
   TWILIO_ACCOUNT_SID
   TWILIO_AUTH_TOKEN
   TWILIO_FROM_NUMBER      (e.g. "+14155238886" for WhatsApp sandbox, or your SMS number)

This module fails gracefully if Twilio isn't configured — the dashboard
keeps working, it just skips sending alerts.
"""

import os

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


def is_configured():
    """Check if Twilio credentials are present."""
    return TWILIO_AVAILABLE and all([
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN"),
        os.environ.get("TWILIO_FROM_NUMBER"),
    ])


def _get_client():
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    return Client(sid, token)


def send_sms_alert(to_number, village, state, risk_pct):
    """
    Send a plain SMS alert. to_number must be in E.164 format, e.g. +919876543210
    Returns (success: bool, message: str)
    """
    if not is_configured():
        return False, "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER."

    body = (
        f"JAL-RAKSHAK ALERT\n"
        f"Village: {village}, {state}\n"
        f"Outbreak risk: {risk_pct}%\n"
        f"Action: Test water source, alert ASHA worker, advise boiling water."
    )
    try:
        client = _get_client()
        from_number = os.environ.get("TWILIO_FROM_NUMBER")
        msg = client.messages.create(body=body, from_=from_number, to=to_number)
        return True, f"SMS sent (SID: {msg.sid})"
    except Exception as e:
        return False, f"Failed to send SMS: {e}"


def send_whatsapp_alert(to_number, village, state, risk_pct):
    """
    Send a WhatsApp alert via Twilio's WhatsApp API.
    to_number must be in E.164 format, e.g. +919876543210 (WITHOUT the "whatsapp:" prefix — added here)
    Returns (success: bool, message: str)
    """
    if not is_configured():
        return False, "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER."

    body = (
        f"*JAL-RAKSHAK ALERT*\n"
        f"Village: {village}, {state}\n"
        f"Outbreak risk: {risk_pct}%\n"
        f"Action: Test water source, alert ASHA worker, advise boiling water."
    )
    try:
        client = _get_client()
        from_number = "whatsapp:" + os.environ.get("TWILIO_FROM_NUMBER").replace("whatsapp:", "")
        to_whatsapp = "whatsapp:" + to_number.replace("whatsapp:", "")
        msg = client.messages.create(body=body, from_=from_number, to=to_whatsapp)
        return True, f"WhatsApp sent (SID: {msg.sid})"
    except Exception as e:
        return False, f"Failed to send WhatsApp message: {e}"


def send_bulk_alerts(high_risk_villages, contacts, channel="sms"):
    """
    high_risk_villages: list of dicts with keys: village, state, risk
    contacts: list of phone numbers (E.164 format) to notify
    channel: "sms" or "whatsapp"
    Returns a list of result dicts for display in the dashboard.
    """
    results = []
    send_fn = send_whatsapp_alert if channel == "whatsapp" else send_sms_alert
    for v in high_risk_villages:
        for contact in contacts:
            success, message = send_fn(contact, v["village"], v["state"], v["risk"])
            results.append({
                "village": v["village"],
                "to": contact,
                "success": success,
                "message": message,
            })
    return results
