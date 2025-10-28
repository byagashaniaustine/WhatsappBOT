import requests
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"
MEDIA_API_BASE_URL = "https://graph.facebook.com/v24.0/"

def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID is missing.")
    
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
        logger.info(f"✅ Message sent to {to}: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ WhatsApp API Error for {to}: {e}")
        raise RuntimeError(f"Meta API call failed: {e}")



def send_meta_whatsapp_flow(to: str, flow_id: str) -> Dict[str, Any]:
    """
    Send a WhatsApp Flow (interactive) message via Meta API.
    `flow_id` must be the Flow ID from your Meta Flow Builder.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID is missing.")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "flow": {
                "name": flow_id,
                "language": {
                    "policy": "deterministic",
                    "code": "sw"  # Swahili
                }
            }
        }
    }

    try:
        logger.info(f"Attempting to send Flow ID {flow_id} to {to}")
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"✅ Flow sent successfully to {to}: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ WhatsApp Flow API Error for {to}: {e}")
        raise RuntimeError(f"Meta Flow API call failed: {e}")

def get_media_url(media_id: str) -> str:
    if not ACCESS_TOKEN:
        raise EnvironmentError("META_ACCESS_TOKEN is missing for media lookup.")
    
    url = f"{MEDIA_API_BASE_URL}{media_id}"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        download_url = data.get("url")
        if not download_url:
            raise RuntimeError(f"No 'url' found in media response: {data}")
        logger.info(f"✅ Media URL retrieved for ID {media_id}")
        return download_url
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Media URL lookup failed for {media_id}: {e}")
        raise RuntimeError(f"Media URL lookup failed: {e}")
