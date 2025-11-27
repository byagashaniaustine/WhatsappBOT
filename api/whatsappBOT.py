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

# --- NEW HELPER FUNCTION FOR WHATSAPP MESSAGING ---
def send_loan_calculation_whatsapp(from_number: str, principal: float, duration: int, rate: float, monthly_payment: float, total_payment: float):
    """
    Formats the final loan calculation results professionally in Swahili
    and sends them to the user via WhatsApp.
    """
    try:
        # Format numbers for professional display (with commas and no decimals)
        p_formatted = f"{principal:,.0f}"
        mp_formatted = f"{monthly_payment:,.0f}"
        tp_formatted = f"{total_payment:,.0f}"
        rate_formatted = f"{rate}" # Keep rate as provided
        
        # --- Professional Swahili Message Structure ---
        whatsapp_message = (
            "Habari!\n"
            "Tumekamilisha kuhesabu malipo ya mkopo wako. Kulingana na maelezo uliyotoa:\n\n"
            f"Kiasi cha Mkopo (Principal): **TZS {p_formatted}**\n"
            f"Muda wa Kurejesha: **{duration} miezi**\n"
            f"Riba kwa Mwezi: **{rate_formatted}%**\n\n"
            
            "Malipo yako ya kila mwezi yatakuwa:\n"
            "💰 **TZS "
            f"{mp_formatted}"
            "**\n\n"
            
            f"Jumla ya kiasi utakachorejesha (Total Repayment): TZS {tp_formatted}.\n\n"
            "Tafadhali jibu 'NDIYO' ili kuendelea na mchakato wa maombi ya mkopo, au 'MENU' kurudi kwenye huduma zetu. Asante kwa kutumia huduma ya Manka."
        )

        send_meta_whatsapp_message(from_number, whatsapp_message)
        logger.critical(f"✅ WhatsApp Message Sent: Loan results for P={p_formatted} sent to {from_number}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send loan result WhatsApp message: {e}")

# --- MODIFIED CORE HANDLER ---
def calculate_loan_results(user_data: dict):
    """
    Performs the loan calculation, sends the WhatsApp message, 
    and formats the response dictionary to advance the Flow to LOAN_RESULT.
    
    Note: 'From' (phone number) and 'data' (form input) are expected in user_data.
    """
    
    # 1. Retrieve Input Data
    principal = float(user_data.get("principal", 0))
    duration = int(user_data.get("duration", 0))
    rate = float(user_data.get("rate", 0))
    from_number = str(user_data.get("From") or "") # Get the client's number
    
    if not from_number.startswith("+"):
        from_number = "+" + from_number
    
    logger.critical(f"✅ Executing Loan Calculation: P={principal}, D={duration}, R={rate}")

    # 2. Perform Calculation
    try:
        monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)
    except ValueError as e:
        logger.error(f"❌ Calculation failed due to bad input: {e}")
        # Return an error screen or re-route if necessary, but for simplicity, we return the Flow structure
        return {"screen": "MAIN_MENU", "data": {"error": "Invalid input"}}

    # 3. Send WhatsApp Message (Immediate Action)
    send_loan_calculation_whatsapp(from_number, principal, duration, rate, monthly_payment, total_payment)

    # 4. Format and Return Flow Response (To display LOAN_RESULT screen)
    response_screen = {
        "screen": "LOAN_RESULT", # The screen ID in the Flow JSON to display results
        "data": {
            # Format numbers for display in the Flow UI (e.g., 10,000)
            # The Flow JSON (v7.2) will use these fields: ${data.monthly_payment}
            "principal": f"{principal:,.0f}",  
            "duration": str(duration),
            "rate": str(rate),
            "monthly_payment": f"{monthly_payment:,.0f}",
            "total_payment": f"{total_payment:,.0f}",
            "total_interest": f"{total_interest:,.0f}"
        }
    }
    
    logger.critical(f"Flow routing answer: {response_screen} ➡️ Calculation Complete. Ready to route to LOAN_RESULT.")
    return response_screen


async def whatsapp_menu(data: dict):
    # (Existing function remains unchanged)
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
        else:
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