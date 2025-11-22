import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

# Import cryptography libraries
try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad # Not strictly needed for GCM, but good practice if mode changes
except ImportError:
    # A helpful message if the user forgot to install pycryptodome
    raise RuntimeError("PyCryptodome is not installed. Please install with: pip install pycryptodome")

# Assuming these modules exist in the user's project structure
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

# Setup logging
logger = logging.getLogger("whatsapp_app")
# Set a lower level for detailed key debugging on startup
logger.setLevel(logging.DEBUG) 

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# --- KEY LOADING AND SETUP ---
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    # This will still raise an error, but with a clearer message
    raise RuntimeError("PRIVATE_KEY environment variable is not set or empty.")

PRIVATE_KEY = None
try:
    # 1. Handle escaped newlines (the most common cause of failure)
    private_key_str = private_key_str.replace("\\n", "\n")
    logger.info("Attempting to load RSA private key from environment variable.")
    
    # 2. Import the key
    PRIVATE_KEY = RSA.import_key(private_key_str)
    
    # 3. Initialize the RSA Cipher
    RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY)
    
    # --- CRITICAL DEBUG STEP: LOG PUBLIC KEY FOR VALIDATION ---
    public_key_pem = PRIVATE_KEY.publickey().export_key(format='PEM').decode('utf-8')
    logger.info(f"RSA Private Key loaded successfully (Key Size: {PRIVATE_KEY.size_in_bytes() * 8} bits).")
    logger.debug("\n\n--- VALIDATED PUBLIC KEY FROM PRIVATE KEY (MUST MATCH META'S KEY) ---")
    logger.debug(public_key_pem)
    logger.debug("----------------------------------------------------------------------\n")
    

except ValueError as e:
    logger.critical(f"FATAL: Failed to import RSA Private Key. Check formatting (BEGIN/END tags, base64 encoding, and presence of all newlines). Error: {e}")
    # Re-raise the error to stop the application from running with a broken key
    raise RuntimeError(f"Key Import Error: {e}")
except Exception as e:
    logger.critical(f"FATAL: An unexpected error occurred during key setup: {e}")
    raise


# --- WEBHOOK VERIFICATION (GET) ---
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# --- WEBHOOK HANDLER (POST) ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()

        # ---- Encrypted Flow Payload Handling ----
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        is_flow_payload = encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64
        
        logger.info(
            f"Payload flags -> Flow data check: {is_flow_payload}, "
            f"encrypted_flow_data: {encrypted_flow_b64 is not None}, "
            f"encrypted_aes_key: {encrypted_aes_key_b64 is not None}, "
            f"iv: {iv_b64 is not None}"
        )

        if is_flow_payload:
            try:
                # 1️⃣ Decode and decrypt AES key with RSA
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                
                # --- CRUCIAL DEBUG STEP ---
                logger.debug(f"Encrypted AES Key Length: {len(encrypted_aes_key_bytes)} bytes")
                
                # Check if the length matches the RSA key size
                if len(encrypted_aes_key_bytes) != PRIVATE_KEY.size_in_bytes():
                    raise ValueError(
                        f"Ciphertext length mismatch. Expected {PRIVATE_KEY.size_in_bytes()} bytes, "
                        f"got {len(encrypted_aes_key_bytes)} bytes. Check key size and padding."
                    )
                
                # The actual RSA decryption
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)
                logger.info(f"✅ AES key successfully decrypted. Key length: {len(aes_key)} bytes.")

                # 2️⃣ Decode IV and encrypted flow
                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)

                logger.debug(f"IV length: {len(iv)} bytes. Encrypted flow length: {len(encrypted_flow_bytes)} bytes")

                # 3️⃣ Split ciphertext and tag (last 16 bytes are GCM tag)
                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]

                logger.debug(f"Ciphertext length: {len(ciphertext)}, Tag length: {len(tag)}")

                # 4️⃣ Decrypt AES-GCM
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                
                # This step can also fail if the AES key or IV is wrong, or the data is corrupted
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.info(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data, indent=2)}")

                # 5️⃣ Trigger WhatsApp menu processing
                from_number = decrypted_data.get("From")
                user_text = decrypted_data.get("Body")
                if from_number and user_text:
                    # Note: You might want to pass the whole decrypted_data object if other flow fields are needed
                    background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})

                # 6️⃣ Return encrypted response in base64 (optional)
                response = {
                    "screen": "RESPONSE_SCREEN_NAME", # Adjust screen name as needed
                    "data": {"status": "success", "message": "Flow data processed."}
                }

                # Encrypt response using AES-GCM with flipped IV
                flipped_iv = bytes([b ^ 0xFF for b in iv]) # Standard practice for response encryption
                cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(json.dumps(response).encode("utf-8"))
                full_resp = encrypted_resp_bytes + resp_tag
                full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")
                
                logger.info("Encrypted flow response generated successfully.")

                return PlainTextResponse(full_resp_b64)

            except ValueError as e:
                # Catches errors related to RSA Decryption failure, GCM verification failure, or JSON loading
                logger.error(f"⚠️ Security/Decryption Failed: ValueError: {e}")
                # This specific error usually means the private key is wrong or the data was tampered with.
                return PlainTextResponse("Decryption or data verification failed. Check RSA key pair.", status_code=400)
            
            except Exception as e:
                logger.exception(f"General Flow Decryption Error: {e}")
                return PlainTextResponse("Failed to decrypt flow payload due to internal error.", status_code=500)

        # ---- Regular WhatsApp message handling (Unchanged) ----
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return PlainTextResponse("OK")

        # ... (rest of the regular message handling logic)
        
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
        logger.exception(f"Top-level Webhook Error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)