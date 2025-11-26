from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)


def calculate_loan(principal: float, duration: int, rate: float):
    """
    Calculate monthly payment, total payment, and total interest.
    Assumes rate is the monthly percentage (e.g., 2.5)
    Uses the standard amortization formula.
    """
    
    if duration <= 0 or principal <= 0:
        raise ValueError("Principal and duration must be positive.")
        
    # Convert monthly percentage rate (e.g., 2.5%) to monthly decimal rate (0.025)
    monthly_rate_decimal = rate / 100.0
    
    if monthly_rate_decimal == 0:
        monthly_payment = principal / duration
    else:
        n = duration
        i = monthly_rate_decimal
        # Amortization Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1]
        numerator = i * (1 + i)**n
        denominator = (1 + i)**n - 1
        monthly_payment = principal * (numerator / denominator)

    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    
    # Return raw numbers for precise use, formatted for display later
    return monthly_payment, total_payment, total_interest


async def whatsapp_menu(data: dict):
    """
    Unified handler for flow payloads and regular text messages.
    Expects data = {"From": <phone>, "Body": <decrypted_flow_json_dict OR text>}
    """
    
    from_number = str(data.get("From") or "")
    # Ensure phone number is in E.164 format for safe use
    if not from_number.startswith("+"):
        from_number = "+" + from_number
        
    payload = data.get("Body")

    # --- 1. Handle Regular Text Message Fallback ---
    if isinstance(payload, str):
        # This is not a flow, it's a regular text message (e.g., a reply to a menu template)
        user_text = payload.strip().upper()
        
        # Simple text logic (optional, but good for main menu access)
        if user_text in ["MENU", "MWANZO"]:
            send_manka_menu_template(to=from_number)
            return JSONResponse({"status": "ok", "message": "Text menu sent"})

        # IMPORTANT: When a flow is active, regular text messages are ignored by Meta's Flow protocol.
        # This part handles regular messages when no flow is running.
        send_meta_whatsapp_message(
            from_number,
            f"Samahani, sikuelewi '{payload}'. Tuma 'menu' kupata orodha ya huduma."
        )
        send_manka_menu_template(to=from_number)
        return JSONResponse({"status": "ok", "message": "Text message handled"})

    # --- 2. Handle Decrypted Flow Payload (dict) ---
    if isinstance(payload, dict):
        try:
            decrypted_data = payload
            action = decrypted_data.get("action")
            current_screen = decrypted_data.get("screen")
            user_data = decrypted_data.get("data", {})
            
            logger.info(f"📥 Flow Action Received: screen={current_screen}, action={action}")

            # ------------------------------
            # PING/INIT Handler
            # ------------------------------
            if action == "ping" or action == "INIT":
                # Always route to the starting screen ID defined in your JSON
                return JSONResponse({"screen": "MAIN_MENU", "data": {}})

            # ------------------------------
            # MAIN_MENU Submission (Endelea Button Click)
            # ------------------------------
            if current_screen == "MAIN_MENU" and action == "data_exchange":
                # The payload from the flow JSON uses the key "selected_service" directly
                next_screen_id = user_data.get("selected_service")
                
                if next_screen_id in ["CREDIT_SCORE", "CREDIT_BANDWIDTH", "LOAN_CALCULATOR", "LOAN_TYPES", "SERVICES"]:
                    logger.info(f"➡️ Routing to dynamic screen: {next_screen_id}")
                    # Dynamic Routing: Tell Meta to show the screen ID the user selected
                    return JSONResponse({"screen": next_screen_id, "data": {}})
                else:
                    logger.error(f"Invalid selection: {next_screen_id}")
                    # Routing back to the main menu or an error screen
                    return JSONResponse({"screen": "MAIN_MENU", "data": {"error_message": "Chaguo batili."}})
            
            # ------------------------------
            # LOAN_CALCULATOR Submission (Kokotoa Malipo Button Click)
            # ------------------------------
            if current_screen == "LOAN_CALCULATOR" and action == "data_exchange":
                try:
                    # Input field names are 'principal', 'duration', 'rate'
                    principal = float(user_data.get("principal", 0))
                    duration = int(user_data.get("duration", 0))
                    rate = float(user_data.get("rate", 0))

                    monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)

                    response_screen = {
                        "screen": "LOAN_RESULT", # Route to the result screen
                        "data": {
                            "principal": f"{principal:,.0f}",  # Format for Tsh display in Flow
                            "duration": str(duration),
                            "rate": str(rate),
                            "monthly_payment": f"{monthly_payment:,.0f}",
                            "total_payment": f"{total_payment:,.0f}",
                            "total_interest": f"{total_interest:,.0f}"
                        }
                    }
                    return JSONResponse(response_screen)

                except ValueError:
                    # Handle non-numeric input error
                    return JSONResponse({
                        "screen": "LOAN_CALCULATOR", # Stay on calculator screen
                        "data": {"error_message": "Tafadhali jaza nambari sahihi kwa kiasi, muda na riba."}
                    })
                except Exception as e:
                    logger.exception(f"❌ Loan calculation failed: {e}")
                    return JSONResponse({
                        "screen": "ERROR",
                        "data": {"error_message": "Kikokotoo cha mkopo kilishindikana"}
                    })

            # ------------------------------
            # Default/Informational Screen Handling
            # ------------------------------
            # If the user is on an informational screen (CREDIT_SCORE, etc.) and there is no specific action, 
            # or if the flow is terminal (e.g., LOAN_RESULT), we tell Meta to exit the flow by returning the current screen
            # or force the user back to the main menu if they somehow submit from a non-form page.
            
            if action == "complete" or current_screen == "LOAN_RESULT":
                 # This action handles flow exit (if defined in your flow JSON) or simply returns the final state.
                 # No specific action needed here unless you want to log the final state externally.
                 return JSONResponse({"screen": current_screen, "data": user_data})


            # Pass-through / Fallback: If an informational screen is hit, send the user back to the menu.
            return JSONResponse({"screen": "MAIN_MENU", "data": {}})
            
        except Exception as e:
            logger.exception(f"❌ Error processing decrypted flow data: {e}")
            send_meta_whatsapp_message(
                from_number,
                "❌ Hitilafu imetokea katika mfumo wa Flow. Tafadhali jaribu tena."
            )
            # Return a response that tells the Flow to display an error or exit
            return JSONResponse({"screen": "ERROR", "data": {"error_message": "Hitilafu isiyotarajiwa."}})

    return JSONResponse({"status": "ok"})