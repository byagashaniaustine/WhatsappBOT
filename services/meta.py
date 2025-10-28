import requests
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"
MEDIA_API_BASE_URL = "https://graph.facebook.com/v24.0/"

def send_meta_whatsapp_message(to: str, body: str) -> Dict[str, Any]:
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
        response.raise_for_status() 

        logger.info(f"✅ Message sent successfully to {to}. Response: {response.json()}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # ... (Mantiki ya kushughulikia makosa imetolewa ili kurahisisha) ...
        error_details: Dict[str, Any] = {"status_code": None, "error_data": None}
        if e.response is not None:
            error_details["status_code"] = e.response.status_code
            try:
                error_data = e.response.json()
                error_details["error_data"] = error_data
                logger.error(f"❌ WhatsApp API Error: Failed to send message to {to} (Status {e.response.status_code}). Details: {error_data}")
            except requests.exceptions.JSONDecodeError:
                error_details["error_data"] = e.response.text
                logger.error(f"❌ WhatsApp API Error: Failed to send message to {to} (Status {e.response.status_code}). Response Text: {e.response.text}")
        else:
            logger.error(f"❌ Connection Error: Failed to send message to {to}. Exception: {e}")

        raise RuntimeError(f"Meta API call failed: {e}")


# --- KAZI MPYA YA KUTUMA MTIRIRIKO WA WHATSAPP (FLOW) ---
def send_meta_whatsapp_flow(
    to: str, 
    flow_id: str, 
    screen: str, 
    cta_text: str,
    # Hili ni chaguo ambalo linaweza kutumika kupitisha data ya awali kwa Flow
    data_exchange_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Hutuma Ujumbe wa Interactive Flow kwa kutumia Meta WhatsApp API.
    """
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        error_msg = "Security Error: META_ACCESS_TOKEN or WA_PHONE_NUMBER_ID is missing."
        logger.error(f"❌ {error_msg}")
        raise EnvironmentError(error_msg) 

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Huu ndio muundo unaohitajika wa payload kwa Ujumbe wa Aina ya Flow
    flow_payload = {
        "flow_token": "<UNIQUE_TOKEN_HERE>", # Hii inapaswa kutengenezwa (mfano, UUID)
        "flow_action": "navigate",
        "flow_message_version": "3",
        "flow_type": "template",
        "flow_cta": cta_text,
        "flow_id": flow_id,
        "flow_presentation": {
            "header": "text",
            "body": "Jaza fomu hapa chini ili uanze mchakato.",
            "footer": "Taarifa yako ni siri."
        },
        "flow_action_data": {
            "screen": screen,
            # Inaweza kuongeza 'data' hapa kwa kutuma data ya awali, kwa mfano:
            # "data": data_exchange_payload 
        }
    }
    
    # Jumuisha payload ya Flow katika payload kuu ya Meta
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": flow_payload
    }

    try:
        logger.info(f"Attempting to send Flow ID {flow_id} to {to}")
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status() 

        logger.info(f"✅ Flow message sent successfully to {to}. Response: {response.json()}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # ... (Mantiki ya kushughulikia makosa imetolewa ili kurahisisha) ...
        logger.error(f"❌ WhatsApp Flow API Error: Failed to send Flow to {to}. Exception: {e}")
        raise RuntimeError(f"Meta Flow API call failed: {e}")


# --- Media URL Lookup Function ---

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
        response.raise_for_status() 

        data = response.json()
        download_url = data.get("url")
        
        if download_url:
            logger.info(f"Successfully retrieved media download URL.")
            return download_url
        else:
            raise RuntimeError(f"Meta API response for media ID {media_id} did not contain a 'url'. Response: {data}")

    except requests.exceptions.RequestException as e:
        error_details = {"status_code": e.response.status_code if e.response is not None else "N/A"}
        logger.error(f"❌ Media URL Lookup Failed for ID {media_id} (Status {error_details['status_code']}). Exception: {e}")
        raise RuntimeError(f"Media URL lookup failed: {e}")