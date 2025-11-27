import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from starlette.responses import JSONResponse 

# Import cryptography libraries
try:
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256 
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Util.Padding import unpad
except ImportError:
    raise RuntimeError("PyCryptodome is not installed. Please install with: pip install pycryptodome")

# --- Import only necessary functions from whatsappBOT ---
from api.whatsappBOT import whatsapp_menu, calculate_loan_results 
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url 

# Setup logging
logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG) 

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")

# --- FLOW SCREEN DEFINITIONS ---
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

# --- UTILITY FUNCTION FOR ROBUST KEY LOADING ---
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

# --- KEY LOADING AND SETUP ---
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


# --- DEBUG / HEALTH CHECK ENDPOINT ---
@app.post("/debug-test/")
async def debug_test(request: Request):
    logger.critical(f"✅ [DEBUG] Successfully hit the /debug-test/ endpoint from {request.client.host if request.client else 'Unknown Host'}")
    raw_body = await request.body()
    logger.debug(f"[DEBUG] Raw Body Length: {len(raw_body)} bytes.")
    return PlainTextResponse("Debug check successful. Check logs for CRITICAL messages.", status_code=200)

async def send_loan_results_direct(
    to_number: str,
    principal: float,
    duration: int,
    rate: float,
    monthly_payment: float,
    total_payment: float,
    total_interest: float
):
    """Sends beautiful formatted loan results via WhatsApp"""
    message = (
        f"*Matokeo ya Mkopo Wako*\n\n"
        f"💰 *Kiasi cha Mkopo:* TZS {principal:,.0f}\n"
        f"⏳ *Muda:* {duration} miezi\n"
        f"📈 *Riba:* {rate}%\n\n"
        f"✅ *Malipo ya Kila Mwezi:*\n"
        f"*TZS {monthly_payment:,.0f}*\n\n"
        f"🔥 *Jumla ya Riba:* TZS {total_interest:,.0f}\n"
        f"💸 *Jumla ya Kulipa:* TZS {total_payment:,.0f}\n\n"
        f"Asante kwa kutumia huduma yetu!\n"
        f"Tuma *menu* kupata chaguo zaidi"
    )
    try:
        send_meta_whatsapp_message(to_number, message)
        logger.critical(f"Loan results sent to {to_number}")
    except Exception as e:
        logger.error(f"Failed to send results to {to_number}: {e}")

