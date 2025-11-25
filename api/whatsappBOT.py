from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)


def calculate_loan(principal: float, duration: int, rate: float):
    """Calculate monthly payment, total payment, and total interest."""
    monthly_payment = principal * (1 + (rate / 100) * duration) / duration
    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    return monthly_payment, total_payment, total_interest


async def whatsapp_menu(data: dict):
    """
    Unified handler for flow payloads.
    Expects structured flow payload, not free text.
    """
    try:
        # ------------------------------
        # Extract sender and payload
        # ------------------------------
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        payload = data.get("Body")  # Expecting dict from flow, not plain text

        if not isinstance(payload, dict):
            # fallback for legacy text (optional)
            send_meta_whatsapp_message(
                from_number,
                "⚠️ Samahani, sielewi kilichotumwa. Tafadhali angalia menyu yetu."
            )
            send_manka_menu_template(to=from_number)
            return JSONResponse({"status": "ok"})

        # ------------------------------
        # Extract flow fields
        # ------------------------------
        screen_id = payload.get("screen")
        action = payload.get("action")
        user_data = payload.get("data", {})

        logger.info(f"📥 Received payload from {from_number}: screen={screen_id}, action={action}")

        # ------------------------------
        # Handle MAIN_MENU selection
        # ------------------------------
        if screen_id == "MAIN_MENU" and action == "data_exchange":
            # payload should contain: main_menu_form.menu_selection
            selection_obj = user_data.get("main_menu_form", {}).get("menu_selection")
            if not selection_obj:
                send_meta_whatsapp_message(
                    from_number,
                    "⚠️ Samahani, hatukupata chaguo lako. Tafadhali jaribu tena."
                )
                send_manka_menu_template(to=from_number)
                return JSONResponse({"status": "ok"})

            # The selection object usually has {"id": "...", "title": "..."}
            next_screen_id = selection_obj.get("id")
            logger.info(f"➡️ User selected menu id={next_screen_id}")
            return JSONResponse({"screen": next_screen_id, "data": {}})

        # ------------------------------
        # Handle Loan Calculator submission
        # ------------------------------
        if screen_id == "LOAN_CALCULATOR" and action == "data_exchange":
            try:
                principal = float(user_data.get("loan_calc_form", {}).get("principal", 0))
                duration = int(user_data.get("loan_calc_form", {}).get("duration", 1))
                rate = float(user_data.get("loan_calc_form", {}).get("rate", 0))

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
                logger.error(f"❌ Loan calculation failed: {e}")
                return JSONResponse({
                    "screen": "ERROR",
                    "data": {"error_message": "Kikokotoo cha mkopo kilishindikana"}
                })

        # ------------------------------
        # Handle complete action
        # ------------------------------
        if action == "complete":
            return JSONResponse({"screen": "MAIN_MENU", "data": {}})

        # ------------------------------
        # Pass through other screens
        # ------------------------------
        return JSONResponse({"screen": screen_id, "data": user_data})

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            from_number,
            "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
