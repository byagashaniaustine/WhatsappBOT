import logging
from fastapi.responses import PlainTextResponse
from services.meta import (
    send_meta_whatsapp_message,
    send_meta_whatsapp_template,
    send_manka_menu_template
)

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# =====================================================
# USER STATES
# =====================================================
user_states = {}

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
# UNIVERSAL SCREEN ROUTER (FOR ALL JSON FLOW SCREENS)
# =====================================================
async def route_flow_screen(screen_name: str, payload: dict, user: str):
    logger.info(f"➡️ Routing screen: {screen_name}")

    screen_handlers = {
        # Add all your flow screens here
        "welcome_screen": handle_welcome_screen,
        "loan_amount_screen": handle_loan_amount_screen,
        "loan_duration_screen": handle_loan_duration_screen,
        "confirm_details_screen": handle_confirm_details_screen,
        "final_submission_screen": handle_final_submission_screen,
        # Add more screens as needed
    }

    handler = screen_handlers.get(screen_name)

    if handler is None:
        logger.warning(f"⚠️ No handler mapped for screen: {screen_name}")
        send_meta_whatsapp_message(user, f"🚧 Screen '{screen_name}' not implemented.")
        return PlainTextResponse("OK")

    return await handler(payload, user)

# =====================================================
# SAMPLE SCREEN HANDLERS
# (YOU WILL DUPLICATE & EDIT FOR YOUR REAL FLOW SCREENS)
# =====================================================
async def handle_welcome_screen(payload, user):
    name = payload.get("name") or ""
    send_meta_whatsapp_message(user, f"Karibu {name}! Endelea kuchagua.")
    return PlainTextResponse("OK")

async def handle_loan_amount_screen(payload, user):
    amount = payload.get("amount")
    send_meta_whatsapp_message(user, f"Umechagua kiasi: {amount}")
    return PlainTextResponse("OK")

async def handle_loan_duration_screen(payload, user):
    duration = payload.get("duration")
    send_meta_whatsapp_message(user, f"Muda wa mkopo: {duration}")
    return PlainTextResponse("OK")

async def handle_confirm_details_screen(payload, user):
    send_meta_whatsapp_message(user, "Asante kwa kuthibitisha taarifa zako!")
    return PlainTextResponse("OK")

async def handle_final_submission_screen(payload, user):
    send_meta_whatsapp_message(user, "Maombi yako yametumwa kikamilifu!")
    return PlainTextResponse("OK")

# =====================================================
# MAIN WHATSAPP BOT FUNCTION — FULL REWRITE
# =====================================================
async def whatsapp_menu(data: dict):
    try:
        # Normalize phone number
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = data.get("Body")
        state = user_states.get(from_number)

        # =====================================================
        # DYNAMIC FLOW PAYLOAD HANDLING (ALL SCREENS)
        # =====================================================
        if isinstance(incoming_msg, dict):
            screen = data.get("screen")
            flow_id = data.get("flow_id")

            logger.info(
                f"📥 FLOW PAYLOAD RECEIVED | User: {from_number} | Screen: {screen} | Flow ID: {flow_id}"
            )

            # Route based on FLOW SCREEN
            if screen:
                return await route_flow_screen(
                    screen_name=screen,
                    payload=incoming_msg,
                    user=from_number
                )

            incoming_msg = str(incoming_msg)

        else:
            incoming_msg = str(incoming_msg or "").strip().lower()

        # =====================================================
        # LOAN CALCULATOR FLOW (UNTOUCHED)
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
                        "Tafadhali ingiza muda wa mkopo (siku/wiki/miezi):"
                    )

                # STEP 2: Collect duration
                elif step == 2:
                    collected["duration"] = int(incoming_msg)
                    state["step"] = 3
                    send_meta_whatsapp_message(
                        from_number,
                        "Chagua aina ya riba:\n"
                        "1️⃣ Siku\n"
                        "2️⃣ Wiki\n"
                        "3️⃣ Mwezi"
                    )

                # STEP 3: Choose riba type
                elif step == 3:
                    if incoming_msg not in ["1", "2", "3"]:
                        send_meta_whatsapp_message(from_number, "❌ Chagua 1, 2, au 3.")
                        return PlainTextResponse("OK")

                    collected["riba_type"] = int(incoming_msg)
                    state["step"] = 4
                    send_meta_whatsapp_message(from_number, "Ingiza asilimia ya riba (%):")

                # STEP 4: Calculate final result
                elif step == 4:
                    collected["rate"] = float(incoming_msg)

                    P = collected["principal"]
                    t = collected["duration"]
                    r = collected["rate"]
                    riba_type = collected["riba_type"]

                    monthly_payment = calculate_monthly_payment(P, t, r, riba_type)

                    unit = "siku" if riba_type == 1 else "wiki" if riba_type == 2 else "miezi"

                    message = (
                        f"💰 *Kikokotoo cha Mkopo*\n\n"
                        f"Kiasi: Tsh {P:,.0f}\n"
                        f"Muda: {t} {unit}\n"
                        f"Riba: {r}%\n\n"
                        f"Kiasi cha kulipa kila mwezi: *Tsh {monthly_payment:,.0f}*"
                    )

                    send_meta_whatsapp_message(from_number, message)
                    user_states.pop(from_number)
                    return PlainTextResponse("OK")

            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Ingiza namba sahihi.")
                return PlainTextResponse("OK")

            return PlainTextResponse("OK")

        # =====================================================
        # MAIN MENU — Template
        # =====================================================
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            send_manka_menu_template(to=from_number)
            return PlainTextResponse("OK")

        # =====================================================
        # Option 3: Send Template with Flow Button
        # =====================================================
        if incoming_msg == "3":
            send_meta_whatsapp_template(
                to=from_number,
                template_name="nakopeshekaa_1",
                language_code="en"
            )
            return PlainTextResponse("OK")

        # =====================================================
        # Option 4: Start Loan Calculator
        # =====================================================
        if incoming_msg == "4":
            user_states[from_number] = {"mode": "LOAN_CALC", "step": 1, "data": {}}
            send_meta_whatsapp_message(
                from_number,
                "Karibu! Ingiza kiasi unachotaka kukopa (Tsh):"
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
        logger.exception(f"❌ whatsapp_menu error: {e}")
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Jaribu tena."
        )
        return PlainTextResponse("Internal Server Error", status_code=500)
