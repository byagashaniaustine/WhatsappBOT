import logging
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message,send_manka_menu_template

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# -------------------------------------------------------
# Loan calculator helper
# -------------------------------------------------------
def calculate_loan(principal: float, duration: int, rate: float):
    """Return monthly payment, total payment, and total interest."""
    monthly_payment = principal * (1 + (rate / 100) * duration) / duration
    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    return monthly_payment, total_payment, total_interest

# -------------------------------------------------------
# WhatsApp flow handler
# -------------------------------------------------------
async def whatsapp_menu(data: dict):
    """
    Handles both text messages and flow payloads.
    Routes screens correctly and calculates loan results if needed.
    """
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        payload = data.get("Body")
        if not isinstance(payload, dict):
            # Legacy text messages
            text = str(payload or "").strip().lower()
            if text in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
                send_manka_menu_template(to=from_number)
                logger.info(f"✅ Sent main menu template to {from_number}")
                return PlainTextResponse("OK")
            else:
                # unrecognized input → polite Swahili response + menu template
                send_meta_whatsapp_message(
                    from_number,
                    "Samahani, sielewi kilichotumwa. Tafadhali angalia menyu yetu chini."
                )
                send_manka_menu_template(to=from_number)
                logger.info(f"⚠️ Sent fallback message + main menu to {from_number}")
                return PlainTextResponse("OK")
        # Extract screen info
        current_screen_id = payload.get("screen")
        action = payload.get("action")
        user_data = payload.get("data", {})

        # Determine next screen
        next_screen_id = user_data.get("next_screen") or current_screen_id

        logger.info(f"Payload received: current_screen={current_screen_id}, next_screen={next_screen_id}, action={action}, user={from_number}")

        # ----------------------------
        # Loan Calculator Submission
        # ----------------------------
        if next_screen_id == "LOAN_CALCULATOR" and action == "data_exchange":
            try:
                principal = float(user_data.get("principal", 0))
                duration = int(user_data.get("duration", 1))
                rate = float(user_data.get("rate", 0))

                monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)

                # Prepare LOAN_RESULT screen
                response_screen = {
                    "screen": "LOAN_RESULT",
                    "data": {
                        "principal": f"{principal:,.0f}",
                        "duration": str(duration),
                        "rate": str(rate),
                        "monthly_payment": f"{monthly_payment:,.0f}",
                        "total_payment": f"{total_payment:,.0f}",
                        "total_interest": f"{total_interest:,.0f}"
                    }
                }
                return PlainTextResponse(response_screen)

            except Exception as e:
                logger.error(f"Loan calculation failed: {e}")
                return PlainTextResponse({
                    "screen": "ERROR",
                    "data": {"error_message": "Loan calculation failed"}
                })

        # ----------------------------
        # Complete Flow
        # ----------------------------
        if action == "complete":
            return PlainTextResponse({
                "screen": "MAIN_MENU",
                "data": {}
            })

        # ----------------------------
        # Default: forward the payload to next screen
        # ----------------------------
        return PlainTextResponse({
            "screen": next_screen_id,
            "data": user_data
        })

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return PlainTextResponse("Internal Server Error", status_code=500)
