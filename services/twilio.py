import os 
from twilio.rest import Client


TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_message(to: str, body: str):
    client.messages.create(
        from_=TWILIO_PHONE_NUMBER,
        body=body,
        to=to
    )

def trigger_twilio_flow(user_number: str, action: str):
    """
    Triggers a Twilio Flow by sending a message to the user.
    The Flow should be configured to start when it receives this keyword or instruction.
    """
    try:
        message_body = f"⚡ Tumeanza mchakato wa '{action}'. Tafadhali fuata maelekezo yaliyotolewa."
        client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            body=message_body,
            to=user_number
        )
        return {"status": "success", "message": f"Flow '{action}' triggered for {user_number}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
