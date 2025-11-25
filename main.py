import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

# Import cryptography libraries
try:
    from Crypto.PublicKey import RSA
    # Import relevant Hash algorithm explicitly
    from Crypto.Hash import SHA256 
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad
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

# --- FLOW SCREEN DEFINITIONS ---
# Define screens for different flows, using dictionary keys to separate them.
FLOW_DEFINITIONS = {
    # --- FLOW 1: LOAN APPLICATION ---
    "LOAN_FLOW_ID_1": { # Use the actual Flow ID from Meta's setup here
        "LOAN": {
            "screen": "LOAN",
            "data": {}
        },
        "CONFIRM": {
            "screen": "CONFIRM",
            "data": {
                "loan_amount": "50000",
                "loan_duration": "30",
                "interest_rate_type": "day",
                "interest_rate_percent": "5"
            }
        },
        "SUCCESS_ACTION": "SUBMIT_LOAN", # Action name defined in Flow JSON
        "SUCCESS_RESPONSE": {
            "screen": "SUCCESS",
            "data": {
                "extension_message_response": {
                    "params": {
                        "flow_token": "REPLACE_FLOW_TOKEN", 
                        "loan_summary": "Your loan has been processed."
                    }
                }
            }
        },
    },
    # --- FLOW 2: ACCOUNT UPDATE EXAMPLE ---
    "ACCOUNT_FLOW_ID_2": { # Use the actual Flow ID for the second app
        "PROFILE": {
            "screen": "PROFILE_UPDATE",
            "data": {"name": "John Doe", "email": "john.doe@example.com"}
        },
        "SUMMARY": {
            "screen": "SUMMARY_SCREEN",
            "data": {}
        },
        "SUCCESS_ACTION": "SAVE_PROFILE", # Action name for successful exit
        "SUCCESS_RESPONSE": {
            "screen": "ACCOUNT_SAVED",
            "data": {
                "extension_message_response": {
                    "params": {
                        "flow_token": "REPLACE_FLOW_TOKEN", 
                        "update_message": "Account profile updated successfully!"
                    }
                }
            },
        }
    },
    # --- COMMON RESPONSES ---
    "HEALTH_CHECK_PING": {
        "screen": "HEALTH_CHECK_OK",
        "data": {"status": "active"}
    },
    "ERROR": {
        "screen": "ERROR",
        "data": {"error_message": "An unknown action occurred."}
    }
}
# ---------------------------------------------------

# --- UTILITY FUNCTION FOR ROBUST KEY LOADING ---
def load_private_key(key_string: str) -> RSA.RsaKey:
    """Handles various newline escaping issues when loading key from ENV."""
    # Attempt to handle common escape sequences for newlines
    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    try:
        # Standard import
        return RSA.import_key(key_string)
    except ValueError as e:
        # If standard import fails, try stripping common whitespace/noise
        logger.warning(f"Initial key import failed: {e}. Attempting clean import...")
        key_lines = [
            line.strip() 
            for line in key_string.split('\n') 
            if line.strip() and not line.strip().startswith(('-----'))
        ]
        
        # If the key is just raw base64 without headers, Crypto.PublicKey handles it if the format is specified,
        # but since we expect PEM, let's re-add headers if they were stripped accidentally.
        if not key_string.startswith('-----BEGIN'):
             cleaned_key_string = (
                "-----BEGIN PRIVATE KEY-----\n" + 
                "\n".join(key_lines) + 
                "\n-----END PRIVATE KEY-----"
            )
             return RSA.import_key(cleaned_key_string)
        
        raise # Re-raise if cleaning didn't help

# --- KEY LOADING AND SETUP ---
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    raise RuntimeError("PRIVATE_KEY environment variable is not set or empty.")

PRIVATE_KEY = None
RSA_CIPHER = None
try:
    logger.info("Attempting to load RSA private key from environment variable.")
    
    # 1. Use the robust loader
    PRIVATE_KEY = load_private_key(private_key_str)
    
    # 2. Initialize the RSA Cipher using OAEP with SHA256 hash.
    # We must only use 'hashAlgo=SHA256' to align with Meta's requirements.
    RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)
    
    logger.info("RSA Cipher initialized with PKCS1_OAEP and SHA256 hashAlgo.")
    
    # --- CRITICAL DEBUG STEP: LOG PUBLIC KEY FOR VALIDATION ---
    public_key_pem = PRIVATE_KEY.publickey().export_key(format='PEM').decode('utf-8')
    logger.info(f"RSA Private Key loaded successfully (Key Size: {PRIVATE_KEY.size_in_bytes() * 8} bits).")
    logger.debug("\n\n--- VALIDATED PUBLIC KEY FROM PRIVATE KEY (MUST MATCH META'S KEY) ---")
    logger.debug(public_key_pem)
    logger.debug("----------------------------------------------------------------------\n")
    
    # Verify the match manually based on the keys you provided
    provided_public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtFvfYSl7PleeHgBioPxz
