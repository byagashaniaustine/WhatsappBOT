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
user_states = {}  
# Example: {"+255712345678": {"mode": "LOAN_CALC", "step": 1, "data": {}}}

# =====================================================
# LOAN CALCULATOR HELPER
# =====================================================
def calculate_monthly_payment(principal: float, duration: int, rate_percent: float, riba_type: int) -> float:
    """Calculate monthly payment based on principal, duration, interest rate, and riba type."""
    
    if riba_type == 1:      # daily
        months = duration / 30
    elif riba_type == 2:    # weekly
        months = duration / 4
    else:                   # monthly
        months = duration

    # Simple interest calculation, as per original bot logic structure
    total_payment = principal * (1 + (rate_percent / 100) * months)

    return total_payment / months if months else total_payment


# =====================================================
# MAIN WHATSAPP BOT FUNCTION
# =====================================================
async def whatsapp_menu(from_number: str, incoming_msg_body: str, wa_id: str):
    """
    Handles stateful text messages. 
    NOTE: Arguments are now received directly from the webhook caller (whatsapp_flow_webhook.py).
    """
    try:
        # The variables (from_number, wa_id) are now provided directly and are clean.
        
        # Clean the incoming message body
        incoming_msg = incoming_msg_body.strip().lower()
        state = user_states.get(from_number)

        # =====================================================
        # LOAN CALCULATOR FLOW STEPS
        # =====================================================
        if state and state.get("mode") == "LOAN_CALC":

            step = state["step"]
            collected = state["data"]

            try:
                # STEP 1: Collect principal
                if step == 1:
                    collected["principal"] = float(incoming_msg)
                    state["step"] = 2
                    send_meta_whatsapp_message(
                        from_number,
                        "Tafadhali ingiza muda wa mkopo (siku / wiki / miezi):",
                        wa_id
                    )

                # STEP 2: Collect duration
                elif step == 2:
                    collected["duration"] = int(incoming_msg)
                    state["step"] = 3
                    send_meta_whatsapp_message(
                        from_number,
                        "Chagua aina ya riba:\n"
                        "1️⃣ Riba ya Siku\n"
                        "2️⃣ Riba ya Wiki\n"
                        "3️⃣ Riba ya Mwezi",
                        wa_id
                    )

                # STEP 3: Choose riba type
                elif step == 3:
                    if incoming_msg not in ["1", "2", "3"]:
                        send_meta_whatsapp_message(from_number, "❌ Tafadhali chagua 1, 2, au 3.", wa_id)
                        return PlainTextResponse("OK")

                    collected["riba_type"] = int(incoming_msg)
                    state["step"] = 4
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza asilimia ya riba (%):", wa_id)

                # STEP 4: Collect interest rate and compute
                elif step == 4:
                    collected["rate"] = float(incoming_msg)

                    P = collected["principal"]
                    t = collected["duration"]
                    r = collected["rate"]
                    riba_type = collected["riba_type"]

                    monthly_payment = calculate_monthly_payment(P, t, r, riba_type)

                    unit = "siku" if riba_type == 1 else "wiki" if riba_type == 2 else "miezi"

                    message = (
                        f"💰 *Matokeo ya Kikokotoo cha Mkopo*\n\n"
                        f"Kiasi cha mkopo: Tsh {P:,.0f}\n"
                        f"Muda: {t} {unit}\n"
                        f"Riba: {r}%\n\n"
                        f"Kiasi cha kulipa kila mwezi: *Tsh {monthly_payment:,.0f}*"
                    )

                    send_meta_whatsapp_message(from_number, message, wa_id)
                    user_states.pop(from_number)  # CLEAR USER STATE
                    return PlainTextResponse("OK")

            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Tafadhali ingiza namba sahihi.", wa_id)
                return PlainTextResponse("OK")

            return PlainTextResponse("OK")

        # =====================================================
        # SHOW MAIN MENU
        # =====================================================
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_list = "\n".join([f"*{k}* - {v}" for k, v in main_menu.items()])
            send_meta_whatsapp_message(
                from_number,
                f"👋 *Karibu kwenye Huduma za Mikopo!*\n\n"
                "Chagua huduma kwa kutuma namba:\n\n" + menu_list,
                wa_id
            )
            return PlainTextResponse("OK")

        # =====================================================
        # HANDLE USER OPTION SELECTION
        # =====================================================
        if incoming_msg in main_menu:

            # -------------------------------------------------
            # OPTION 3 — Send Template With Flow Button
            # -------------------------------------------------
            if incoming_msg == "3":
                send_meta_whatsapp_template(
                    to=from_number,
                    template_name="nakopeshekaa_1",
                    language_code="en_US",
                    components=[
                        {
                            "type": "body",
                            "parameters": []
                        }
                    ]
                )
                return PlainTextResponse("OK")

            # -------------------------------------------------
            # OPTION 4 — Start Loan Calculator
            # -------------------------------------------------
            if incoming_msg == "4":
                user_states[from_number] = {"mode": "LOAN_CALC", "step": 1, "data": {}}
                send_meta_whatsapp_message(
                    from_number,
                    "Karibu kwenye Kikokotoo cha Mkopo!\n"
                    "Tafadhali ingiza kiasi unachotaka kukopa (Tsh):",
                    wa_id
                )
                return PlainTextResponse("OK")

            # -------------------------------------------------
            # OTHER MENU OPTIONS → Simple replies
            # -------------------------------------------------
            title = main_menu[incoming_msg]
            send_meta_whatsapp_message(
                from_number,
                f"*{title}*\n\nTafadhali angalia huduma hii kupitia flow yetu ya WhatsApp.",
                wa_id
            )
            return PlainTextResponse("OK")

        # =====================================================
        # UNKNOWN INPUT
        # =====================================================
        send_meta_whatsapp_message(
            from_number,
            "⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena.",
            wa_id
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")

        # Ensure the final error message also includes wa_id
        # Note: If an error occurs before wa_id is available in the caller, this might not run, 
        # but in the corrected structure, it should always be available here.
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'.",
            wa_id
        )
        return PlainTextResponse("Internal Server Error", status_code=500)