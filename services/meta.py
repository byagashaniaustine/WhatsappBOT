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
        logger.error(f"❌ Error sending message to {to}: {e}")
        raise RuntimeError(f"Meta API call failed: {e}")

# ==============================================================
# SEND WHATSAPP TEMPLATE MESSAGE
# ==============================================================
def send_meta_whatsapp_template(
    to: str,
    template_name: str,
    language_code: str = "en_US",
    components: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

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
        logger.info(f"✅ Template sent successfully: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Template send error for {to}: {e}")
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

        logger.info("✅ Media URL retrieved successfully")
        return download_url
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Media URL lookup failed: {e}")
        raise RuntimeError(f"Media URL lookup failed: {e}")
