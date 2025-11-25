import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

# Cryptography
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA256

# Your project modules
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

# -------------------------------
# Logging Setup
# -------------------------------
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)

# -------------------------------
# FastAPI App
# -------------------------------
app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
PRIVATE_KEY_STR = os.environ.get("PRIVATE_KEY")
if not PRIVATE_KEY_STR:
    raise RuntimeError("PRIVATE_KEY env variable not set")

# -------------------------------
# Load Private Key + RSA Cipher
# -------------------------------
def load_private_key(key_string: str) -> RSA.RsaKey:
    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    return RSA.import_key(key_string)

PRIVATE_KEY = load_private_key(PRIVATE_KEY_STR)
RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)

# -------------------------------
# Webhook Verification
# -------------------------------
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

# -------------------------------
# Debug / Health Check Endpoint
# -------------------------------
@app.post("/debug-test/")
async def debug_test(request: Request):
    logger.critical(f"✅ Debug endpoint hit from {request.client.host if request.client else 'Unknown'}")
    return PlainTextResponse("Debug check successful. Check logs.", status_code=200)

# -------------------------------
# WhatsApp Webhook (POST)
# Handles Flows + Text + Media
# -------------------------------
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_body = await request.body()
        payload_str = raw_body.decode("utf-8", errors="ignore")
        logger.debug(f"Incoming raw payload (truncated 500 chars): {payload_str[:500]}")

        payload = json.loads(payload_str)

        # -------------------------------
        # Check for Flow payload
        # -------------------------------
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        if encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64:
            try:
                # Decode & decrypt AES key
                aes_key = RSA_CIPHER.decrypt(base64.b64decode(encrypted_aes_key_b64))
                iv = base64.b64decode(iv_b64)

                # AES GCM decrypt
                encrypted_bytes = base64.b64decode(encrypted_flow_b64)
                ciphertext, tag = encrypted_bytes[:-16], encrypted_bytes[-16:]
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.info(f"📥 Decrypted Flow payload: {json.dumps(decrypted_data, indent=2)}")

                # Send to whatsapp_menu in background
                from_number = decrypted_data.get("from_number")
                if from_number:
                    background_tasks.add_task(
                        whatsapp_menu,
                        {"From": from_number, "payload": decrypted_data, "flow": True}
                    )
                    logger.info(f"📤 Flow payload sent to whatsapp_menu for {from_number}")

                # Always respond 200 OK immediately for Flow health check
                return PlainTextResponse("OK")

            except Exception as e:
                logger.exception(f"⚠️ Flow decryption failed: {e}")
                return PlainTextResponse("Failed to decrypt flow payload.", status_code=500)

        # -------------------------------
        # Legacy Text / Media Messages
        # -------------------------------
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return PlainTextResponse("OK")

        message = messages[0]
        from_number = message.get("from")
        msg_type = message.get("type")

        if not from_number:
            return PlainTextResponse("OK")

        # -------------------------------
        # Text Messages
        # -------------------------------
        if msg_type == "text":
            user_text = message.get("text", {}).get("body", "")
            logger.info(f"💬 Text from {from_number}: {user_text}")
            background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})
            return PlainTextResponse("OK")

        # -------------------------------
        # Media Messages
        # -------------------------------
        if msg_type in ["image", "document", "audio", "video"]:
            media_data = message.get(msg_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type")

            if not media_id:
                background_tasks.add_task(
                    send_meta_whatsapp_message,
                    from_number,
                    "Samahani, faili halikupatikana."
                )
                return PlainTextResponse("OK")

            # Notify user processing
            background_tasks.add_task(
                send_meta_whatsapp_message,
                from_number,
                "*Faili limepokelewa.*\n🔄 Linafanyiwa uchambuzi...\nTafadhali subiri."
            )

            # Process file in background
            def process_job():
                media_url = get_media_url(media_id)
                process_file_upload(
                    user_id=from_number,
                    user_name="",
                    user_phone=from_number,
                    flow_type="whatsapp_upload",
                    media_url=media_url,
                    mime_type=mime_type
                )
                send_meta_whatsapp_message(
                    from_number,
                    "✅ *Uchambuzi wa faili umekamilika.*\nAsante kwa kuchagua huduma zetu."
                )

            background_tasks.add_task(process_job)
            return PlainTextResponse("OK")

        # -------------------------------
        # Unknown Message Type
        # -------------------------------
        background_tasks.add_task(
            send_meta_whatsapp_message,
            from_number,
            f"Samahani, siwezi kusoma ujumbe wa aina: {msg_type}"
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Webhook error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)
