import logging
import os
import base64
import json
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from Crypto.Cipher import AES 

from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# Load private key from environment variable
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    raise RuntimeError("PRIVATE_KEY environment variable is not set")

# Replace escaped newlines with actual newlines
private_key_str = private_key_str.replace("\\n", "\n").strip()
PRIVATE_KEY = serialization.load_pem_private_key(
    private_key_str.encode("utf-8"),
    password=None
)

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

        # 1️⃣ Check for encrypted flow payload
        encrypted_flow_data = (
            payload.get("encrypted_flow_data")
        )
        encrypted_aes_key = (
            payload.get("encrypted_aes_key")
        )
        initial_vector = (
            payload.get("initial_vector")
        )

        if encrypted_flow_data and encrypted_aes_key and initial_vector:
            try:
                # 2️⃣ Decrypt AES key using RSA
                aes_key = PRIVATE_KEY.decrypt(
                    base64.b64decode(encrypted_aes_key),
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )

                # 3️⃣ Decode IV
                iv = base64.b64decode(initial_vector)

                # 4️⃣ Decrypt flow data using AES-CBC
                cipher = AES.new(aes_key, AES.MODE_CBC, iv)
                encrypted_bytes = base64.b64decode(encrypted_flow_data)
                decrypted_bytes = cipher.decrypt(encrypted_bytes)

                # 5️⃣ Remove PKCS7 padding
                padding_len = decrypted_bytes[-1]
                decrypted_bytes = decrypted_bytes[:-padding_len]

                # 6️⃣ Convert to JSON
                decrypted_json = json.loads(decrypted_bytes.decode("utf-8"))
                logger.info(f"📥 Decrypted Flow Data: {decrypted_json}")

                # 7️⃣ Pass decrypted data to your flow handler
                from_number = decrypted_json.get("From")
                user_text = decrypted_json.get("Body")
                if from_number and user_text:
                    background_tasks.add_task(
                        whatsapp_menu, {"From": from_number, "Body": user_text}
                    )

                return PlainTextResponse("OK")
            except Exception as e:
                logger.exception(f"Flow Decryption Error: {e}")
                return PlainTextResponse("Failed to decrypt flow payload", status_code=500)

        # 8️⃣ Fallback: regular WhatsApp messages
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
