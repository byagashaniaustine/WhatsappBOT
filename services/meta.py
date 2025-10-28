import requests
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"

def send_meta_whatsapp_flow(
    to: str,
    flow_id: str,
    flow_cta: str,
    initial_screen: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Sends a WhatsApp Flow message using the official Meta API.
    `flow_token` is generated for each user session.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID missing.")

    # 1️⃣ Generate flow token for this user
    token_url = f"https://graph.facebook.com/v24.0/{flow_id}/generate_token"
    try:
        token_resp = requests.post(
            token_url,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"user_phone": to}
        )
        token_resp.raise_for_status()
        flow_token = token_resp.json().get("flow_token")
        if not flow_token:
            raise RuntimeError("Failed to get flow_token from Meta API.")
        logger.info(f"✅ Generated flow_token for {to}")
    except Exception as e:
        logger.error(f"❌ Failed to generate flow_token: {e}")
        raise RuntimeError(f"Flow token generation failed: {e}")

    # 2️⃣ Prepare Flow message payload
    payload = {
        "recipient_type": "individual",
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {"type": "text", "text": "Flow Header"},
            "body": {"text": "Please fill in the form below"},
            "footer": {"text": "All info is private"},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": flow_token,
                    "flow_id": flow_id,
                    "flow_cta": flow_cta,
                    "flow_action": "navigate",
                    "flow_action_payload": {
                        "screen": initial_screen,
                        "data": data or {}
                    }
                }
            }
        }
    }

    # 3️⃣ Send Flow message
    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json=payload
        )
        response.raise_for_status()
        logger.info(f"✅ Flow sent successfully to {to}. Response: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"❌ WhatsApp Flow API Error for {to}: {e}")
        raise RuntimeError(f"Meta Flow API call failed: {e}")
