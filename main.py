import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

# --- FLOW DECRYPTION IMPORTS REINSTATED ---
try:
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256 
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad
except ImportError:
    # A helpful message if the user forgot to install pycryptodome
    raise RuntimeError("PyCryptodome is not installed. Please install with: pip install pycryptodome")
# ------------------------------------------

# Assuming these modules exist in the user's project structure
# NOTE: whatsapp_menu must now be able to handle a stringified JSON payload 
# and synchronously return the next Flow response dictionary.
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

# Setup logging
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG) 

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# --- GENERIC FLOW ERROR RESPONSE (Fallback for exceptions/unhandled returns) ---
FLOW_ERROR_RESPONSE = {
    "screen": "ERROR",
    "data": {
        "error_message": "Flow interaction failed: Invalid response from handler."
    }
}
# -------------------------------------------------------------


# --- UTILITY FUNCTION FOR ROBUST KEY LOADING (Reinstated) ---
def load_private_key(key_string: str) -> RSA.RsaKey:
    """Handles various newline escaping issues when loading key from ENV."""
    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    try:
        return RSA.import_key(key_string)
    except ValueError as e:
        logger.warning(f"Initial key import failed: {e}. Attempting clean import...")
        key_lines = [
            line.strip() 
            for line in key_string.split('\n') 
            if line.strip() and not line.strip().startswith(('-----'))
        ]
        
        if not key_string.startswith('-----BEGIN'):
             cleaned_key_string = (
                "-----BEGIN PRIVATE KEY-----\n" + 
                "\n".join(key_lines) + 
                "\n-----END PRIVATE KEY-----"
            )
             return RSA.import_key(cleaned_key_string)
        
        raise # Re-raise if cleaning didn't help

# --- KEY LOADING AND SETUP (Reinstated) ---
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    logger.warning("PRIVATE_KEY environment variable is missing. Flow decryption will fail if attempted.")

PRIVATE_KEY = None
RSA_CIPHER = None
if private_key_str:
    try:
        PRIVATE_KEY = load_private_key(private_key_str)
        # CRITICAL FIX RETAINED: Initialize the RSA Cipher using OAEP with SHA256 hash.
        RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)
        logger.info("RSA Cipher initialized successfully for Flow decryption.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to import RSA Private Key. Error: {e}")
# -----------------------------------------------------------


