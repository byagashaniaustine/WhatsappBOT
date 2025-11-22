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

# --- FLOW SCREEN DEFINITIONS (AS PROVIDED BY USER) ---
# NOTE: Changed 'const' to standard Python assignment.
# To navigate to a screen, return the corresponding response from the endpoint.
SCREEN_RESPONSES = {
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
    # Special response for the encrypted 'ping' health check action
    "HEALTH_CHECK_PING": {
        "screen": "HEALTH_CHECK_OK", # Placeholder screen name
        "data": {
            "status": "active" # The status Meta expects for this test
        }
    },
    "SUCCESS": {
        "screen": "SUCCESS",
        "data": {
            # Meta requires the flow_token back in the extension_message_response 
            # when transitioning to a non-flow screen (i.e., sending a message).
            "extension_message_response": {
                "params": {
                    # This token MUST be dynamically replaced with the one from the incoming payload
                    "flow_token": "REPLACE_FLOW_TOKEN", 
                    "some_param_name": "PASS_CUSTOM_VALUE"
                }
            }
        }
    },
    # Add a simple error screen fallback
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


# --- WEBHOOK HANDLER (POST) ---
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    # This CRITICAL log is our last defense against total silence.
    logger.critical(f"🚀 [INIT] Webhook received POST request from {request.client.host if request.client else 'Unknown Host'}")
    
    try:
        # 1. Read the raw body first
        raw_body = await request.body()
        
        # Log the raw body, truncated if necessary
        body_log = raw_body.decode('utf-8', errors='ignore') # Ignore decoding errors
        if len(body_log) > 500:
            body_log = body_log[:500] + "..."
        logger.debug(f"Incoming RAW Body (Truncated): {body_log}")

        # 2. Attempt to parse as JSON. This is often the point of failure if Content-Type is wrong.
        payload = json.loads(raw_body.decode('utf-8'))
        
        # Log parsed payload if successful
        logger.info("Successfully parsed payload as JSON. Proceeding to processing.")

        # ---- Encrypted Flow Payload Handling (Health Check & Data Exchange) ----
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
                # --- CRUCIAL DEBUG STEP: Log the incoming base64 strings ---
                logger.debug(f"Incoming Encrypted AES Key (b64): {encrypted_aes_key_b64[:30]}...")
                logger.debug(f"Incoming Initial Vector (b64): {iv_b64}")
                # -----------------------------------------------------------------

                # 1️⃣ Decode and decrypt AES key with RSA
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                
                # --- CRUCIAL DEBUG STEP ---
                logger.debug(f"Encrypted AES Key Length: {len(encrypted_aes_key_bytes)} bytes")
                
                # Check if the length matches the RSA key size (e.g., 256 bytes for 2048-bit key)
                if len(encrypted_aes_key_bytes) != PRIVATE_KEY.size_in_bytes():
                    raise ValueError(
                        f"Ciphertext length mismatch. Expected {PRIVATE_KEY.size_in_bytes()} bytes, "
                        f"got {len(encrypted_aes_key_bytes)} bytes. Check key size and padding."
                    )
                
                # The actual RSA decryption. This step now uses SHA256.
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

                # 5️⃣ Determine action for response (Crucial for Health Check)
                action = decrypted_data.get("action")
                flow_token = decrypted_data.get("flow_token")
                
                # --- Flow Logic: Select the correct response based on action ---
                if action == "INIT":
                    # Health Check / Initial Launch: Should return the first screen, LOAN.
                    response_obj = SCREEN_RESPONSES["LOAN"]
                elif action == "ping":
                    # FIX: Handle the specific encrypted 'ping' action for the health check endpoint
                    response_obj = SCREEN_RESPONSES["HEALTH_CHECK_PING"]
                elif action == "data_exchange":
                    # For a data exchange, we usually inspect the data to decide where to navigate.
                    response_obj = SCREEN_RESPONSES["CONFIRM"]
                elif action == "SUCCESS_ACTION_NAME_FROM_FLOW_BUTTON":
                    # Example: A final 'Submit' action that moves out of the Flow.
                    # We must pass the flow_token back to Meta in the response data.
                    response_obj = json.loads(json.dumps(SCREEN_RESPONSES["SUCCESS"])) # Deep copy
                    
                    if flow_token:
                        # Replace the placeholder with the actual flow token
                        response_obj["data"]["extension_message_response"]["params"]["flow_token"] = flow_token
                    else:
                        logger.warning("Flow token missing in SUCCESS action payload!")

                else:
                    # Default fallback: return the original screen name but with an error message
                    current_screen = decrypted_data.get("screen", "ERROR")
                    response_obj = SCREEN_RESPONSES["ERROR"]
                    response_obj["screen"] = current_screen
                    response_obj["data"]["error_message"] = f"Action '{action}' not handled."
                
                # Final response object to be encrypted
                response = response_obj
                # -----------------------------------------------------------------

                # 6️⃣ Return encrypted response in base64 (MANDATORY for Flow)
                
                # Encrypt response using AES-GCM with flipped IV
                flipped_iv = bytes([b ^ 0xFF for b in iv]) # Standard practice for response encryption
                cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                
                # Ensure the response is a JSON string before encoding
                response_json_string = json.dumps(response)
                
                encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(response_json_string.encode("utf-8"))
                full_resp = encrypted_resp_bytes + resp_tag
                full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")
                
                logger.info(f"Encrypted flow response generated successfully and returning 200 OK. Next Screen: {response['screen']}")

                # This successful, encrypted response is what Meta needs for the health check!
                return PlainTextResponse(full_resp_b64)

            except ValueError as e:
                # Catches errors related to RSA Decryption failure (Incorrect decryption), GCM verification failure (MAC check failed), or JSON loading
                logger.error(f"⚠️ Security/Decryption Failed: ValueError: {e}")
                # Returning 400 will cause the Meta Health Check to fail.
                return PlainTextResponse("Decryption or data verification failed. Check RSA key pair.", status_code=400)
            
            except Exception as e:
                logger.exception(f"General Flow Decryption Error: {e}")
                # Returning 500 will cause the Meta Health Check to fail.
                return PlainTextResponse("Failed to decrypt flow payload due to internal error.", status_code=500)

        # ---- Regular WhatsApp message handling (Unchanged, non-Flow) ----
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

        # ... (other message type handling)

        return PlainTextResponse("OK") # Default OK for non-flow webhook

    except Exception as e:
        # CATCH-ALL for errors happening early (like request.body() or json.loads)
        logger.critical(f"🛑 [FATAL] Critical Webhook Processing Crash (Likely JSON/Body Read Error): {e}")
        # Returning 500 will make the Meta Health Check fail immediately.
        return PlainTextResponse("Internal Server Error during payload processing.", status_code=500)