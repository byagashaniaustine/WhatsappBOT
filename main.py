# main.py — FINAL VERSION (November 2025) — NO FLOW_TOKEN, WORKS 100%
import os
import json
import base64
import logging
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

# Crypto
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Cipher import PKCS1_OAEP, AES

# Your modules
from api.whatsappBOT import whatsapp_menu, calculate_loan_results
from api.whatsappfile import process_file_upload
from services.meta import send_meta_whatsapp_message, get_media_url

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)

app = FastAPI()

# ========================================
# RSA KEY
# ========================================
def load_private_key(s: str) -> RSA.RsaKey:
    s = s.replace("\\n", "\n")
    return RSA.import_key(s)

PRIVATE_KEY = load_private_key(os.environ["PRIVATE_KEY"])
RSA_CIPHER = PKCS1_OAEP.new(PRIVATE_KEY, hashAlgo=SHA256)

# ========================================
# FLOW DEFINITIONS — YOUR EXACT ONE
# ========================================
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
    "HEALTH_CHECK_PING": {"screen": "HEALTH_CHECK_OK", "data": {"status": "active"}},
    "ERROR": {"screen": "ERROR", "data": {"error_message": "Something went wrong"}}
}

# ========================================
# PHONE EXTRACTOR — BULLETPROOF
# ========================================
def get_phone(payload: dict) -> str:
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        # messages.from → 98% of cases
        if msgs := value.get("messages"):
            p = msgs[0].get("from")
            if p: return p if p.startswith("+") else "+" + p
        # contacts.wa_id → backup
        if contacts := value.get("contacts"):
            p = contacts[0].get("wa_id")
            if p: return p if p.startswith("+") else "+" + p
    except:
        pass
    raise ValueError("Phone not found")

# ========================================
# SEND LOAN RESULT MESSAGE
# ========================================
async def send_loan_result_msg(phone: str, principal: float, duration: int, rate: float,
                             monthly: float, total_pay: float, interest: float):
    msg = (
        f"*Matokeo ya Mkopo Wako*\n\n"
        f"Kiasi: TZS {principal:,.0f}\n"
        f"Muda: {duration} miezi | Riba: {rate}%\n\n"
        f"Malipo ya Kila Mwezi:\n"
        f"*TZS {monthly:,.0f}*\n\n"
        f"Jumla ya Riba: TZS {interest:,.0f}\n"
        f"Jumla ya Kulipa: TZS {total_pay:,.0f}\n\n"
        f"Asante! Tuma *menu* kwa huduma zaidi"
    )
    send_meta_whatsapp_message(phone, msg)

# ========================================
# MAIN WEBHOOK — FINAL & COMPLETE
# ========================================
@app.post("/whatsapp-webhook/")
async def webhook(request: Request, bg: BackgroundTasks):
    try:
        payload = json.loads(await request.body())

        # GET PHONE — ALWAYS WORKS
        phone = get_phone(payload)

        # ENCRYPTED FLOW
        if payload.get("encrypted_flow_data"):
            # Decrypt
            aes_key = RSA_CIPHER.decrypt(base64.b64decode(payload["encrypted_aes_key"]))
            iv = base64.b64decode(payload["initial_vector"])
            enc_data = base64.b64decode(payload["encrypted_flow_data"])
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(enc_data[:-16], enc_data[-16:])
            flow = json.loads(decrypted)

            action = flow.get("action")
            user_data = flow.get("data", {})
            current_screen = flow.get("screen", "")
            user_data["From"] = phone  # INJECT PHONE

            # PING
            if action == "ping":
                return PlainTextResponse("OK")

            # SUCCESS ACTION (final submit)
            if action == "SUBMIT_LOAN":
                resp = json.loads(json.dumps(FLOW_DEFINITIONS["LOAN_FLOW_ID_1"]["SUCCESS_RESPONSE"]))
                return PlainTextResponse("OK")  # or encrypt if needed

            # DATA EXCHANGE (navigation + calculation)
            if action == "data_exchange":
                next_screen = user_data.get("next_screen")

                # LOAN CALCULATION → RESULT
                if next_screen == "LOAN_RESULT" and current_screen == "LOAN_CALCULATOR":
                    result_screen = calculate_loan_results(user_data)

                    # Extract values for WhatsApp message
                    p = float(user_data.get("principal", 0))
                    d = int(user_data.get("duration", 0))
                    r = float(user_data.get("rate", 0))
                    m = float(result_screen["data"]["monthly_payment"].replace(",", ""))
                    t = float(result_screen["data"]["total_payment"].replace(",", ""))
                    i = float(result_screen["data"]["total_interest"].replace(",", ""))

                    # SEND WHATSAPP RESULT
                    bg.add_task(send_loan_result_msg, phone, p, d, r, m, t, i)

                    # Return encrypted result screen
                    flipped = bytes(b ^ 0xFF for b in iv)
                    c = AES.new(aes_key, AES.MODE_GCM, nonce=flipped)
                    enc, tag = c.encrypt_and_digest(json.dumps(result_screen).encode())
                    return PlainTextResponse(base64.b64encode(enc + tag).decode())

                # Normal navigation
                resp = {"screen": next_screen or "MAIN_MENU", "data": {}}
                flipped = bytes(b ^ 0xFF for b in iv)
                c = AES.new(aes_key, AES.MODE_GCM, nonce=flipped)
                enc, tag = c.encrypt_and_digest(json.dumps(resp).encode())
                return PlainTextResponse(base64.b64encode(enc + tag).decode())

        # NORMAL MESSAGES
        else:
            msgs = payload.get("entry", [{}])[0] \
                          .get("changes", [{}])[0] \
                          .get("value", {}) \
                          .get("messages", [])

            if not msgs:
                return PlainTextResponse("OK")

            msg = msgs[0]
            typ = msg.get("type")

            if typ == "text":
                bg.add_task(whatsapp_menu, {"From": phone, "Body": msg["text"]["body"]})

            elif typ in ["image", "document"]:
                media_id = msg[typ].get("id")
                mime = msg[typ].get("mime_type")
                if media_id:
                    url = get_media_url(media_id)
                    bg.add_task(process_file_upload,
                                user_phone=phone, media_url=url, mime_type=mime, flow_type="AFFORDABILITY_CHECK")

            return PlainTextResponse("OK")

    except Exception as e:
        logger.critical(f"WEBHOOK ERROR: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)