# --- WEBHOOK VERIFICATION (GET) ---
@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    """Handles Meta's initial webhook verification request."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# --- WEBHOOK HANDLER (POST) ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handles all incoming WhatsApp messages (text, media) and flow encryption/decryption."""
    logger.critical(f"🚀 [INIT] Webhook received POST request from {request.client.host if request.client else 'Unknown Host'}")
    
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body.decode('utf-8'))
        
        # Determine the WhatsApp Business Account ID (wa_id) for API calls
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        wa_id = value.get("metadata", {}).get("phone_number_id")

        # --- FLOW DECRYPTION AND ENCRYPTION HANDSHAKE ---
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        is_flow_payload = encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64

        if is_flow_payload:
            if not RSA_CIPHER:
                 logger.error("Flow payload received but RSA key is not initialized.")
                 # Fall through to the end of the POST handler to return OK (preventing retry loop)
            else:
                try:
                    # 1️⃣ Decode and decrypt AES key with RSA (using PKCS1_OAEP + SHA256)
                    encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                    
                    if len(encrypted_aes_key_bytes) != PRIVATE_KEY.size_in_bytes():
                        raise ValueError("Ciphertext length mismatch with RSA key size.")
                        
                    aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)
                    logger.info("✅ AES key successfully decrypted.")

                    # 2️⃣ Decode IV and encrypted flow
                    iv = base64.b64decode(iv_b64)
                    encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)

                    # 3️⃣ Decrypt AES-GCM (Payload is now available in decrypted_data)
                    ciphertext = encrypted_flow_bytes[:-16]
                    tag = encrypted_flow_bytes[-16:]
                    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                    decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                    decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))
                    
                    logger.info(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data)}")
                    
                    # 5️⃣ Flow Logic: Synchronous call to whatsapp_menu to get the next response object.
                    # Prepare the flow payload for whatsapp_menu (as stringified JSON)
                    flow_message_body = json.dumps(decrypted_data) 

                    # We assume whatsapp_menu is now modified to handle this stringified JSON payload
                    # and return the next UNENCRYPTED Flow screen dictionary SYNCHRONOUSLY.
                    response_obj = whatsapp_menu(
                        from_number, 
                        flow_message_body, 
                        wa_id
                    )
                    
                    if not isinstance(response_obj, dict):
                         # Use fallback if whatsapp_menu returns something unexpected
                         logger.error(f"Flow handler returned unexpected type: {type(response_obj)}")
                         response_obj = FLOW_ERROR_RESPONSE


                    # 6️⃣ Encrypt response using AES-GCM with bit-flipped IV (Meta's requirement)
                    flipped_iv = bytes([b ^ 0xFF for b in iv]) 
                    cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                    # Use the dictionary returned by whatsapp_menu
                    response_json_string = json.dumps(response_obj)
                    encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(response_json_string.encode("utf-8"))
                    full_resp = encrypted_resp_bytes + resp_tag
                    full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")
                    
                    logger.info(f"Encrypted flow response generated for screen: {response_obj.get('screen', 'N/A')}")

                    return PlainTextResponse(full_resp_b64)

                except Exception as e:
                    logger.exception(f"General Flow Decryption/Encryption Error: {e}")
                    # Return 400 for security failures, preventing the flow from continuing
                    return PlainTextResponse("Flow cryptographic failure.", status_code=400)
        # ---------------------------------------------------------------------------------


        # --- REGULAR WHATSAPP MESSAGE HANDLING ---
        messages = value.get("messages", [])

        # If no messages or no Business Account ID (wa_id) are found, return OK.
        if not messages or not wa_id:
            logger.info("Payload contains no messages or no phone_number_id. Returning OK.")
            return PlainTextResponse("OK")

        message = messages[0]
        from_number = message.get("from")
        msg_type = message.get("type")

        if not from_number:
            return PlainTextResponse("OK")

        # --- Handle Text Messages ---
        if msg_type == "text":
            user_text = message.get("text", {}).get("body", "")
            logger.info(f"💬 Message from {from_number}: {user_text}")
            # Delegate to business logic for text response (ASYNCHRONOUS)
            # Pass user_text as a simple string for standard message processing
            background_tasks.add_task(whatsapp_menu, from_number, user_text, wa_id)
            return PlainTextResponse("OK")

        # --- Handle Media Messages (image, document, audio, video) ---
        if msg_type in ["image", "document", "audio", "video"]:
            media_data = message.get(msg_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type")

            if not media_id:
                # If a media message is received but the ID is missing
                background_tasks.add_task(
                    send_meta_whatsapp_message,
                    from_number,
                    "Samahani, faili halikupatikana.",
                    wa_id
                )
                return PlainTextResponse("OK")

            # 1. Notify user immediately (initial response)
            background_tasks.add_task(
                send_meta_whatsapp_message,
                from_number,
                "*Faili limepokelewa.*\n🔄 Linafanyiwa uchambuzi...\nTafadhali subiri.",
                wa_id
            )

            # 2. Process file and send final confirmation in background
            def process_job():
                # Get the media URL from Meta's API using the media ID
                media_url = get_media_url(media_id)
                
                # Process the file using the application's service logic
                process_file_upload(
                    user_id=from_number,
                    user_name="",
                    user_phone=from_number,
                    flow_type="whatsapp_upload",
                    media_url=media_url,
                    mime_type=mime_type
                )
                
                # Send final success message
                send_meta_whatsapp_message(
                    from_number,
                    "✅ *Uchambuzi wa faili umekamilika.*\nAsante kwa kuchagua huduma zetu.",
                    wa_id
                )

            background_tasks.add_task(process_job)
            return PlainTextResponse("OK")

        # --- Handle Unsupported Message Types ---
        background_tasks.add_task(
            send_meta_whatsapp_message,
            from_number,
            f"Samahani, siwezi kusoma ujumbe wa aina: {msg_type}",
            wa_id
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Webhook Error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)