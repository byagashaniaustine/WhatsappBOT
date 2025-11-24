import logging
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_template

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# =====================================================
# MAIN MENU
# =====================================================
main_menu = {
    "1": "Fahamu kuhusu Alama za Mikopo (Credit Score)",
    "2": "Kiwango cha Mkopo (Credit Bandwidth)",
    "3": "Nakopesheka!! (Uwezo wa Kukopa) - Template + Flow",
    "4": "Kikokotoo cha Mkopo (Loan Calculator)",
    "5": "Aina za Mikopo",
    "6": "Huduma za Mikopo"
}

# =====================================================
# USER STATES
# =====================================================
user_states = {}  # Example: {"+255712345678": {"mode": "LOAN_CALC", "step": 1, "data": {}}}

# =====================================================
# LOAN CALCULATOR HELPER
# =====================================================
def calculate_monthly_payment(principal: float, duration: int, rate_percent: float, riba_type: int) -> float:
    if riba_type == 1:      # daily
        months = duration / 30
    elif riba_type == 2:    # weekly
        months = duration / 4
    else:                   # monthly
        months = duration
    total_payment = principal * (1 + (rate_percent / 100) * months)
    return total_payment / months if months else total_payment

# =====================================================
# MAIN WHATSAPP BOT FUNCTION
# =====================================================
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = str(data.get("Body") or "").strip().lower()
        state = user_states.get(from_number)

        # =========================
        # LOAN CALCULATOR FLOW
        # =========================
        if state and state.get("mode") == "LOAN_CALC":
            step = state["step"]
            collected = state["data"]

            try:
                if step == 1:
                    collected["principal"] = float(incoming_msg)
                    state["step"] = 2
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza muda wa mkopo (siku / wiki / miezi):")
                elif step == 2:
                    collected["duration"] = int(incoming_msg)
                    state["step"] = 3
                    send_meta_whatsapp_message(
                        from_number,
                        "Chagua aina ya riba:\n1️⃣ Riba ya Siku\n2️⃣ Riba ya Wiki\n3️⃣ Riba ya Mwezi"
                    )
                elif step == 3:
                    if incoming_msg not in ["1", "2", "3"]:
                        send_meta_whatsapp_message(from_number, "❌ Tafadhali chagua 1, 2, au 3.")
                        return PlainTextResponse("OK")
                    collected["riba_type"] = int(incoming_msg)
                    state["step"] = 4
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza asilimia ya riba (%):")
                elif step == 4:
                    collected["rate"] = float(incoming_msg)

                    P = collected["principal"]
                    t = collected["duration"]
                    r = collected["rate"]
                    riba_type = collected["riba_type"]

                    monthly_payment = calculate_monthly_payment(P, t, r, riba_type)
                    unit = "siku" if riba_type == 1 else "wiki" if riba_type == 2 else "miezi"

                    send_meta_whatsapp_message(
                        from_number,
                        f"💰 *Matokeo ya Kikokotoo cha Mkopo*\n\n"
                        f"Kiasi cha mkopo: Tsh {P:,.0f}\n"
                        f"Muda: {t} {unit}\n"
                        f"Riba: {r}%\n\n"
                        f"Kiasi cha kulipa kila mwezi: *Tsh {monthly_payment:,.0f}*"
                    )
                    user_states.pop(from_number)
                    return PlainTextResponse("OK")

            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Tafadhali ingiza namba sahihi.")
                return PlainTextResponse("OK")

            return PlainTextResponse("OK")

        # =========================
        # SHOW MAIN MENU
        # =========================
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_list = "\n".join([f"*{k}* - {v}" for k, v in main_menu.items()])
            send_meta_whatsapp_message(
                from_number,
                f"👋 *Karibu kwenye Huduma za Mikopo!*\n\nChagua huduma kwa kutuma namba:\n\n{menu_list}"
            )
            return PlainTextResponse("OK")

        # =========================
        # HANDLE MENU SELECTION
        # =========================
        if incoming_msg in main_menu:
            if incoming_msg == "3":
                send_meta_whatsapp_template(
                    to=from_number,
                    template_name="hello",
                    language_code="en_US",
                    components=[{"type": "body", "parameters": []}]
                )
                return PlainTextResponse("OK")

            elif incoming_msg == "4":
                user_states[from_number] = {"mode": "LOAN_CALC", "step": 1, "data": {}}
                send_meta_whatsapp_message(from_number, "Karibu kwenye Kikokotoo cha Mkopo!\nTafadhali ingiza kiasi unachotaka kukopa (Tsh):")
                return PlainTextResponse("OK")

            else:
                title = main_menu[incoming_msg]
                send_meta_whatsapp_message(from_number, f"*{title}*\n\nTafadhali angalia huduma hii kupitia flow yetu ya WhatsApp.")
                return PlainTextResponse("OK")

        # =========================
        # UNKNOWN INPUT
        # =========================
        send_meta_whatsapp_message(from_number, "⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(from_number, "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'.")
        return PlainTextResponse("Internal Server Error", status_code=500)
