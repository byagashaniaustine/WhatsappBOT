import os
import json
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
    raise EnvironmentError("Missing Twilio credentials (SID, TOKEN, or PHONE NUMBER).")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Hardcoded Flow SIDs
FLOW_TEMPLATES = {
    "open_flow_upload_documents": "HX705e35a409323bab371b5d371771ae33",
    "open_flow_loan_calculator": "HXyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
}

def send_message(to: str, body: str) -> None:
    """
    Safely send a WhatsApp message via Twilio.
    """
    try:
        message = client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=f"whatsapp:{to}",
            body=body
        )
        logger.info(f"✅ WhatsApp message sent to {to}. SID: {message.sid}")

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
    try:
        flow_sid = FLOW_TEMPLATES.get(flow_type)
        if not flow_sid:
            msg = f"No Flow Template found for type '{flow_type}'"
            logger.warning(msg)
            return {"status": "error", "message": msg}

        content_vars = {
            "user_id": user_id or "",
            "user_name": user_name or "",
            "user_phone": user_phone,
            "flow_type": flow_type
        }

        message = client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=f"whatsapp:{user_phone}",
            content_sid=flow_sid,
            content_variables=json.dumps(content_vars)
        )

        logger.info(f"✅ Triggered Flow '{flow_type}' for {user_phone}. Message SID: {message.sid}")
        return {"status": "success", "message": f"Flow '{flow_type}' triggered for {user_phone}"}

    except TwilioRestException as e:
        if e.status == 429:
            logger.warning(
                f"⚠️ Twilio daily Flow limit reached. Skipping Flow to {user_phone}. Reason: {e.msg}"
            )
        else:
            logger.error(f"❌ Twilio API error triggering Flow for {user_phone}: {e.msg} (HTTP {e.status})", exc_info=True)
        return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.exception(f"❌ General error triggering Flow for {user_phone}")
        return {"status": "error", "message": str(e)}
