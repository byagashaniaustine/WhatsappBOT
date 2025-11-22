import os
import uuid
import logging
import requests
from typing import Dict, Any, Optional

# -----------------------------------
# LOGGER SETUP
# -----------------------------------
logger = logging.getLogger("meta_service")
logger.setLevel(logging.INFO)

# -----------------------------------
# ENVIRONMENT VARIABLES
# -----------------------------------
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"
MEDIA_API_BASE_URL = "https://graph.facebook.com/v24.0/"

# ==============================================================
# SEND SIMPLE WHATSAPP TEXT MESSAGE
# ==============================================================
def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID missing.")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"✅ Message sent to {to}. Response: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else str(e)
        logger.error(f"❌ WhatsApp API Error to {to} (Status {status_code}): {error_text}")
        raise RuntimeError(f"Meta API call failed: {e}")

# ==============================================================
# SEND WHATSAPP FLOW
# ==============================================================
def send_meta_whatsapp_flow(
    to: str,
    flow_id: str,
    flow_cta: str,
    flow_body_text: str = "",
    flow_header_text: str = "Huduma ya Mikopo",
    flow_footer_text: str = "Taarifa yako ni siri.",
    flow_action_payload: Optional[Dict[str, Any]] = None,
    flow_mode: str = "draft"  # 'draft' for testing, 'published' for production
) -> Dict[str, Any]:
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID missing.")

    flow_token = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    if flow_mode == "draft":
        headers["X-Meta-Flow-Draft"] = "true"

    # Draft mode does not support flow_action or flow_action_payload
    parameters = {
        "flow_message_version": "3",
        "flow_id": flow_id,
        "flow_token": flow_token,
        "flow_cta": flow_cta,
    }
    if flow_mode != "draft" and flow_action_payload:
        parameters["flow_action"] = "navigate"
        parameters["flow_action_payload"] = flow_action_payload

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {"type": "text", "text": flow_header_text},
            "body": {"text": flow_body_text},
            "footer": {"text": flow_footer_text},
            "action": {
                "name": "flow",
                "parameters": parameters
            }
        }
    }

    try:
        logger.info(f"🚀 Sending Flow '{flow_id}' to {to} (Mode: {flow_mode}, Token: {flow_token})")
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"✅ Flow sent successfully to {to}. Response: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else str(e)
        logger.error(f"❌ WhatsApp Flow API Error for {to} (Status {status_code}): {error_text}")
        raise RuntimeError(f"Meta Flow API call failed: {e}")

# ==============================================================
# SEND WHATSAPP TEMPLATE MESSAGE
# ==============================================================
def send_meta_whatsapp_template(
    to: str,
    template_name: str,
    language_code: str = "en_US",
    components: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a pre-approved WhatsApp template message via Meta API.

    Args:
        to (str): Recipient phone number in international format.
        template_name (str): Name of the WhatsApp template configured in Meta Business.
        language_code (str, optional): Language code for the template. Default is 'en_US'.
        components (dict, optional): Optional template components (header, body, buttons).

    Returns:
        dict: Response from Meta API.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID missing.")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        }
    }

    if components:
        payload["template"]["components"] = components

    try:
        logger.info(f"🚀 Sending Template '{template_name}' to {to}")
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"✅ Template sent successfully to {to}. Response: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else str(e)
        logger.error(f"❌ WhatsApp Template API Error for {to} (Status {status_code}): {error_text}")
        raise RuntimeError(f"Meta Template API call failed: {e}")

# ==============================================================
# GET MEDIA DOWNLOAD URL
# ==============================================================
def get_media_url(media_id: str) -> str:
    if not ACCESS_TOKEN:
        raise EnvironmentError("META_ACCESS_TOKEN missing for media lookup.")

    url = f"{MEDIA_API_BASE_URL}{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    try:
        logger.info(f"📥 Fetching media URL for ID {media_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        download_url = data.get("url")
        if not download_url:
            raise RuntimeError(f"No URL returned for media_id {media_id}. Response: {data}")
        logger.info(f"✅ Media URL retrieved for ID {media_id}")
        return download_url
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else str(e)
        logger.error(f"❌ Media URL lookup failed for {media_id} (Status {status_code}): {error_text}")
        raise RuntimeError(f"Media URL lookup failed: {e}")
