# services/twilio.py

import os
import json
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional, Dict, Any, cast # Import 'cast'

logger = logging.getLogger(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
# NOTE: This environment variable must contain the E.164 number (e.g., +1234567890)
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER") 

# --- FIX: Ensure TWILIO_PHONE_NUMBER is treated as str after validation ---
if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
    # This check ensures we won't proceed with None values
    raise EnvironmentError("Missing Twilio credentials (SID, TOKEN, or PHONE NUMBER).")

# We use typing.cast to tell the type checker that TWILIO_PHONE_NUMBER is guaranteed to be a string
# because of the check above. This resolves the Pylance warning without suppressing the check.
TWILIO_PHONE_NUMBER_STR = cast(str, TWILIO_PHONE_NUMBER)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Hardcoded Template SIDs (Flows and Content Templates)
FLOW_TEMPLATES = {
    "open_flow_upload_documents": "HX705e35a409323bab371b5d371771ae33",
    "open_flow_loan_calculator": "HXyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
    "nakopesheka_list_menu": "HX332ef91b92981458dd394eb18f97e0f5" 
}

# --- Helper function to ensure the sender number is always correct ---
def _get_whatsapp_from_number(phone_number: str) -> str:
    """Ensures the number is prefixed with 'whatsapp:'."""
    return phone_number if phone_number.startswith("whatsapp:") else f"whatsapp:{phone_number}"
# -------------------------------------------------------------------

def send_message(to: str, body: str) -> None:
    """
    Safely send a basic WhatsApp message via Twilio.
    """
    try:
        # Pylance is satisfied because we use TWILIO_PHONE_NUMBER_STR
        from_number_whatsapp = _get_whatsapp_from_number(TWILIO_PHONE_NUMBER_STR) 
        target_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        
        message = client.messages.create(
            from_=from_number_whatsapp,
            to=target_to,
            body=body
        )

        logger.info(f"✅ WhatsApp message sent to {target_to}. SID: {message.sid}")

    except TwilioRestException as e:
        if e.status == 429:
            logger.warning(f"⚠️ Twilio daily message limit reached. Skipping message to {to}. Reason: {e.msg}")
        else:
            logger.error(f"❌ Twilio API error while sending to {to}: {e.msg} (HTTP {e.status})", exc_info=True)
    except Exception as e:
        logger.exception(f"❌ General error while sending message to {to}: {str(e)}")


def trigger_twilio_flow(user_phone: str, flow_type: str, user_name: str, user_id: str) -> dict:
    """
    Trigger a Twilio WhatsApp Flow safely.
    """
    return _send_content_template(user_phone, flow_type, user_name=user_name, user_id=user_id)


def send_list_message_template(user_phone: str, template_key: str, variables: Dict[str, Any]) -> dict:
    """
    Send an approved Content Template (Quick Reply/List Message).
    """
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
    """
    try:
        content_sid = FLOW_TEMPLATES.get(template_key)
        if not content_sid:
            msg = f"No Content Template found for key '{template_key}'"
            logger.warning(msg)
            return {"status": "error", "message": msg}

        # --- Variable Construction Logic ---
        if variables is not None:
            content_vars = variables
        else:
            content_vars = {
                "user_id": user_id or "",
                "user_name": user_name or "",
                "user_phone": user_phone,
                "flow_type": template_key
            }

        content_vars_json = json.dumps(content_vars)
        
        # **FIX**: Use the guaranteed string variable (TWILIO_PHONE_NUMBER_STR)
        from_number_whatsapp = _get_whatsapp_from_number(TWILIO_PHONE_NUMBER_STR)

        message = client.messages.create(
            from_=from_number_whatsapp, 
            to=f"whatsapp:{user_phone}",
            content_sid=content_sid,
            content_variables=content_vars_json
        )

        logger.info(f"✅ Sent Content Template '{template_key}' for {user_phone}. Message SID: {message.sid}")
        return {"status": "success", "message": f"Template '{template_key}' sent for {user_phone}"}

    except TwilioRestException as e:
        if e.status == 429:
            logger.warning(f"⚠️ Twilio limit reached. Skipping template to {user_phone}. Reason: {e.msg}")
        else:
            logger.error(f"❌ Twilio API error sending template for {user_phone}: {e.msg} (HTTP {e.status})", exc_info=True)
        return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.exception(f"❌ General error sending template for {user_phone}")
        return {"status": "error", "message": str(e)}