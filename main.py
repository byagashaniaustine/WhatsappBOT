import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import math
from typing import Dict, Any
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload

from services.twilio import send_message

logger = logging.getLogger("whatsapp_app")
app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    try:
        data = await request.form()
        payload = dict(data)

        from_number = str(payload.get("From") or "")
        if not from_number:
            logger.warning("⚠️ Missing 'From' number in request")
            return PlainTextResponse("OK")

        # --- Check for Media Content (Files/Images) ---
        # Twilio sends 'NumMedia' when a file is attached
        num_media = int(payload.get("NumMedia", 0))
        
        if num_media > 0:
            logger.info(f"📁 Media content detected from {from_number}. Num media: {num_media}")
            
            # Assuming we only process the first media item (MediaUrl0)
            media_url = payload.get("MediaUrl0")
            mime_type = payload.get("MediaContentType0")
            
            if media_url and mime_type:
                # Pass media details for download, analysis, and storage
                # Using from_number for both ID and Phone since user name is unknown in webhook
                result = process_file_upload(
                    user_id=from_number, 
                    user_name="", # Name is not provided in a standard Twilio media webhook
                    user_phone=from_number,
                    flow_type="whatsapp_upload",
                    media_url=media_url,
                    mime_type=mime_type
                )
                logger.info(f"File analysis and storage result: {result}")

            else:
                send_message(
                    to_phone=from_number,
                    message="❌ Samahani, nimeshindwa kupata kiungo au aina ya faili ulilotuma."
                )
                
        else:
            # Normal text message or other non-media content
            logger.info(f"💬 Text message content detected from {from_number}. Passing to menu handler.")
            await whatsapp_menu(payload)
            
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error handling WhatsApp webhook: {e}")
        # Attempt to send a generic error back to the user
        try:
             # Use the phone number extracted earlier, if available
             if 'from_number' in locals() and from_number:
                 send_message(from_number, "❌ Samahani, kuna tatizo la kiufundi limetokea. Tafadhali jaribu tena.")
        except Exception:
             # Suppress error if sending the error message fails
             pass
        return PlainTextResponse("Internal Server Error", status_code=500)

