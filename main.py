import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES

from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# Load RSA private key from environment
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    raise RuntimeError("PRIVATE_KEY environment variable is not set")

# Replace escaped newlines with real newlines
private_key_str = private_key_str.replace("\\n", "\n")
PRIVATE_KEY = RSA.import_key(private_key_str)
RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY)


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

        # ---- Encrypted Flow Payload ----
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        logger.info(
            f"Payload flags -> encrypted_flow_data: {encrypted_flow_b64 is not None}, "
            f"encrypted_aes_key: {encrypted_aes_key_b64 is not None}, "
            f"iv: {iv_b64 is not None}"
        )

        if encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64:
            try:
                # 1️⃣ Decode and decrypt AES key with RSA
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)
                logger.info(f"AES key (base64): {base64.b64encode(aes_key).decode()}")

                # 2️⃣ Decode IV and encrypted flow
                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)

                logger.info(f"IV (base64): {base64.b64encode(iv).decode()}")
                logger.info(f"Encrypted flow length: {len(encrypted_flow_bytes)} bytes")

                # 3️⃣ Split ciphertext and tag (last 16 bytes are GCM tag)
                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]

                logger.info(f"Ciphertext length: {len(ciphertext)}, Tag (base64): {base64.b64encode(tag).decode()}")

                # 4️⃣ Decrypt AES-GCM
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.info(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data, indent=2)}")

                # 5️⃣ Trigger WhatsApp menu processing
                from_number = decrypted_data.get("From")
                user_text = decrypted_data.get("Body")
                if from_number and user_text:
                    background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})

                # 6️⃣ Return encrypted response in base64 (optional)
                response = {
                    "screen": "SCREEN_NAME",
                    "data": {"some_key": "some_value"}
                }

                # Encrypt response using AES-GCM with flipped IV
                flipped_iv = bytes([b ^ 0xFF for b in iv])
                cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(json.dumps(response).encode("utf-8"))
                full_resp = encrypted_resp_bytes + resp_tag
                full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")

                return PlainTextResponse(full_resp_b64)

            except Exception as e:
                logger.exception(f"Flow Decryption Error: {e}")
                return PlainTextResponse("Failed to decrypt flow payload", status_code=500)

        # ---- Regular WhatsApp message ----
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

            # Notify user immediately
            background_tasks.add_task(
                send_meta_whatsapp_message,
                from_number,
                "*Faili limepokelewa.*\n🔄 Linafanyiwa uchambuzi...\nTafadhali subiri."
            )

            # Continue processing in background
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
