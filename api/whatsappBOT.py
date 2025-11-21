import logging
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, get_media_url, process_file_upload

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# ----------------------------
# MAIN MENU CONFIG
# ----------------------------
main_menu = {
    "1": {"title": "Fahamu kuhusu Alama za Mikopo (Credit Score)", "description": "Alama ya mikopo ..."},
    "2": {"title": "Kiwango cha Mkopo (Credit Bandwidth)", "description": "Kiwango cha mkopo ..."},
    "3": {"title": "Nakopesheka!! (Uwezo wa Kukopa)", "description": "Uwezo wa Kukopa ..."},
    "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "description": "Tumia kikokotoo kujua kiasi ..."},
    "5": {"title": "Aina za Mikopo", "description": "Mikopo inaweza kugawanywa ..."},
    "6": {"title": "Huduma za Mikopo", "description": "Kuna huduma za aina mbalimbali ..."},
}

# ----------------------------
# USER STATES
# ----------------------------
user_states = {}  # phone_number -> {"mode": str, "step": int, "data": {}}

# ----------------------------
# LOAN CALCULATOR FUNCTION
# ----------------------------
def calculate_monthly_payment(principal: float, duration: int, rate_percent: float, riba_type: int) -> float:
    if riba_type == 1:  # daily
        months = duration / 30
    elif riba_type == 2:  # weekly
        months = duration / 4
    else:
        months = duration
    total_payment = principal * (1 + (rate_percent / 100) * months)
    return total_payment / months if months else total_payment

# ----------------------------
# WHATSAPP MENU HANDLER
# ----------------------------
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = str(data.get("Body") or "").strip().lower()
        state = user_states.get(from_number)

        # ----------------------------
        # LOAN CALCULATOR STATE
        # ----------------------------
        if state and state.get("mode") == "LOAN_CALC":
            step = state["step"]
            collected = state["data"]

            try:
                if step == 1:
                    collected["principal"] = float(incoming_msg)
                    state["step"] = 2
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza muda wa mkopo (idadi ya siku/ wiki/ miezi):")
                elif step == 2:
                    collected["duration"] = int(incoming_msg)
                    state["step"] = 3
                    send_meta_whatsapp_message(from_number, "Chagua aina ya riba:\n1️⃣ Riba ya Siku\n2️⃣ Riba ya Wiki\n3️⃣ Riba ya Mwezi")
                elif step == 3:
                    if incoming_msg not in ["1", "2", "3"]:
                        send_meta_whatsapp_message(from_number, "❌ Tafadhali chagua 1, 2, au 3.")
                        return PlainTextResponse("OK")
                    collected["riba_type"] = int(incoming_msg)
                    state["step"] = 4
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza asimilia za riba ya %:")
                elif step == 4:
                    collected["rate"] = float(incoming_msg)
                    P, t, r, riba_type = collected["principal"], collected["duration"], collected["rate"], collected["riba_type"]
                    monthly_payment = calculate_monthly_payment(P, t, r, riba_type)
                    unit = "siku" if riba_type == 1 else "wiki" if riba_type == 2 else "miezi"
                    message = (
                        f"💰 *Matokeo ya Kikokotoo cha Mkopo*\n\n"
                        f"Kiasi cha mkopo: Tsh {P:,.0f}\nMuda: {t} {unit}\nRiba: {r}%\n\n"
                        f"Kiasi cha kulipa kila mwezi: Tsh {monthly_payment:,.0f}"
                    )
                    send_meta_whatsapp_message(from_number, message)
                    user_states.pop(from_number)
                    return PlainTextResponse("OK")
            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Tafadhali ingiza namba sahihi.")
            return PlainTextResponse("OK")

        # ----------------------------
        # MAIN MENU TRIGGERS
        # ----------------------------
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_list = "\n".join([f"*{k}* - {v['title']}" for k, v in main_menu.items()])
            reply = f"👋 *Karibu kwenye Huduma za Mikopo!*\n\nChagua huduma kwa kutuma namba:\n\n{menu_list}"
            send_meta_whatsapp_message(from_number, reply)
            return PlainTextResponse("OK")

        # ----------------------------
        # USER MENU SELECTION
        # ----------------------------
        if incoming_msg in main_menu:
            if incoming_msg == "3":
                # Option 3: Send WhatsApp template directly
                template_payload = {
                    "to": from_number,
                    "type": "template",
                    "template": {
                        "name": "survey_ask",
                        "language": {"code": "en"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": "Please help us fill-in our survey. Press the button below to start."}
                                ]
                            },
                            {
                                "type": "button",
                                "sub_type": "quick_reply",
                                "index": 0,
                                "parameters": [{"type": "payload", "payload": "start_survey"}]
                            }
                        ]
                    }
                }
                send_meta_whatsapp_message(from_number, template_payload=template_payload)
                return PlainTextResponse("OK")

            elif incoming_msg == "4":
                user_states[from_number] = {"mode": "LOAN_CALC", "step": 1, "data": {}}
                send_meta_whatsapp_message(from_number, "Karibu kwenye Kikokotoo cha Mkopo!\nTafadhali ingiza kiasi unachotaka kukopa (Tsh):")
                return PlainTextResponse("OK")

            else:
                item = main_menu[incoming_msg]
                send_meta_whatsapp_message(from_number, f"*{item['title']}*\n\n{item['description']}")
                return PlainTextResponse("OK")

        # ----------------------------
        # UNKNOWN INPUT
        # ----------------------------
        send_meta_whatsapp_message(from_number, "⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(from_number, "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'.")
        return PlainTextResponse("Internal Server Error", status_code=500)