# =============================================
# MAIN WEBHOOK – FULLY FIXED & IMPROVED
# =============================================
@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body)

        # ========================
        # 1. Extract phone number – works for EVERY message type
        # ========================
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        primary_from_number = None
        if messages:
            primary_from_number = messages[0].get("from")
        elif contacts:
            primary_from_number = contacts[0].get("wa_id")

        if primary_from_number and not primary_from_number.startswith("255"):
            primary_from_number = "+" + primary_from_number

        # ========================
        # 2. Handle ENCRYPTED Flow payloads
        # ========================
        encrypted_flow_b64 = payload.get("encrypted_flow_data")
        encrypted_aes_key_b64 = payload.get("encrypted_aes_key")
        iv_b64 = payload.get("initial_vector")

        if encrypted_flow_b64 and encrypted_aes_key_b64 and iv_b64:
            try:
                # Decrypt
                aes_key = RSA_CIPHER.decrypt(base64.b64decode(encrypted_aes_key_b64))
                iv = base64.b64decode(iv_b64)
                encrypted_data = base64.b64decode(encrypted_flow_b64)
                ciphertext, tag = encrypted_data[:-16], encrypted_data[-16:]

                cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
                decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
                decrypted_data = json.loads(decrypted_bytes)

                logger.critical(f"Decrypted Flow Payload: {json.dumps(decrypted_data, indent=2)}")

                action = decrypted_data.get("action")
                flow_token = decrypted_data.get("flow_token")
                user_data = decrypted_data.get("data", {})
                current_screen = decrypted_data.get("screen", "UNKNOWN")
                flow_id_key = user_data.get("flow_id", "LOAN_FLOW_ID_1")
                current_flow = FLOW_DEFINITIONS.get(flow_id_key, {})

                # INJECT PHONE NUMBER INTO user_data – THIS IS THE KEY FIX
                if primary_from_number:
                    user_data["From"] = primary_from_number
                    user_data["phone"] = primary_from_number
                    logger.critical(f"Injected phone {primary_from_number} into Flow user_data")
                else:
                    logger.error("No phone number found in encrypted Flow payload!")

                response_obj = None

                if action == "ping":
                    response_obj = FLOW_DEFINITIONS["HEALTH_CHECK_PING"]

                elif action == "data_exchange":
                    next_screen_key = user_data.get("next_screen")

                    # LOAN CALCULATION → RESULT SCREEN
                    if flow_id_key == "LOAN_FLOW_ID_1" and next_screen_key == "LOAN_RESULT" and current_screen == "LOAN_CALCULATOR":
                        logger.critical("Calculating loan & preparing results screen + WhatsApp message")

                        result_screen = calculate_loan_results(user_data)  # This now has "From" inside

                        # Extract calculated values to send via WhatsApp
                        data = result_screen.get("data", {})
                        try:
                            principal = float(user_data.get("principal", 0))
                            duration = int(user_data.get("duration", 0))
                            rate = float(user_data.get("rate", 0))
                            monthly = float(data.get("monthly_payment", "0").replace(",", ""))
                            total_payment = float(data.get("total_payment", "0").replace(",", ""))
                            interest = float(data.get("total_interest", "0").replace(",", ""))

                            # FIRE AND FORGET WhatsApp message
                            if primary_from_number:
                                background_tasks.add_task(
                                    send_loan_results_direct,
                                    to_number=primary_from_number,
                                    principal=principal,
                                    duration=duration,
                                    rate=rate,
                                    monthly_payment=monthly,
                                    total_payment=total_payment,
                                    total_interest=interest
                                )
                        except Exception as e:
                            logger.error(f"Failed to trigger WhatsApp message: {e}")

                        response_obj = result_screen  # Show LOAN_RESULT screen in Flow

                    # Simple navigation
                    elif next_screen_key and next_screen_key in current_flow:
                        response_obj = {"screen": next_screen_key, "data": {}}
                    else:
                        # Fallback navigation logic (your existing one)
                        response_obj = {"screen": "MAIN_MENU", "data": {}}

                elif action in ("SUBMIT_LOAN", "SAVE_PROFILE"):
                    response_obj = json.loads(json.dumps(current_flow["SUCCESS_RESPONSE"]))
                    if flow_token:
                        response_obj["data"]["extension_message_response"]["params"]["flow_token"] = flow_token

                else:
                    response_obj = {"screen": current_screen, "data": {}}

                # Encrypt response
                if response_obj:
                    flipped_iv = bytes(b ^ 0xFF for b in iv)
                    cipher_resp = AES.new(aes_key, AES.MODE_GCM, nonce=flipped_iv)
                    resp_json = json.dumps(response_obj)
                    encrypted_resp, tag = cipher_resp.encrypt_and_digest(resp_json.encode())
                    full = encrypted_resp + tag
                    return PlainTextResponse(base64.b64encode(full).decode())

                return PlainTextResponse("OK", status_code=200)

            except Exception as e:
                logger.critical(f"Flow decryption/error: {e}", exc_info=True)
                return PlainTextResponse("Error", status_code=500)

        # ========================
        # 3. Normal messages (text, image document)
        # ========================
        if messages:
            msg = messages[0]
            from_number = primary_from_number or msg.get("from")
            if from_number and not from_number.startswith("+"):
                from_number = "+" + from_number

            msg_type = msg.get("type")

            if msg_type == "text":
                body = msg["text"]["body"]
                background_tasks.add_task(whatsapp_menu, {"From": from_number, "Body": body})

            elif msg_type in ["image", "document"]:
                media = msg[msg_type]
                media_id = media.get("id")
                mime = media.get("mime_type")
                if media_id and from_number:
                    try:
                        url = get_media_url(media_id)
                        background_tasks.add_task(
                            process_file_upload,
                            user_id=from_number,
                            user_phone=from_number,
                            media_url=url,
                            mime_type=mime,
                            flow_type="AFFORDABILITY_CHECK"
                        )
                    except Exception as e:
                        send_meta_whatsapp_message(from_number, "Hitilafu kupakua faili lako. Tafadhali jaribu tena.")

            return PlainTextResponse("OK")

        return PlainTextResponse("OK")

    except Exception as e:
        logger.critical(f"Webhook crash: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)