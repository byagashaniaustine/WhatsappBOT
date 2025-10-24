import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Dict, Any

# Assuming these modules exist in your project
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message # Use the Meta/Cloud API sender

logger = logging.getLogger("whatsapp_app")
app = FastAPI()

# --- Configuration for Webhook Verification ---
# You MUST set this environment variable on your Railway deployment 
# to match the token entered in the Meta Developer Portal.
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "YOUR_SECRET_TOKEN_HERE")


# --- 1. WEBHOOK VERIFICATION (GET) ENDPOINT ---
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    """
    Handles the Meta verification request (GET request) when setting up the webhook.
    """
    try:
        # 1. Get query parameters from the request
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        # 2. Check for matching mode and token
        if mode and token:
            if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
                # Verification successful, return the challenge string
                logger.info("✅ Webhook verified successfully!")
                return PlainTextResponse(challenge)
            else:
                # Token mismatch or incorrect mode
                logger.warning("⚠️ Webhook verification failed: Token mismatch or incorrect mode.")
                raise HTTPException(status_code=403, detail="Verification failed: Token mismatch or incorrect mode.")
        
        # Missing required parameters
        logger.warning("⚠️ Webhook verification failed: Missing required parameters.")
        raise HTTPException(status_code=400, detail="Missing required parameters for verification.")

    except Exception as e:
        logger.error(f"❌ Error during webhook verification: {e}")
        # Return 403 Forbidden on failure to pass verification
        raise HTTPException(status_code=403, detail="Verification request processing error.")


# --- 2. INCOMING MESSAGE (POST) ENDPOINT ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    """
    Handles incoming messages (text and media) from the WhatsApp webhook.
    """
    try:
        data = await request.form()
        payload = dict(data)
        from_number = str(payload.get("From") or "")
        
        if not from_number:
            logger.warning("⚠️ Missing 'From' number in request")
            return PlainTextResponse("OK")
            
        # Twilio webhooks use 'NumMedia' for file/image attachments
        num_media = int(str(payload.get("NumMedia", 0)))
        
        if num_media > 0:
            # --- Handle Media Content ---
            logger.info(f"📁 Media content detected from {from_number}. Num media: {num_media}")
            
            # Assuming we only process the first media item (MediaUrl0)
            media_url = str(payload.get("MediaUrl0"))
            mime_type = str(payload.get("MediaContentType0"))
            
            if media_url and mime_type:
                # Pass media details for download, analysis, and storage
                result = process_file_upload(
                    user_id=from_number, 
                    user_name="",
                    user_phone=from_number,
                    flow_type="whatsapp_upload",
                    media_url=media_url,
                    mime_type=mime_type
                )
                logger.info(f"File analysis and storage result: {result}")

            else:
                # Notify user if media content is incomplete
                send_meta_whatsapp_message(
                    from_number,
                    "❌ Samahani, nimeshindwa kupata kiungo au aina ya faili ulilotuma."
                )
                
        else:
            # --- Handle Text Message Content ---
            logger.info(f"💬 Text message content detected from {from_number}. Passing to menu handler.")
            await whatsapp_menu(payload)
            
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error handling WhatsApp webhook: {e}")

        # Attempt to send a generic error back to the user
        try:
            from_number_safe = locals().get("from_number", None)
            if from_number_safe:
                # Use the imported Meta-compatible sending function
                send_meta_whatsapp_message(
                    from_number_safe,
                    "❌ Samahani, kuna tatizo la kiufundi limetokea. Tafadhali jaribu tena."
                )
        except Exception as inner_error:
            logger.warning(f"⚠️ Failed to send error message to user via Meta API service: {inner_error}")
            pass

        return PlainTextResponse("Internal Server Error", status_code=500)
