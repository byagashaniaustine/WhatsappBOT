import logging
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_template, send_manka_menu_template

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# =====================================================
# MAIN MENU (Kept for reference but now using template)
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

    total_payment = principal * (1 + (rate_percent / 100) * months)

    return total_payment / months if months else total_payment


# =====================================================
# MAIN WHATSAPP BOT FUNCTION
# =====================================================
async def whatsapp_menu(data: dict):
    try:
        # ------------------------------------------
        # Normalize phone number
        # ------------------------------------------
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = str(data.get("Body") or "").strip().lower()
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
                        "Tafadhali ingiza muda wa mkopo (siku / wiki / miezi):"
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
                        "3️⃣ Riba ya Mwezi"
                    )

                # STEP 3: Choose riba type
                elif step == 3:
                    if incoming_msg not in ["1", "2", "3"]:
                        send_meta_whatsapp_message(from_number, "❌ Tafadhali chagua 1, 2, au 3.")
                        return PlainTextResponse("OK")

                    collected["riba_type"] = int(incoming_msg)
                    state["step"] = 4
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza asilimia ya riba (%):")

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

                    send_meta_whatsapp_message(from_number, message)
                    user_states.pop(from_number)  # CLEAR USER STATE
                    return PlainTextResponse("OK")

            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Tafadhali ingiza namba sahihi.")
                return PlainTextResponse("OK")

            return PlainTextResponse("OK")

        # =====================================================
        # SHOW MAIN MENU - NOW SENDS TEMPLATE INSTEAD OF TEXT
        # =====================================================
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            try:
                logger.info(f"👋 User {from_number} initiated conversation - sending manka_menu template")
                
                # Send the manka_menu template with flow button
                send_manka_menu_template(to=from_number)
                
                logger.info(f"✅ Successfully sent manka_menu template to {from_number}")
                return PlainTextResponse("OK")
                
            except Exception as e:
                logger.error(f"❌ Failed to send template to {from_number}: {e}")
                
                # Fallback to text menu if template fails
                menu_list = "\n".join([f"*{k}* - {v}" for k, v in main_menu.items()])
                send_meta_whatsapp_message(
                    from_number,
                    f"👋 *Karibu kwenye Huduma za Mikopo!*\n\n"
                    "Chagua huduma kwa kutuma namba:\n\n" + menu_list
                )
                return PlainTextResponse("OK")

        # =====================================================
        # HANDLE USER OPTION SELECTION (Legacy text menu)
        # =====================================================
        if incoming_msg in main_menu:

            # -------------------------------------------------
            # OPTION 3 — Send nakopesheka Template
            # -------------------------------------------------
            if incoming_msg == "3":
                send_meta_whatsapp_template(
                    to=from_number,
                    template_name="nakopeshekaa_1",  # Fixed: correct template name
                    language_code="en"
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
                    "Tafadhali ingiza kiasi unachotaka kukopa (Tsh):"
                )
                return PlainTextResponse("OK")

            # -------------------------------------------------
            # OTHER MENU OPTIONS → Simple replies
            # -------------------------------------------------
            title = main_menu[incoming_msg]
            send_meta_whatsapp_message(
                from_number,
                f"*{title}*\n\nTafadhali angalia huduma hii kupitia flow yetu ya WhatsApp."
            )
            return PlainTextResponse("OK")

        # =====================================================
        # UNKNOWN INPUT
        # =====================================================
        send_meta_whatsapp_message(
            from_number,
            "⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kupata menyu kuu."
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")

        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return PlainTextResponse("Internal Server Error", status_code=500)