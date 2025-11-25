import os
import uuid
import logging
import requests
from typing import Dict, Any, Optional, List

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

# WhatsApp Cloud API version (Consistent with recent Meta API logs)
API_VERSION = "v21.0" 

API_URL = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
MEDIA_API_BASE_URL = f"https://graph.facebook.com/{API_VERSION}/"

# TEMPORARY DEBUGGING LINE - CHECK THIS OUTPUT IN RAILWAY LOGS!
logger.info(f"*** DEBUG: Using PHONE_NUMBER_ID: {PHONE_NUMBER_ID} for API_URL: {API_URL}")

# ==============================================================
# SEND SIMPLE WHATSAPP TEXT MESSAGE
# ==============================================================
def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
    # NOTE: wa_id is included for compatibility with caller but not used here.
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
# SEND WHATSAPP TEMPLATE MESSAGE WITH FLOW BUTTON
# ==============================================================
def send_meta_whatsapp_template(
    to: str,
    template_name: str,
    language_code: str = "en",
    components: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Send a WhatsApp template message.
    
    Args:
        to: Recipient phone number (with country code, no + sign)
        template_name: Name of the approved template
        language_code: Language code (default: "en")
        components: Optional list of component objects for dynamic content
    
    Returns:
        API response as dictionary
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        raise EnvironmentError("META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID missing.")

    # Normalize phone number - remove + if present
    to = to.replace("+", "")

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
            "language": {"code": language_code}
        }
    }

    # Add components if provided
    if components:
        payload["template"]["components"] = components

    try:
        logger.info(f"🚀 Sending Template '{template_name}' to {to}")
        logger.info(f"📦 Payload: {payload}")
        
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        logger.info(f"✅ Template sent successfully: {response.json()}")
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP Error sending template to {to}: {e}")
        logger.error(f"Response: {e.response.text if e.response else 'No response'}")
        raise RuntimeError(f"Meta Template API HTTP error: {e}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Template send error for {to}: {e}")
        raise RuntimeError(f"Meta Template API call failed: {e}")

# ==============================================================
# SEND MANKA MENU TEMPLATE (CONVENIENCE FUNCTION)
# ==============================================================
def send_manka_menu_template(to: str) -> Dict[str, Any]:
    """
    Send the manka_menu template with flow button.
    This is a convenience function for the main menu template.
    
    Args:
        to: Recipient phone number
    
    Returns:
        API response as dictionary
    """
    return send_meta_whatsapp_template(
        to=to,
        template_name="manka_menu",
        language_code="en"
        # No components needed - the template has default flow button
    )

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