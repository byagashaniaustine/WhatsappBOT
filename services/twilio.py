import os
import json
from twilio.rest import Client

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# 🔒 Hardcoded Flow SIDs (replace with your real Twilio Flow Template SIDs)
FLOW_TEMPLATES = {
    "open_flow_upload_documents": "HX705e35a409323bab371b5d371771ae33",  # Upload Documents Flow SID
    "open_flow_loan_calculator": "HXyyyyyyyyyyyyyyyyyyyyyyyyyyyy",        # Loan Calculator Flow SID
}

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to: str, body: str):
    """
    Send a normal WhatsApp text message.
    """
    client.messages.create(
        from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
        body=body,
        to=f"{to}"   # ✅ No whatsapp: prefix here
    )


def trigger_twilio_flow(user_phone: str, flow_type: str, user_name: str, user_id: str):
    """
    Trigger a WhatsApp Flow Template using Content SID.
    Parameters use fixed key names for all users, but are filled dynamically from backend.
    """
    try:
        # Get flow SID based on flow_type
        flow_sid = FLOW_TEMPLATES.get(flow_type)
        if not flow_sid:
            raise ValueError(f"No Flow Template found for type '{flow_type}'")

        # Fixed parameter key names (values filled dynamically)
        content_vars = {
            "user_id": user_id or "",
            "user_name": user_name or "",
            "user_phone": user_phone,
            "flow_type": flow_type
        }

        # Send interactive flow message
        client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=f"{user_phone}",   # ✅ No whatsapp: prefix
            content_sid=flow_sid,
            content_variables=json.dumps(content_vars)
        )

        return {
            "status": "success",
            "message": f"Triggered WhatsApp Flow '{flow_type}' for {user_phone}"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
