from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)


def calculate_loan(principal: float, duration: int, rate: float):
    """
    Calculate monthly payment, total payment, and total interest.
    Assumes rate is the monthly percentage (e.g., 2.5)
    Uses the standard amortization formula.
    
    Raises: ValueError if principal or duration are non-positive.
    """
    
    if duration <= 0 or principal <= 0:
        raise ValueError("Principal and duration must be positive.")
        
    monthly_rate_decimal = rate / 100.0
    
    if monthly_rate_decimal == 0:
        monthly_payment = principal / duration
    else:
        n = duration
        i = monthly_rate_decimal
        # Amortization Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1]
        denominator = (1 + i)**n - 1
        if denominator == 0:
             # Handle near zero rate edge case
             monthly_payment = principal / duration
        else:
            numerator = i * (1 + i)**n
            monthly_payment = principal * (numerator / denominator)

    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    
    # Return raw numbers for precise use
    return monthly_payment, total_payment, total_interest


def calculate_loan_results(user_data: dict):
    """
    Performs the loan calculation based on user input and formats the 
    response dictionary for the LOAN_RESULT Flow screen.
    
    Raises: ValueError or other exceptions on bad input/calculation failure.
    """
    
    # Input field names are 'principal', 'duration', 'rate'
    principal = float(user_data.get("principal", 0))
    duration = int(user_data.get("duration", 0))
    rate = float(user_data.get("rate", 0))
    
    logger.critical(f"✅ Executing Loan Calculation: P={principal}, D={duration}, R={rate}")

    # Call the core calculation utility
    monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)

    # Format the results into the required Flow response structure
    response_screen = {
        "screen": "LOAN_RESULT", # The screen ID in the Flow JSON to display results
        "data": {
            # Format numbers for display in the Flow UI (e.g., 10,000)
            "principal": f"{principal:,.0f}",  
            "duration": str(duration),
            "rate": str(rate),
            "monthly_payment": f"{monthly_payment:,.0f}",
            "total_payment": f"{total_payment:,.0f}",
            "total_interest": f"{total_interest:,.0f}"
        }
    }
    logger.critical(f"{response_screen} is answer➡️ Calculation Complete. Ready to route to LOAN_RESULT.")
    return response_screen


async def whatsapp_menu(data: dict):
    """
    Handles ONLY regular text messages (non-Flow traffic).
    Flow payloads are now expected to be handled by the caller (main.py).
    """
    
    from_number = str(data.get("From") or "")
    # Ensure phone number is in E.164 format for safe use
    if not from_number.startswith("+"):
        from_number = "+" + from_number
        
    payload = data.get("Body")

    # --- Handle Regular Text Message Fallback ---
    if isinstance(payload, str):
        user_text = payload.strip().upper()
        
        # Simple text logic (main menu access)
        if user_text in ["MENU","mambo","hi","hello","anza", "MWANZO"]:
            send_manka_menu_template(to=from_number)
            logger.critical("💬 Regular text: Sending menu template.")
            return JSONResponse({"status": "ok", "message": "Text menu sent"})

        # Fallback for unhandled text
        send_meta_whatsapp_message(
            from_number,
            f"Samahani, sikuelewi '{payload}'. Tuma 'menu' kupata orodha ya huduma."
        )
        send_manka_menu_template(to=from_number)
        logger.critical(f"💬 Regular text: Unhandled text '{payload}'. Sending fallback menu.")
        return JSONResponse({"status": "ok", "message": "Text message handled"})

    # --- Handle Unexpected Flow Payload (Should not be called with dicts anymore) ---
    if isinstance(payload, dict):
        logger.critical("⚠️ whatsapp_menu received an unexpected dictionary payload. Ignoring flow data.")
        send_meta_whatsapp_message(
            from_number,
            "Samahani, nimepoteza mawasiliano na mfumo wa huduma. Tafadhali tuma 'menu' kuanza tena."
        )

    return JSONResponse({"status": "ok"})