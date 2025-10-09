# services/twilio.py

import os
import json
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional, Dict, Any, Union # Import necessary types for clarity

logger = logging.getLogger(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
    raise EnvironmentError("Missing Twilio credentials (SID, TOKEN, or PHONE NUMBER).")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Hardcoded Template SIDs (Flows and Content Templates like List Messages)
FLOW_TEMPLATES = {
    "open_flow_upload_documents": "HX705e35a409323bab371b5d371771ae33",
    "open_flow_loan_calculator": "HXyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
    # Placeholder SID for the new Nakopesheka List Message Template
    "nakopesheka_list_menu": "HXkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk" 
}

def send_message(to: str, body: str) -> None:
    """
    Safely send a basic WhatsApp message via Twilio.
    """
    try:
        # Note: 'to' must contain the 'whatsapp:' prefix for the Twilio API
        target_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        
        message = client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=target_to,
            body=body
        )

        logger.info(f"✅ WhatsApp message sent to {target_to}. SID: {message.sid}")

    except TwilioRestException as e:
        if e.status == 429:
            logger.warning(
                f"⚠️ Twilio daily message limit reached. Skipping message to {to}. Reason: {e.msg}"
            )
        else:
            logger.error(f"❌ Twilio API error while sending to {to}: {e.msg} (HTTP {e.status})", exc_info=True)
    except Exception as e:
        logger.exception(f"❌ General error while sending message to {to}: {str(e)}")


def trigger_twilio_flow(user_phone: str, flow_type: str, user_name: str, user_id: str) -> dict:
    """
    Trigger a Twilio WhatsApp Flow safely.
    """
    # Flow data is passed positionally and constructed inside the helper
    return _send_content_template(user_phone, flow_type, user_name=user_name, user_id=user_id)


def send_list_message_template(user_phone: str, template_key: str, variables: Dict[str, Any]) -> dict:
    """
    Send an approved List Message Content Template (twilio/list-picker).
    """
    # List message variables are passed directly via the 'variables' keyword
    return _send_content_template(user_phone, template_key, variables=variables)


def _send_content_template(
    user_phone: str, 
    template_key: str, 
    user_name: str = "", 
    user_id: str = "", 
    variables: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Internal helper to send any Content Template (Flow or List Message).
    
    If 'variables' is provided, it's used for List/Button messages.
    If 'variables' is None, it uses user_name/user_id to construct Flow variables.
    """
    try:
        content_sid = FLOW_TEMPLATES.get(template_key)
        if not content_sid:
            msg = f"No Content Template found for key '{template_key}'"
            logger.warning(msg)
            return {"status": "error", "message": msg}

        # --- Variable Construction Logic ---
        if variables is not None:
            # Use the dictionary passed directly (for List Messages)
            content_vars = variables
        else:
            # Construct default Flow context variables
            content_vars = {
                "user_id": user_id or "",
                "user_name": user_name or "",
                "user_phone": user_phone,
                "flow_type": template_key
            }

        # The Twilio API requires content_variables to be a JSON string
        content_vars_json = json.dumps(content_vars)

        message = client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=f"whatsapp:{user_phone}",
            content_sid=content_sid,
            content_variables=content_vars_json
        )

        logger.info(f"✅ Sent Content Template '{template_key}' for {user_phone}. Message SID: {message.sid}")
        return {"status": "success", "message": f"Template '{template_key}' sent for {user_phone}"}

    except TwilioRestException as e:
        if e.status == 429:
            logger.warning(
                f"⚠️ Twilio limit reached. Skipping template to {user_phone}. Reason: {e.msg}"
            )
        else:
            logger.error(f"❌ Twilio API error sending template for {user_phone}: {e.msg} (HTTP {e.status})", exc_info=True)
        return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.exception(f"❌ General error sending template for {user_phone}")
        return {"status": "error", "message": str(e)}