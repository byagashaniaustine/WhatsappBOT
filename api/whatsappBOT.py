import logging
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# -------------------------------------------------------
# Loan calculator helper
# -------------------------------------------------------
def calculate_loan(principal: float, duration: int, rate: float):
    """
    Monthly payment = principal * (1 + rate*duration)/duration
    All in months
    """
    monthly_payment = principal * (1 + (rate / 100) * duration) / duration
    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    return monthly_payment, total_payment, total_interest

# -------------------------------------------------------
# Unified WhatsApp flow handler
# -------------------------------------------------------
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        payload = data.get("Body")  # Could be text or flow payload

        # ------------------------------------------
        # Handle legacy or plain text messages
        # ------------------------------------------
        if not isinstance(payload, dict):
            text = str(payload or "").strip().lower()
            if text in ["hi", "start", "menu", "hello", "anza", "habari", "mambo"]:
                # Send main menu template
                send_manka_menu_template(to=from_number)
                return PlainTextResponse("OK")
            # Unknown text fallback
            send_meta_whatsapp_message(
                from_number,
                "⚠️ Samahani, hatuwezi kuelewa mahitaji yako. Tafadhali tuma *menu* ili kuona menyu yetu."
            )
            return PlainTextResponse("OK")

        # ------------------------------------------
        # Handle flow payload
        # ------------------------------------------
        screen_id = payload.get("screen")
        action = payload.get("action")
        user_data = payload.get("data", {})

        logger.info(f"Flow payload: screen={screen_id}, action={action}, user={from_number}")

        # ---------------------------------------------------
        # Handle Loan Calculator screen
        # ---------------------------------------------------
        if screen_id == "LOAN_CALCULATOR" and action == "data_exchange":
            try:
                # Extract values from form
                principal = float(user_data.get("principal", 0))
                duration = int(user_data.get("duration", 1))
                rate = float(user_data.get("rate", 0))

                # Compute loan results
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
                logger.error(f"Loan calculation error: {e}")
                return PlainTextResponse({
                    "screen": "ERROR",
                    "data": {"error_message": "Kikokotoo cha mkopo kimeshindwa"}
                })

        # ---------------------------------------------------
        # Handle completion of a flow
        # ---------------------------------------------------
        if action == "complete":
            return PlainTextResponse({"screen": "MAIN_MENU", "data": {}})

        # ---------------------------------------------------
        # All other screens: continue the flow without modification
        # ---------------------------------------------------
        return PlainTextResponse({
            "screen": screen_id,
            "data": user_data
        })

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return PlainTextResponse("Internal Server Error", status_code=500)
