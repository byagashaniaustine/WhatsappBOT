import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

# --- Existing Imports ---
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url


logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)
app = FastAPI()

# --- CONFIG ---
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "YOUR_SECRET_TOKEN_HERE")

# ------------------------------
# 1️⃣ WEBHOOK VERIFICATION
# ------------------------------
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    try:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
            logger.info("✅ Webhook verified successfully!")
            return PlainTextResponse(challenge)

        logger.warning("⚠️ Webhook verification failed.")
        raise HTTPException(status_code=403, detail="Verification failed.")

    except Exception as e:
        logger.error(f"❌ Error during webhook verification: {e}")
        raise HTTPException(status_code=403, detail="Webhook verification error.")


# ------------------------------
# 2️⃣ INCOMING MESSAGE HANDLER
# ------------------------------
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    try:
        payload = await request.json()
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            logger.info("No message content — ignoring.")
            return PlainTextResponse("OK")

        message = messages[0]
        from_number = message.get("from")
        message_type = message.get("type")

        if not from_number:
            return PlainTextResponse("OK")

        # ------------------------------
        # 🟢 TEXT MESSAGE
        # ------------------------------
        if message_type == "text":
            text_body = message.get("text", {}).get("body", "")
            payload = {"From": from_number, "Body": text_body}
            logger.info(f"💬 Text message from {from_number}: {text_body}")
            await whatsapp_menu(payload)

        # ------------------------------
        # 🟣 MEDIA UPLOAD
        # ------------------------------
        elif message_type in ["image", "document", "audio", "video"]:
            media_data = message.get(message_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type")

            if not media_id:
                send_meta_whatsapp_message(from_number, "Samahani, faili halikupatikana.")
                return PlainTextResponse("OK")

            actual_media_url = get_media_url(media_id)
            result = process_file_upload(
                user_id=from_number,
                user_name="",
                user_phone=from_number,
                flow_type="whatsapp_upload",
                media_url=actual_media_url,
                mime_type=mime_type
            )

            logger.info(f"📎 File processed for {from_number}: {result}")
            send_meta_whatsapp_message(from_number, "✅ Faili lako limepokelewa, linafanyiwa uchambuzi.")

        # ------------------------------
        # ❌ UNKNOWN MESSAGE TYPE
        # ------------------------------
        else:
            send_meta_whatsapp_message(
                from_number,
                f"Haiwezi kushughulikia ujumbe wa aina '{message_type}'."
            )

        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ WhatsApp webhook error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)
