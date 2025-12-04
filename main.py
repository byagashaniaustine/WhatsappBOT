import os
import json
import base64
import logging
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from starlette.responses import JSONResponse 
from typing import Optional 

# Import cryptography libraries
try:
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256 
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad
except ImportError:
    # Ensure this dependency is available
    raise RuntimeError("PyCryptodome is not installed. Please install with: pip install pycryptodome")

# Import WhatsApp handling functions
# NOTE: whatsapp_menu must be updated to accept a dict/json payload.
# NOTE: The Quick Reply sending logic for loan results has been REMOVED from the webhook.
from api.whatsappBOT import whatsapp_menu, calculate_loan_results 
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url, send_manka_menu_template 


# Setup logging
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG) 

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

@app.get("/whatsapp-webhook/")
async def verify_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge, status_code=200)

    return PlainTextResponse("Verification failed", status_code=403)


# --- FLOW SCREEN DEFINITIONS (UNCHANGED) ---
FLOW_DEFINITIONS = {
    "LOAN_FLOW_ID_1": { 
        "MAIN_MENU": {"screen": "MAIN_MENU", "data": {}},
        "LOAN_CALCULATOR": {"screen": "LOAN_CALCULATOR", "data": {}}, 
        "LOAN_RESULT": {"screen": "LOAN_RESULT", "data": {}}, 
        "CREDIT_SCORE": {"screen": "CREDIT_SCORE", "data": {}},
        "LOAN_TYPES": {"screen": "LOAN_TYPES", "data": {}},
        "SERVICES": {"screen": "SERVICES", "data": {}}, 
        "AFFORDABILITY_CHECK": {"screen": "AFFORDABILITY_WELCOME", "data": {}},
        "DOCUMENT_REQUEST": {"screen": "DOCUMENT_REQUEST", "data": {}},
        "SUCCESS_ACTION": "SUBMIT_LOAN",
        "SUCCESS_RESPONSE": {
            "screen": "SUCCESS",
            "data": {
                "extension_message_response": {
                    "params": {
                        "flow_token": "RETURNED_FLOW_TOKEN", 
                        "loan_summary": "Your loan has been processed."
                    }
                }
            }
        },
    },
    "ACCOUNT_FLOW_ID_2": {
        "PROFILE": {"screen": "PROFILE_UPDATE", "data": {"name": "John Doe", "email": "john.doe@example.com"}},
        "SUMMARY": {"screen": "SUMMARY_SCREEN", "data": {}},
        "SUCCESS_ACTION": "SAVE_PROFILE",
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
    "HEALTH_CHECK_PING": {"screen": "HEALTH_CHECK_OK", "data": {"status": "active"}},
    "ERROR": {"screen": "ERROR", "data": {"error_message": "An unknown action occurred."}}
}

# --- KEY LOADING AND UTILITIES (UNCHANGED) ---
def load_private_key(key_string: str) -> RSA.RsaKey:
    """Handles various newline escaping issues when loading key from ENV."""
    if key_string:
        logger.critical(f"🔑 Private Key ENV length: {len(key_string)} characters.")

    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    try:
        key = RSA.import_key(key_string)
        logger.critical(f"✅ Key imported successfully. Bit length: {key.n.bit_length()} bits.")
        return key
    except ValueError as e:
        logger.critical(f"⚠️ Initial key import failed: {e}. Attempting clean import...")
        key_lines = [line.strip() for line in key_string.split('\n') if line.strip() and not line.strip().startswith(('-----'))]
        
        if not key_string.startswith('-----BEGIN'):
             cleaned_key_string = ("-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----")
             key = RSA.import_key(cleaned_key_string)
             logger.critical(f"✅ Key cleaned and imported. Bit length: {key.n.bit_length()} bits.")
             return key
        
        raise 

private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
    logger.critical("❌ FATAL: PRIVATE_KEY environment variable is NOT set.")
    raise RuntimeError("PRIVATE_KEY environment variable is not set or empty.")

PRIVATE_KEY = None
RSA_CIPHER = None
try:
    logger.critical("🔑 Attempting to load RSA private key from environment variable.")
    PRIVATE_KEY = load_private_key(private_key_str)
    RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)
    logger.critical("✅ RSA Cipher initialized with PKCS1_OAEP and SHA256 hashAlgo.")
    
except Exception as e:
    logger.critical(f"FATAL: Failed to import RSA Private Key: {e}")
    raise

