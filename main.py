import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Dict, Any

# Assuming these modules exist in your project
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message 

logger = logging.getLogger("whatsapp_app")
app = FastAPI()

# --- Configuration for Webhook Verification ---
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "YOUR_SECRET_TOKEN_HERE")


# --- 1. WEBHOOK VERIFICATION (GET) ENDPOINT ---
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    """
    Handles the Meta verification request (GET request) when setting up the webhook.
    (This part remains the same)
    """
    try:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
                logger.info("✅ Webhook verified successfully!")
                return PlainTextResponse(challenge)
            else:
                logger.warning("⚠️ Webhook verification failed: Token mismatch or incorrect mode.")
                raise HTTPException(status_code=403, detail="Verification failed: Token mismatch or incorrect mode.")
        
        logger.warning("⚠️ Webhook verification failed: Missing required parameters.")
        raise HTTPException(status_code=400, detail="Missing required parameters for verification.")

    except Exception as e:
        logger.error(f"❌ Error during webhook verification: {e}")
        raise HTTPException(status_code=403, detail="Verification request processing error.")


# --- 2. INCOMING MESSAGE (POST) ENDPOINT (UPDATED FOR META JSON) ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    """
    Handles incoming messages (text and media) using the Meta/Cloud API JSON payload format.
    """
    try:
        # Meta sends a JSON payload in the body, not form data
        meta_payload = await request.json()
        
        # We need to traverse the nested Meta JSON structure
        entry = meta_payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        # Check if this is a message notification
        if value.get("messaging_product") != "whatsapp":
            logger.info("Ignoring non-whatsapp notification.")
            return PlainTextResponse("OK")

        messages = value.get("messages", [])
        
        if not messages:
            # Handle status updates, contacts, etc.
            logger.info("Ignoring non-message payload (e.g., status update, read receipt).")
            return PlainTextResponse("OK")

        # Process the first message in the list
        message = messages[0]
        from_number = message.get("from") # The sender's phone number
        message_type = message.get("type") # e.g., 'text', 'image', 'document'
        
        if not from_number:
            logger.warning("⚠️ Missing 'from' number in Meta message payload.")
            return PlainTextResponse("OK")

        # --- Standardize Payload for existing BOT functions ---
        # We create a simple payload dictionary that might be expected by your existing modules
        standard_payload: Dict[str, Any] = {
            "From": from_number, # Mapping to the old 'From' for compatibility
            "Body": message.get("text", {}).get("body", ""),
            "MediaUrl0": None,
            "NumMedia": 0,
        }

        # --- Handle Different Message Types (Text, Media) ---
        if message_type == "text":
            text_body = message.get("text", {}).get("body", "")
            standard_payload["Body"] = text_body
            
            logger.info(f"💬 Text message detected from {from_number}. Passing to menu handler.")
            # Pass the full, raw Meta payload for full context if needed by whatsapp_menu
            await whatsapp_menu(meta_payload)
            
        elif message_type in ["image", "document", "audio", "video"]:
            # --- Handle Media Content ---
            media_data = message.get(message_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type")
            
            if media_id and mime_type:
                # IMPORTANT: Meta's payload only gives the media ID, not the URL. 
                # Your process_file_upload needs to be updated to use the media ID and 
                # call the Meta API to get the actual URL or download the file.
                # For now, we simulate the Twilio flow by passing key details.
                standard_payload["NumMedia"] = 1
                
                logger.info(f"📁 Media content detected from {from_number}. Type: {message_type}")
                
                # NOTE: Since we cannot easily get the MediaUrl0 here, we pass the ID and Mime Type
                # Assuming process_file_upload can handle the ID instead of a URL. 
                # If not, this function will need significant modification.
                result = process_file_upload(
                    user_id=from_number, 
                    user_name="",
                    user_phone=from_number,
                    flow_type="whatsapp_upload",
                    media_url=media_id,  # Pass ID instead of URL
                    mime_type=mime_type
                )
                logger.info(f"File analysis and storage result: {result}")
            else:
                send_meta_whatsapp_message(
                    from_number,
                    "❌ Samahani, nimeshindwa kupata kiungo au aina ya faili ulilotuma."
                )

        else:
            # Handle unsupported message types (e.g., sticker, location)
            send_meta_whatsapp_message(
                from_number,
                f"Samahani, sijui jinsi ya kushughulikia ujumbe wa aina ya '{message_type}'."
            )
            
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error handling WhatsApp webhook: {e}")

        # Attempt to send a generic error back to the user
        try:
            from_number_safe = locals().get("from_number", None)
            if from_number_safe:
                send_meta_whatsapp_message(
                    from_number_safe,
                    "❌ Samahani, kuna tatizo la kiufundi limetokea. Tafadhali jaribu tena."
                )
        except Exception as inner_error:
            logger.warning(f"⚠️ Failed to send error message to user via Meta API service: {inner_error}")
            pass

        return PlainTextResponse("Internal Server Error", status_code=500)
