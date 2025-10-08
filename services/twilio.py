import os
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")  # WhatsApp number

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to: str, body: str):
    """
    Send plain text WhatsApp message
    """
    client.messages.create(
        from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
        to=f"whatsapp:{to}",
        body=body
    )


def trigger_twilio_flow(user_number: str, action: str, parameters: dict):
    """
    Trigger a Twilio Studio Flow with dynamic user values but fixed key names.
    """
    # Map menu action → Flow SID
    flow_map = {
        "open_flow_upload_documents": "HX705e35a409323bab371b5d371771ae33",  # replace with your Flow SID
        "open_flow_loan_calculator": "FWYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY"  # replace with your Flow SID
    }

    flow_sid = flow_map.get(action)
    if not flow_sid:
        return {"status": "error", "message": f"No Flow configured for action '{action}'"}

    try:
        execution = client.studio.v2.flows(flow_sid).executions.create(
            to=f"whatsapp:{user_number}",
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            parameters=parameters
        )
        return {"status": "success", "message": f"Flow '{action}' triggered for {user_number}", "execution_sid": execution.sid}

    except Exception as e:
        return {"status": "error", "message": str(e)}
