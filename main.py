# file: main.py
import os
import json
import base64
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP,AES
from Crypto.Hash import SHA256

# -------------------------------
# Config & Logging
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp_flows")
logger.setLevel(logging.INFO)

app = FastAPI()

WEBHOOK_VERIFY_TOKEN = os.environ["WEBHOOK_VERIFY_TOKEN"]
PRIVATE_KEY_PEM = os.environ["PRIVATE_KEY"].replace("\\n", "\n")
FLOW_AES_KEY = base64.b64decode(os.environ["FLOW_AES_KEY"])  # 32-byte key for v7 data_exchange

# Your Flow Asset ID (get from Meta dashboard)
FLOW_ID = os.environ["FLOW_ID"]

# -------------------------------
# RSA Setup (for decrypting AES key from Meta)
# -------------------------------
private_key = RSA.import_key(PRIVATE_KEY_PEM)
rsa_cipher = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)

# -------------------------------
# Helper: Send Flow Message (use your existing function)
# -------------------------------
from services.meta import send_interactive_message  # ← your existing function

def restart_flow(phone: str, screen_id: str, data: dict = None):
    send_interactive_message(
        to=phone,
        type="flow",
        flow_id=FLOW_ID,
        initial_screen_id=screen_id,
        data=data or {}
    )

# -------------------------------
# 1. Webhook Verification
# -------------------------------
@app.get("/webhook")
async def verify(mode: str = None, token: str = None, challenge: str = None):
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    raise HTTPException(403)

# -------------------------------
# 2. MAIN WEBHOOK (Handles complete, pings, etc.)
# -------------------------------
@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                flows = value.get("flows", [])

                # Handle Flow "complete" action
                for flow in flows:
                    if flow.get("action") == "complete":
                        phone = flow["from"]
                        user_data = flow.get("data", {})

                        jump_to = user_data.get("jump_to")
                        if jump_to:
                            logger.info(f"Dynamic jump to {jump_to} for {phone}")
                            restart_flow(phone, jump_to)
                        return {"status": "ok"}

                # Handle regular messages if needed
                for msg in messages:
                    if msg["type"] == "text":
                        phone = msg["from"]
                        # Optional: restart menu
                        restart_flow(phone, "MAIN_MENU")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"error": str(e)}, 500

# -------------------------------
# 3. DATA_EXCHANGE ENDPOINT (v7+ Flows)
# -------------------------------
@app.post("/api/flow-router")
async def flow_data_exchange(request: Request):
    try:
        body = await request.json()
        exchange = body["data_exchange"]
        payload_in = exchange["payload"]

        # Support both old and new encryption formats
        encrypted_aes_key_b64 = payload_in.get("encrypted_aes_key")
        encrypted_data_b64 = payload_in.get("encrypted_flow_data") or payload_in.get("encrypted_data")
        iv_b64 = payload_in.get("initial_vector") or payload_in.get("iv")

        if not all([encrypted_aes_key_b64, encrypted_data_b64, iv_b64]):
            raise ValueError("Missing encryption fields")

        # Decrypt AES key
        aes_key = rsa_cipher.decrypt(base64.b64decode(encrypted_aes_key_b64))
        iv = base64.b64decode(iv_b64)
        encrypted_bytes = base64.b64decode(encrypted_data_b64)
        ciphertext, tag = encrypted_bytes[:-16], encrypted_bytes[-16:]

        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        user_data = json.loads(decrypted.decode())

        logger.info(f"Received from user: {user_data}")

        # YOUR DYNAMIC ROUTING LOGIC
        selected = user_data.get("selected_service") or user_data.get("go_to") or user_data.get("selected")

        screen_map = {
            "CREDIT_SCORE": "CREDIT_SCORE",
            "CREDIT_BANDWIDTH": "CREDIT_BANDWIDTH",
            "LOAN_CALCULATOR": "LOAN_CALCULATOR",
            "LOAN_TYPES": "LOAN_TYPES",
            "SERVICES": "SERVICES"
        }
        target_screen = screen_map.get(selected, "MAIN_MENU")

        # Response: tell system to complete and jump
        response_data = {"jump_to": target_screen}
        resp_json = json.dumps(response_data).encode()

        # Encrypt response
        resp_iv = os.urandom(12)
        resp_cipher = AES.new(aes_key, AES.MODE_GCM, nonce=resp_iv)
        resp_ct, resp_tag = resp_cipher.encrypt_and_digest(resp_json)

        encrypted_resp = base64.b64encode(resp_ct + resp_tag).decode()
        encrypted_iv = base64.b64encode(resp_iv).decode()

        return {
            "version": "3.0",
            "data_exchange": {
                "id": exchange["id"],
                "payload": {
                    "encrypted_flow_data": encrypted_resp,
                    "encrypted_aes_key": encrypted_aes_key_b64,  # echo back
                    "initial_vector": encrypted_iv
                }
            }
        }

    except Exception as e:
        logger.exception(f"data_exchange failed: {e}")
        raise HTTPException(500, "Processing failed")