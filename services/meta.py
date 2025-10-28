
import requests
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
MEDIA_API_BASE_URL = "https://graph.facebook.com/v24.0/"

def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        error_msg = "Security Error: META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID is missing."
        logger.error(f"❌ {error_msg}")
        # Note: We raise an EnvironmentError here, which is better than RuntimeError for config issues
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
        
        # ⚠️ CRITICAL: This raises an HTTPError for 4xx/5xx status codes
        response.raise_for_status() 

        # Log success
        logger.info(f"✅ Message sent successfully to {to}. Response: {response.json()}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # Log and raise the failure, which is now visible
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


# --- Media URL Lookup Function (NEW) ---

def get_media_url(media_id: str) -> str:
    if not ACCESS_TOKEN:
        raise EnvironmentError("Security Error: META_ACCESS_TOKEN is missing for media lookup.")
        
    url = f"{MEDIA_API_BASE_URL}{media_id}"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    try:
        logger.info(f"Attempting to fetch download URL for Media ID: {media_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raise error for bad status codes

        data = response.json()
        download_url = data.get("url")
        
        if download_url:
            logger.info(f"Successfully retrieved media download URL.")
            return download_url
        else:
            # This happens if the API response is successful but doesn't contain 'url'
            raise RuntimeError(f"Meta API response for media ID {media_id} did not contain a 'url'. Response: {data}")

    except requests.exceptions.RequestException as e:
        # Catch connection and HTTP errors
        error_details = {"status_code": e.response.status_code if e.response is not None else "N/A"}
        logger.error(f"❌ Media URL Lookup Failed for ID {media_id} (Status {error_details['status_code']}). Exception: {e}")
        raise RuntimeError(f"Media URL lookup failed: {e}")