OoQ5ClaDysJwTf2l7EF8tG+jSq9oeE16MIfHWF3+xH3x4vKtXsRP7FqgBQjBOXao
z7Gb53lt6Fm2bpH/ABYaYcawEjGZCE5KBVybl30SDJVTp3LC52Yql2VcO88q54SE
8ATc5+5Zg1vZwFac6aMq2Ej/9EmzbS0Bc3QAB4iF7zx/bVwZStM2vqRpR6NDyF4S
9VhuSid3m4pVfFFoUMYrIpOCI2ISkRAq7y7WUAq9b63zG+Eej6hnbLnEA6veoQ7u
eeOqPHwkl2tkBMTaYvrGk6bI3+L0XY4aDVyA9syFdpJ/cbv4cn3FAQbM7B+sN1kU
swIDAQAB
-----END PUBLIC KEY-----"""
    
    # Simple, non-cryptographic string comparison (ignoring whitespace for robustness)
    if "".join(public_key_pem.split()) != "".join(provided_public_key.split()):
        logger.critical("🚨 KEY MISMATCH DETECTED DURING SELF-CHECK! The Public Key generated from the loaded Private Key does NOT match the Public Key provided in the chat. You MUST ensure the key registered with Meta matches the one generated from your loaded Private Key.")
        # Do not raise an error here, but warn strongly, as the runtime environment might be correct even if the chat history was wrong.

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


# --- DEBUG / HEALTH CHECK ENDPOINT ---
@app.post("/debug-test/")
async def debug_test(request: Request):
    """A minimal endpoint to confirm the server is receiving and logging requests."""
    logger.critical(f"✅ [DEBUG] Successfully hit the /debug-test/ endpoint from {request.client.host if request.client else 'Unknown Host'}")
    raw_body = await request.body()
    logger.debug(f"[DEBUG] Raw Body Length: {len(raw_body)} bytes.")
    return PlainTextResponse("Debug check successful. Check logs for CRITICAL messages.", status_code=200)

# ... keep all your imports, logging setup, key loading, FLOW_DEFINITIONS, etc. as you have above ...

# --- WEBHOOK HANDLER (POST) ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.critical(f"🚀 [INIT] Webhook received POST request from {request.client.host if request.client else 'Unknown Host'}")
    
    try:
        raw_body = await request.body()
        body_log = raw_body.decode('utf-8', errors='ignore')
        if len(body_log) > 500:
            body_log = body_log[:500] + "..."
        logger.debug(f"Incoming RAW Body (Truncated): {body_log}")

        payload = json.loads(raw_body.decode('utf-8'))
        logger.info("Successfully parsed payload as JSON. Proceeding to processing.")

        # -------------------------------
        # Check for Encrypted Flow Payload
        # -------------------------------
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")
        is_flow_payload = encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64

        if is_flow_payload:
            try:
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)

                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)
                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]

                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.info(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data, indent=2)}")

                # -------------------------------
                # Pass payload to whatsapp_menu
                # -------------------------------
                from_number = decrypted_data.get("from_number")
                if from_number:
                    background_tasks.add_task(
                        whatsapp_menu,
                        {
                            "From": from_number,
                            "flow": True,
                            "payload": decrypted_data
                        }
                    )
                    logger.info(f"📤 Flow payload sent to whatsapp_menu for {from_number}")

                # Optionally respond immediately to Meta server with 200 OK
                return PlainTextResponse("OK")

            except Exception as e:
                logger.exception(f"⚠️ Flow Decryption Error: {e}")
                return PlainTextResponse("Failed to decrypt flow payload.", status_code=500)

        # ---- Regular WhatsApp message handling (text/media) ----
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
            logger.info(f"💬 Message from {from_number}: {user_text}")
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

        # -------------------------------
        # Unknown message type
        # -------------------------------
        background_tasks.add_task(
            send_meta_whatsapp_message,
            from_number,
            f"Samahani, siwezi kusoma ujumbe wa aina: {msg_type}"
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Webhook Error: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)
