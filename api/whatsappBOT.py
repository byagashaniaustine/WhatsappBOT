from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# ------------------------------
# Loan calculator helper
# ------------------------------
def calculate_loan(principal: float, duration: int, rate: float):
    monthly_payment = principal * (1 + (rate / 100) * duration) / duration
    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    return round(monthly_payment, 2), round(total_payment, 2), round(total_interest, 2)

# ------------------------------
# WhatsApp menu handler
# ------------------------------
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        payload = data.get("Body")  # could be flow payload dict or plain text

        # ------------------------------
        # LEGACY / TEXT MESSAGE
        # ------------------------------
        if not isinstance(payload, dict):
            text = str(payload or "").strip().lower()
            starters = ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]

            if text in starters:
                send_manka_menu_template(to=from_number)
                logger.info(f"✅ Sent main menu template to {from_number}")
                return JSONResponse({"status": "ok"})
            else:
                # Fallback for unknown text
                send_meta_whatsapp_message(
                    from_number,
                    "⚠️ Samahani, sielewi kilichotumwa. Tafadhali angalia menyu yetu hapa chini."
                )
                send_manka_menu_template(to=from_number)
                logger.info(f"⚠️ Sent fallback message + main menu template to {from_number}")
                return JSONResponse({"status": "ok"})

        # ------------------------------
        # FLOW PAYLOAD
        # ------------------------------
        screen_id = payload.get("screen")
        action = payload.get("action")
        user_data = payload.get("data", {})

        logger.info(f"Received flow payload: screen={screen_id}, action={action}, user={from_number}")

        # ------------------------------
        # Handle Loan Calculator submission
        # ------------------------------
        if screen_id == "LOAN_CALCULATOR" and action == "data_exchange":
            try:
                principal = float(user_data.get("principal", 0))
                duration = int(user_data.get("duration", 1))
                rate = float(user_data.get("rate", 0))

                monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)

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
                return JSONResponse(response_screen)

            except Exception as e:
                logger.error(f"Loan calculation failed: {e}")
                return JSONResponse({
                    "screen": "ERROR",
                    "data": {"error_message": "Kikokotoo cha mkopo kilishindikana"}
                })

        # ------------------------------
        # Handle complete action (end of flow)
        # ------------------------------
        if action == "complete":
            send_manka_menu_template(to=from_number)
            return JSONResponse({"screen": "MAIN_MENU", "data": {}})

        # ------------------------------
        # Dynamic navigation for other screens
        # ------------------------------
        next_screen = None
        if "menu_selection" in user_data:
            next_screen = user_data["menu_selection"]
        elif "next_screen" in user_data:
            next_screen = user_data["next_screen"]

        if next_screen:
            logger.info(f"Navigating user {from_number} to next screen: {next_screen}")
            return JSONResponse({"screen": next_screen, "data": {}})

        # ------------------------------
        # Default: pass current screen forward
        # ------------------------------
        return JSONResponse({"screen": screen_id, "data": user_data})

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