# ----------------------------------------------------------------------
## 🚀 WEBHOOK HANDLER (POST) - All Flow Routing and Message Handling
# ----------------------------------------------------------------------

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.critical(f"🚀 [INIT] Webhook received POST request.")
    
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body.decode('utf-8'))
        logger.critical("JSON Parsed Successfully.")

        # --- Extract Metadata ---
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        
        # Determine if it's a Flow payload
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")
        is_flow_payload = encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64
        
        # Safely extract primary_from_number from standard locations in the webhook payload
        primary_from_number: Optional[str] = None
        
        if messages and messages[0].get("from"):
            primary_from_number = messages[0].get("from")
        elif contacts and contacts[0].get("wa_id"):
            primary_from_number = contacts[0].get("wa_id")

        if primary_from_number and not primary_from_number.startswith("+"):
            primary_from_number = "+" + primary_from_number
        logger.critical(f"📞 Initial Phone Number Detected: {primary_from_number}")

        # ========================================================================
        # ENCRYPTED FLOW PAYLOAD PROCESSING
        # ========================================================================
        if is_flow_payload:
            # ... (Decryption logic remains UNCHANGED) ...
            try:
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                logger.critical(f"🔑 Decrypting AES key size: {len(encrypted_aes_key_bytes)} bytes.")
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)
                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)
                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.critical(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data, indent=2)}")

                action = decrypted_data.get("action")
                flow_token = decrypted_data.get("flow_token")
                user_data = decrypted_data.get("data", {})
                current_screen = decrypted_data.get("screen", "UNKNOWN")
                flow_id_key = user_data.get("flow_id", "LOAN_FLOW_ID_1") 
                current_flow_screens = FLOW_DEFINITIONS.get(flow_id_key)
                response_obj = None
                
                best_phone = primary_from_number if primary_from_number else user_data.get("from_number")
                if best_phone:
                    user_data["from_number"] = best_phone
                    primary_from_number = best_phone
                
                # 1. PING RESPONSE (UNCHANGED)
                if action == "ping":
                    response_obj = FLOW_DEFINITIONS["HEALTH_CHECK_PING"]
                
                # 2. SUCCESS ACTION (FINAL MESSAGE SEND)
                elif current_flow_screens and action == current_flow_screens.get("SUCCESS_ACTION"):
                    
                    response_obj = json.loads(json.dumps(current_flow_screens["SUCCESS_RESPONSE"])) 
                    if flow_token:
                        success_params = response_obj["data"]["extension_message_response"]["params"]
                        success_params["flow_token"] = flow_token
                        logger.critical(f"Flow {flow_id_key} finalized.")
                    
                    # ⭐ LOAN FLOW FINALIZATION: REMOVE QUICK REPLY MESSAGE SENDING
                    if flow_id_key == "LOAN_FLOW_ID_1":
                        logger.critical("🛑 LOAN FLOW SUCCESS: Not sending Quick Reply. Results remain in Flow UI.")
                        
                    # NOTE: You can add logic here if you want to send a *simple* completion message:
                    # if primary_from_number:
                    #     background_tasks.add_task(send_meta_whatsapp_message, primary_from_number, "Asante kwa kutumia kikokotoo cha mkopo!")


                # 3. INIT ACTION (UNCHANGED)
                elif action == "INIT":
                    if flow_id_key == "LOAN_FLOW_ID_1":
                        response_obj = {"screen": "MAIN_MENU", "data": user_data} 
                    elif flow_id_key == "ACCOUNT_FLOW_ID_2":
                        response_obj = current_flow_screens["PROFILE"]
                        response_obj["data"].update(user_data) 
                    else:
                        response_obj = FLOW_DEFINITIONS["ERROR"]
                
                # 4. DATA EXCHANGE ACTION (UNCHANGED)
                elif action == "data_exchange":
                    
                    if user_data.get("error"):
                        response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Hitilafu imetokea. Tunaanza tena."}}
                    
                    elif flow_id_key == "LOAN_FLOW_ID_1":
                        next_screen_key = user_data.get("next_screen")
                        
                        if next_screen_key and next_screen_key in FLOW_DEFINITIONS[flow_id_key]:
                            
                            if next_screen_key == "LOAN_RESULT" and current_screen == "LOAN_CALCULATOR":
                                # Calculate and get Flow UI response (sync)
                                try:
                                    response_obj = calculate_loan_results(user_data)
                                except (ValueError, Exception) as e:
                                    logger.error(f"❌ Invalid loan parameters or calculation error: {e}")
                                    response_obj = {"screen": "LOAN_CALCULATOR", "data": {"error_message": "Tafadhali jaza nambari sahihi."}}
                            
                            else:
                                response_obj = {"screen": next_screen_key, "data": user_data}
                        
                        elif current_screen == "MAIN_MENU":
                            next_screen_id = user_data.get("selected_service")
                            valid_screens = ["CREDIT_SCORE", "CREDIT_BANDWIDTH", "LOAN_CALCULATOR", "LOAN_TYPES", "SERVICES", "AFFORDABILITY_CHECK"]
                            
                            if next_screen_id in valid_screens:
                                response_obj = {"screen": next_screen_id, "data": user_data}
                            else:
                                response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Chaguo batili."}}
                        
                        else:
                            response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Kosa: Sehemu ya huduma haikupatikana."}}
                            
                    elif flow_id_key == "ACCOUNT_FLOW_ID_2":
                        if current_screen == "PROFILE_UPDATE":
                            response_obj = json.loads(json.dumps(current_flow_screens["SUMMARY"]))
                            response_obj["data"].update(user_data)
                        else:
                            response_obj = FLOW_DEFINITIONS["ERROR"] 
                        
                    else:
                        response_obj = FLOW_DEFINITIONS["ERROR"]

                else:
                    response_obj = {"screen": current_screen, "data": {"error_message": f"Action '{action}' not handled."}}

                # --- Encrypt and return response (UNCHANGED) ---
                if response_obj is not None:
                    flipped_iv = bytes([b ^ 0xFF for b in iv]) 
                    cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                    response_json_string = json.dumps(response_obj)
                    encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(response_json_string.encode("utf-8"))
                    full_resp = encrypted_resp_bytes + resp_tag
                    full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")
                    
                    next_screen_name = response_obj.get('screen', 'STATUS_CHECK')
                    logger.critical(f"✅ Encrypted flow response generated. Next Screen: {next_screen_name}")
                    return PlainTextResponse(full_resp_b64)
                
                return PlainTextResponse("Flow action processed, but no response object generated.", status_code=200)

            except Exception as e:
                if "Incorrect decryption" in str(e):
                    logger.critical("🚨 Decryption Failure (Incorrect decryption.): Key mismatch.")
                else:
                    logger.critical(f"General Flow Processing/Security Error: {e}", exc_info=True)
                
                return PlainTextResponse("Failed to process flow payload due to internal error.", status_code=500)

        # ========================================================================
        # REGULAR WHATSAPP MESSAGE HANDLING (Text and Media) (REFRACTORED)
        # ========================================================================
        
        if messages:
            message = messages[0]
            from_number = message.get("from")
            message_type = message.get("type")
            
            if from_number and not from_number.startswith("+"):
                from_number = "+" + from_number
            
            user_name = next((contact.get("profile", {}).get("name") for contact in contacts if contact.get("wa_id") == from_number.lstrip("+")), from_number)
            
            if not from_number:
                 logger.error("❌ Could not determine 'from_number' for regular message.")
                 return PlainTextResponse("OK (No Sender)", status_code=200)

            # Handle TEXT messages (MODIFIED: Pass full message payload as dict)
            if message_type == "text":
                # Create the simplified payload dictionary
                text_payload = {
                    "from_number": from_number,
                    "user_name": user_name,
                    "body": message.get("text", {}).get("body", "") # The message text
                }
                
                logger.critical(f"💬 Message from {from_number} ({user_name}): {text_payload['body']}")
                
                # --- START OF FIX: Reroute to whatsapp_menu with the text payload dict ---
                background_tasks.add_task(
                    whatsapp_menu,
                    text_payload # Pass the dictionary as the *first* argument (or ensure function accepts a dict)
                )
                logger.critical(f"✅ Text message '{text_payload['body']}' routed to whatsapp_menu for {from_number}.")
                # --- END OF FIX ---
            
            # Handle MEDIA messages (unchanged)
            elif message_type in ["image", "document", "video", "audio"]:
                media_object = message.get(message_type, {})
                media_id = media_object.get("id")
                mime_type = media_object.get("mime_type")
                file_name = media_object.get("filename", f"file.{mime_type.split('/')[-1] if '/' in mime_type else 'dat'}")

                if media_id:
                    logger.critical(f"📎 Media message detected: {message_type}, ID: {media_id}")
                    try:
                        media_url = get_media_url(media_id)
                        await send_meta_whatsapp_message(from_number, "✅ Tumepokea faili lako. Tafadhali subiri uchambuzi wa kwanza...")
                        
                        background_tasks.add_task(
                                process_file_upload,
                                user_id=from_number,
                                user_name=user_name,
                                user_phone=from_number,
                                flow_type="REGULAR_MEDIA",
                                media_url=media_url,
                                mime_type=mime_type,
                               file_name=file_name
                        )
                        logger.critical(f"✅ Media processing task queued for {from_number}")

                    except Exception as e:
                        logger.error(f"❌ Error handling media ID {media_id}: {e}", exc_info=True)
                        await send_meta_whatsapp_message(from_number, "Samahani, kuna hitilafu imetokea wakati tukipakia faili lako.")

            
            # Handle INTERACTIVE messages (unchanged)
            elif message_type == "interactive":
                logger.critical(f"💬 Received Interactive message from {from_number}")
                
            else:
                logger.critical(f"Received unhandled message type: {message_type} from {from_number}")
                
        return PlainTextResponse("OK")

    except Exception as e:
        logger.critical(f"Webhook Error: {e}", exc_info=True)
        return PlainTextResponse("Internal Server Error", status_code=500)