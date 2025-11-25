import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

# Cryptography
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Util.Padding import unpad

# Project modules
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

# Logging
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# --- UTILITY: Robust Private Key Loader ---
def load_private_key(key_string: str) -> RSA.RsaKey:
    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    try:
        return RSA.import_key(key_string)
    except ValueError:
        # Try reconstructing PEM format
        key_lines = [line.strip() for line in key_string.split('\n') if line.strip()]
        if not key_string.startswith("-----BEGIN"):
            cleaned_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----"
            return RSA.import_key(cleaned_key)
        raise

# Load RSA private key and initialize cipher
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    raise RuntimeError("PRIVATE_KEY environment variable is not set.")

PRIVATE_KEY = load_private_key(private_key_str)
RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)

# --- WEBHOOK VERIFICATION (GET) ---
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

# --- DEBUG ENDPOINT ---
@app.post("/debug-test/")
async def debug_test(request: Request):
    logger.critical(f"✅ /debug-test/ called from {request.client.host if request.client else 'Unknown'}")
    raw_body = await request.body()
    logger.debug(f"[DEBUG] Raw body length: {len(raw_body)}")
    return PlainTextResponse("Debug successful.", status_code=200)

# --- MAIN WHATSAPP WEBHOOK ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.critical(f"🚀 Webhook POST received from {request.client.host if request.client else 'Unknown'}")
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body.decode("utf-8"))
        logger.debug(f"Incoming payload (truncated): {str(payload)[:500]}")

        # --- Encrypted Flow Handling ---
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")
        if encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64:
            try:
                # Decode & decrypt AES key
                encrypted_aes_bytes = base64.b64decode(encrypted_aes_key_b64)
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_bytes)

                # Decode IV and encrypted payload
                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)

                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.info(f"📥 Decrypted flow data: {json.dumps(decrypted_data, indent=2)}")

                # --- Forward to whatsapp_menu ---
                flow_payload = {
                    "From": decrypted_data.get("from_number", "SYSTEM_USER"),
                    "Body": decrypted_data.get("data", {}),
                    "screen": decrypted_data.get("screen"),
                    "flow_id": decrypted_data.get("data", {}).get("flow_id")
                }
                background_tasks.add_task(whatsapp_menu, flow_payload)

                # Immediately return 200 OK
                return PlainTextResponse("OK")

            except Exception as e:
                logger.exception(f"Flow decryption failed: {e}")
                return PlainTextResponse("Flow decryption failed.", status_code=400)

        # --- Regular WhatsApp message handling ---
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

        if msg_type == "text":
            user_text = message.get("text", {}).get("body", "")
            logger.info(f"💬 Message from {from_number}: {user_text}")
            background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})
            return PlainTextResponse("OK")

        if msg_type in ["image", "document", "audio", "video"]:
            media_data = message.get(msg_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type")
            if not media_id:
                background_tasks.add_task(send_meta_whatsapp_message, from_number, "Samahani, faili halikupatikana.")
                return PlainTextResponse("OK")

            # Notify user
            background_tasks.add_task(
                send_meta_whatsapp_message,
                from_number,
                "*Faili limepokelewa.*\n🔄 Linafanyiwa uchambuzi..."
            )

            # Background media processing
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
                send_meta_whatsapp_message(from_number, "✅ *Uchambuzi wa faili umekamilika.*")

            background_tasks.add_task(process_job)
            return PlainTextResponse("OK")

        # Unsupported type
        background_tasks.add_task(
            send_meta_whatsapp_message,
            from_number,
            f"Samahani, siwezi kusoma ujumbe wa aina: {msg_type}"
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Webhook Error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)
