import os
import json
import base64
import logging
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.PublicKey import RSA

from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# Load private key from env variable
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    raise RuntimeError("PRIVATE_KEY environment variable is not set")

private_key_str = private_key_str.replace("\\n", "\n")
PRIVATE_KEY = RSA.import_key(private_key_str)
RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY)

def unpad_pkcs7(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]

@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()

        encrypted_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        if encrypted_b64 and encrypted_aes_key_b64 and iv_b64:
            try:
                # Decode RSA-encrypted AES key
                encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key)

                # Decode AES-CBC IV and ciphertext
                iv = base64.b64decode(iv_b64)
                ciphertext = base64.b64decode(encrypted_b64)

                # Decrypt AES-CBC
                cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
                decrypted_bytes = cipher_aes.decrypt(ciphertext)
                decrypted_bytes = unpad_pkcs7(decrypted_bytes)

                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))
                logger.info(f"📥 Decrypted Flow Data: {decrypted_data}")

                # Forward to normal WhatsApp flow
                from_number = decrypted_data.get("From")
                user_text = decrypted_data.get("Body")

                if from_number and user_text:
                    background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})

                return PlainTextResponse("OK")

            except Exception as e:
                logger.exception(f"Flow Decryption Error: {e}")
                return PlainTextResponse("Failed to decrypt flow payload", status_code=500)

        # Fallback: normal WhatsApp message processing
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
                background_tasks.add_task(
                    send_meta_whatsapp_message,
                    from_number,
                    "Samahani, faili halikupatikana."
                )
                return PlainTextResponse("OK")

            background_tasks.add_task(
                send_meta_whatsapp_message,
                from_number,
                "*Faili limepokelewa.*\n🔄 Linafanyiwa uchambuzi...\nTafadhali subiri."
            )

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

        background_tasks.add_task(
            send_meta_whatsapp_message,
            from_number,
            f"Samahani, siwezi kusoma ujumbe wa aina: {msg_type}"
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Webhook Error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)
