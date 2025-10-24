import requests
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# --- Configuration ---
# NOTE: These are retrieved from environment variables. Ensure they are set correctly.
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
# --- End Configuration ---

def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
    """
    Sends a standard text message via the Meta WhatsApp Cloud API.
    
    Args:
        to (str): The recipient's phone number in E.164 format (e.g., +255712345678).
        body (str): The text message content.
        
    Returns:
        Dict[str, Any]: The JSON response from the Meta API.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        error_msg = "Security Error: META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID is missing."
        logger.error(f"❌ {error_msg}")
        raise EnvironmentError(error_msg)

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
        
        # ⚠️ CRITICAL FIX: This raises an HTTPError for 4xx/5xx status codes
        response.raise_for_status() 

        # Log success
        logger.info(f"✅ Message sent successfully to {to}. Response: {response.json()}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # Log and raise the failure, which is now visible
        # Fix Pylance error by explicitly typing the dictionary to allow value assignment
        error_details: Dict[str, Any] = {"status_code": None, "error_data": None}
        
        if e.response is not None:
            error_details["status_code"] = e.response.status_code
            try:
                # Attempt to get the detailed error message from the Meta response body
                error_data = e.response.json()
                error_details["error_data"] = error_data
                logger.error(f"❌ WhatsApp API Error: Failed to send message to {to} (Status {e.response.status_code}). Details: {error_data}")
            except requests.exceptions.JSONDecodeError:
                # Handle non-JSON error responses
                error_details["error_data"] = e.response.text
                logger.error(f"❌ WhatsApp API Error: Failed to send message to {to} (Status {e.response.status_code}). Response Text: {e.response.text}")
        else:
            # Handle connectivity or other request errors
            logger.error(f"❌ Connection Error: Failed to send message to {to}. Exception: {e}")

        # Re-raise the exception to be caught by the main menu handler
        raise RuntimeError(f"Meta API call failed: {e}")
