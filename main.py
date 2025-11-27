import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from starlette.responses import JSONResponse # Ensure JSONResponse is imported for consistency

# Import cryptography libraries
try:
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256 
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad
except ImportError:
    raise RuntimeError("PyCryptodome is not installed. Please install with: pip install pycryptodome")

# --- Import only necessary functions from whatsappBOT ---
# whatsapp_menu for text messages, calculate_loan_results for Flow calculation
from api.whatsappBOT import whatsapp_menu, calculate_loan_results 
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url # Ensure get_media_url is imported

# Setup logging
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG) 

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# --- FLOW SCREEN DEFINITIONS (UNCHANGED from last successful flow update) ---
FLOW_DEFINITIONS = {
    "LOAN_FLOW_ID_1": { 
        # Screen used for INIT and general routing
        "MAIN_MENU": {"screen": "MAIN_MENU", "data": {}},
        
        # Screen used for the primary input form
        "LOAN_CALCULATOR": {"screen": "LOAN_CALCULATOR", "data": {}}, 
        
        # Screen used to display calculated results (LOAN_RESULT has no input data to define)
        "LOAN_RESULT": {"screen": "LOAN_RESULT", "data": {}}, 
        
        # Placeholder screens for other menu options (if needed)
        "CREDIT_SCORE": {"screen": "CREDIT_SCORE", "data": {}},
        "LOAN_TYPES": {"screen": "LOAN_TYPES", "data": {}},
        "SERVICES": {"screen": "SERVICES", "data": {}}, 
        
        # --- NEW AFFORDABILITY SCREENS ---
        "AFFORDABILITY_CHECK": {"screen": "AFFORDABILITY_WELCOME", "data": {}},
        "DOCUMENT_REQUEST": {"screen": "DOCUMENT_REQUEST", "data": {}},
        # --------------------------------
        
        # The SUCCESS action and response can remain, assuming SUBMIT_LOAN is the final action.
        "SUCCESS_ACTION": "SUBMIT_LOAN",
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
# ---------------------------------------------------

# --- UTILITY FUNCTION FOR ROBUST KEY LOADING (UNCHANGED) ---
def load_private_key(key_string: str) -> RSA.RsaKey:
    """Handles various newline escaping issues when loading key from ENV."""
    key_string = key_string.replace("\\n", "\n").replace("\r\n", "\n")
    try:
        return RSA.import_key(key_string)
    except ValueError as e:
        logger.critical(f"⚠️ Initial key import failed: {e}. Attempting clean import...")
        key_lines = [line.strip() for line in key_string.split('\n') if line.strip() and not line.strip().startswith(('-----'))]
        
        if not key_string.startswith('-----BEGIN'):
             cleaned_key_string = ("-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----")
             return RSA.import_key(cleaned_key_string)
        
        raise 

# --- KEY LOADING AND SETUP (UNCHANGED) ---
private_key_str = os.environ.get("PRIVATE_KEY")
if not private_key_str:
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


# --- DEBUG / HEALTH CHECK ENDPOINT (UNCHANGED) ---
@app.post("/debug-test/")
async def debug_test(request: Request):
    logger.critical(f"✅ [DEBUG] Successfully hit the /debug-test/ endpoint from {request.client.host if request.client else 'Unknown Host'}")
    raw_body = await request.body()
    logger.debug(f"[DEBUG] Raw Body Length: {len(raw_body)} bytes.")
    return PlainTextResponse("Debug check successful. Check logs for CRITICAL messages.", status_code=200)


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

        # ---- Encrypted Flow Payload Handling (UNCHANGED) ----
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        is_flow_payload = encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64

        if is_flow_payload:
            try:
                # ... [Decryption Logic Remains] ...
                encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key_b64)
                aes_key = RSA_CIPHER.decrypt(encrypted_aes_key_bytes)
                iv = base64.b64decode(iv_b64)
                encrypted_flow_bytes = base64.b64decode(encrypted_flow_b64)
                ciphertext = encrypted_flow_bytes[:-16]
                tag = encrypted_flow_bytes[-16:]
                cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher_aes.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes.decode("utf-8"))

                logger.critical(f"📥 Decrypted Flow Data: {json.dumps(decrypted_data, indent=2)}")

                # --- START FLOW ROUTING LOGIC ---
                action = decrypted_data.get("action")
                flow_token = decrypted_data.get("flow_token")
                user_data = decrypted_data.get("data", {})
                current_screen = decrypted_data.get("screen", "UNKNOWN")
                flow_id_key = user_data.get("flow_id", "LOAN_FLOW_ID_1") 
                current_flow_screens = FLOW_DEFINITIONS.get(flow_id_key)
                response_obj = None

                # 1. RESTORED PING RESPONSE (As requested)
                if action == "ping":
                    response_obj = FLOW_DEFINITIONS["HEALTH_CHECK_PING"]
                    logger.critical("✅ [PING] Responded with original HEALTH_CHECK_PING definition.")
                
                elif current_flow_screens and action == current_flow_screens.get("SUCCESS_ACTION"):
                    # Success/Final action (e.g., SUBMIT_LOAN or SAVE_PROFILE)
                    response_obj = json.loads(json.dumps(current_flow_screens["SUCCESS_RESPONSE"])) 
                    if flow_token:
                        success_params = response_obj["data"]["extension_message_response"]["params"]
                        success_params["flow_token"] = flow_token
                        logger.critical(f"Flow {flow_id_key} finalized.")

                elif action == "INIT":
                    # Initial request from the user to start the flow
                    if flow_id_key == "LOAN_FLOW_ID_1":
                        response_obj = {"screen": "MAIN_MENU", "data": {}}
                    elif flow_id_key == "ACCOUNT_FLOW_ID_2":
                        response_obj = current_flow_screens["PROFILE"]
                    else:
                        response_obj = FLOW_DEFINITIONS["ERROR"]
                
                elif action == "data_exchange":
                    
                    # 1. Check for immediate error report from client
                    if user_data.get("error"):
                        logger.critical("⚠️ Received Flow Error Report. Returning to MAIN_MENU.")
                        response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Hitilafu imetokea. Tunaanza tena."}}
                    
                    # 2. LOAN FLOW ROUTING (LOAN_FLOW_ID_1)
                    elif flow_id_key == "LOAN_FLOW_ID_1":
                        
                        next_screen_key = user_data.get("next_screen")
                        
                        # --- START REFACTORED NEXT_SCREEN/CALCULATOR LOGIC ---
                        if next_screen_key and next_screen_key in FLOW_DEFINITIONS[flow_id_key]:
                            
                            # A. Handle LOAN_CALCULATOR -> LOAN_RESULT transition
                            if next_screen_key == "LOAN_RESULT" and current_screen == "LOAN_CALCULATOR":
                                logger.critical("🎯 Calculating Loan Results before routing to LOAN_RESULT.")
                                try:
                                    # Call the dedicated function, which returns the LOAN_RESULT payload
                                    response_obj = calculate_loan_results(user_data)
                                    background_tasks.add_task(whatsapp_menu, user_data, user_data)  # Call whatsapp_menu to send the WhatsApp message
                                    logger.critical(f"{response_obj}✅ Loan calculation delegated and successful.")
                                    # --- START MODIFIED LOGGING HERE ---
                                    if response_obj and response_obj.get("data"):
                                      data = response_obj["data"]
                                    logger.critical(f"📊 [CALC RESULT LOG] Monthly: {data.get('monthly_payment')} | Total Interest: {data.get('total_interest')}")
                                # --- END MODIFIED LOGGING HERE ---
                                except ValueError:
                                    response_obj = {"screen": "LOAN_CALCULATOR", "data": {"error_message": "Tafadhali jaza nambari sahihi."}}
                                except Exception:
                                    response_obj = FLOW_DEFINITIONS["ERROR"]
                            
                            # B. Handle simple screen navigation (e.g., AFFORDABILITY_WELCOME -> DOCUMENT_REQUEST)
                            else:
                                response_obj = {"screen": next_screen_key, "data": {}}
                                logger.critical(f"Navigating via next_screen key to: {next_screen_key}")
                        # --- END REFACTORED NEXT_SCREEN/CALCULATOR LOGIC ---
                        
                        
                        elif current_screen == "MAIN_MENU":
                            # Route based on service selection
                            next_screen_id = user_data.get("selected_service")
                            
                            # 🎯 LOG RAW SELECTION and APPLY WORKAROUND
                            logger.critical(f"👀 MAIN_MENU Raw Selection: {next_screen_id}") 
                            
                            UNRESOLVED_TOKEN = "${form.menu_selection}"
                            
                            if next_screen_id == UNRESOLVED_TOKEN:
                                next_screen_id = "LOAN_CALCULATOR" 
                                logger.critical("⚠️ WORKAROUND ACTIVATED: Unresolved token detected. Forcing route to LOAN_CALCULATOR.")

                            valid_screens = ["CREDIT_SCORE", "CREDIT_BANDWIDTH", "LOAN_CALCULATOR", "LOAN_TYPES", "SERVICES", "AFFORDABILITY_CHECK"]
                            
                            if next_screen_id in valid_screens:
                                response_obj = {"screen": next_screen_id, "data": {}}
                            else:
                                response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Chaguo batili."}}
                        
                        else:
                            # Fallback for unhandled LOAN_FLOW_ID_1 screens
                            response_obj = {"screen": "MAIN_MENU", "data": {"error_message": "Kosa: Sehemu ya huduma haikupatikana."}}
                            
                    # 3. ACCOUNT FLOW ROUTING (ACCOUNT_FLOW_ID_2) - Unchanged
                    elif flow_id_key == "ACCOUNT_FLOW_ID_2":
                        if current_screen == "PROFILE_UPDATE":
                            new_name = user_data.get("name", "N/A")
                            new_email = user_data.get("email", "N/A")
                            response_obj = json.loads(json.dumps(current_flow_screens["SUMMARY"]))
                            response_obj["data"]["submitted_name"] = new_name
                            response_obj["data"]["submitted_email"] = new_email
                        else:
                            response_obj = FLOW_DEFINITIONS["ERROR"] 
                        
                    else:
                        response_obj = FLOW_DEFINITIONS["ERROR"]

                else:
                    # Default fallback: Unknown action
                    response_obj = {"screen": current_screen, "data": {"error_message": f"Action '{action}' not handled."}}

                # --- END FLOW ROUTING LOGIC ---
                
                # 4️⃣ Encrypt and return response (Protected against 'None' response_obj)
                if response_obj is not None:
                    flipped_iv = bytes([b ^ 0xFF for b in iv]) 
                    cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                    response_json_string = json.dumps(response_obj)
                    encrypted_resp_bytes, resp_tag = cipher_resp.encrypt_and_digest(response_json_string.encode("utf-8"))
                    full_resp = encrypted_resp_bytes + resp_tag
                    full_resp_b64 = base64.b64encode(full_resp).decode("utf-8")
                    
                    # FIXED LOGGING: Using get() for safety, fallback to 'STATUS_CHECK'
                    next_screen_name = response_obj.get('screen', 'STATUS_CHECK')
                    logger.critical(f"Encrypted flow response generated. Next Screen: {next_screen_name}")
                    return PlainTextResponse(full_resp_b64)
                
                return PlainTextResponse("Flow action processed, but no response object generated.", status_code=200)

            except Exception as e:
                logger.critical(f"General Flow Processing/Security Error: {e}", exc_info=True)
                return PlainTextResponse("Failed to process flow payload due to internal error.", status_code=500)

        # ---- Regular WhatsApp message handling (Text and Media) ----
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        
        if messages:
            message = messages[0]
            from_number = message.get("from")
            message_type = message.get("type")
            
            # Extract user name if available (useful for logging/storage)
            user_name = next((contact.get("profile", {}).get("name") for contact in contacts if contact.get("wa_id") == from_number), from_number)
            
            if message_type == "text":
                user_text = message.get("text", {}).get("body", "")
                if from_number:
                    logger.critical(f"💬 Message from {from_number} ({user_name}): {user_text}")
                    # Use whatsapp_menu for text
                    background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": user_text})
            
            # --- START MEDIA MESSAGE HANDLING ---
            elif message_type in ["image", "document"]:
                media_data = message.get(message_type, {})
                media_id = media_data.get("id")
                mime_type = media_data.get("mime_type")
                
                if media_id and mime_type and from_number:
                    logger.critical(f"🖼️ Media Message received from {from_number} ({user_name}). Type: {message_type}, MIME: {mime_type}, ID: {media_id}")
                    
                    try:
                        # 1. Get the direct download URL from Meta
                        media_url = get_media_url(media_id)
                        
                        # 2. Delegate the file processing (download, analyze, store) to the background
                        # We use "AFFORDABILITY_CHECK" as the flow_type context for file processing
                        background_tasks.add_task(
                            process_file_upload, 
                            user_id=from_number, 
                            user_name=user_name, 
                            user_phone=from_number, 
                            flow_type="AFFORDABILITY_CHECK", 
                            media_url=media_url, 
                            mime_type=mime_type
                        )
                        
                    except RuntimeError as e:
                        # Handle failure in getting media URL
                        logger.error(f"Failed to get media URL for {media_id}: {e}")
                        send_meta_whatsapp_message(from_number, "❌ Samahani, tulipata hitilafu kupata kiungo cha faili lako kutoka WhatsApp. Tafadhali jaribu tena.")
                        
                else:
                    logger.warning(f"Media message lacked required ID/MIME from {from_number}")
                    send_meta_whatsapp_message(from_number, "❌ Samahani, upakiaji wa faili haukukamilika. Tafadhali hakikisha umetuma picha (JPG/PNG/WEBP) au PDF.")
            # --- END MEDIA MESSAGE HANDLING ---
            
            else:
                logger.info(f"Received unhandled message type: {message_type} from {from_number}")
                
        return PlainTextResponse("OK")

    except Exception as e:
        logger.critical(f"Webhook Error: {e}", exc_info=True)
        return PlainTextResponse("Internal Server Error", status_code=500)