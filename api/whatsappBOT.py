from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
# 🎯 CORRECTED IMPORTS: Using the ID-based functions defined in the service file.
from services.supabase import store_session_data, get_session_phone_by_id
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)


def calculate_loan(principal: float, duration: int, rate: float):
    """
    Calculate monthly payment, total payment, and total interest.
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
             monthly_payment = principal / duration
        else:
            numerator = i * (1 + i)**n
            monthly_payment = principal * (numerator / denominator)

    total_payment = monthly_payment * duration
    total_interest = total_payment - principal
    
    return monthly_payment, total_payment, total_interest


def calculate_loan_results(user_data: dict):
    """
    Performs the loan calculation and formats the response dictionary to advance 
    the Flow to LOAN_RESULT screen.
    """
    
    # 1. Retrieve Input Data
    principal = float(user_data.get("principal", 0))
    duration = int(user_data.get("duration", 0))
    rate = float(user_data.get("rate", 0))
    from_number = str(user_data.get("From") or "") 
    
    if not from_number.startswith("+"):
        from_number = "+" + from_number
    
    logger.critical(f"✅ Executing Loan Calculation: P={principal}, D={duration}, R={rate} user: {from_number}")

    # 2. Perform Calculation
    try:
        monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)
    except ValueError as e:
        logger.error(f"❌ Calculation failed due to bad input: {e}")
        return {"screen": "MAIN_MENU", "data": {"error": "Invalid input"}}

    # 3. Format and Return Flow Response (for the Flow UI)
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
    
    logger.critical(f"Flow routing answer: {response_screen} ➡️ Calculation Complete. Ready to route to LOAN_RESULT.")
    return response_screen


async def send_loan_results(id :str, user_data: dict):
    """
    🎯 FLOW BACKGROUND TASK HANDLER 🎯
    Retrieves the phone number using the stored session ID (id) and sends the results.
    """
    
    # 1. Retrieve Phone Number using Session ID
    # 🎯 FIX: Use await with the correct ID-based retrieval function.
    from_number = await get_session_phone_by_id(id) 
    
    if not from_number:
        logger.error(f"❌ Failed to retrieve phone number for session ID: {id}. Cannot send message.")
        return
    
    logger.critical(f"✅ Preparing to send loan results to recovered number: {from_number} (Session ID: {id})")

    # 2. Calculate Results
    try:
        principal = float(user_data.get("principal", 0))
        duration = int(user_data.get("duration", 0))
        rate = float(user_data.get("rate", 0))
        
        monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)
        
        # Format strings for the message
        monthly_payment_str = f"{monthly_payment:,.0f}"
        total_payment_str = f"{total_payment:,.0f}"
        total_interest_str = f"{total_interest:,.0f}"

        # 3. Prepare and Send WhatsApp message
        message_text = (
            f"Habari!\n"
            f"Matokeo ya mkopo wako yamekamilika:\n\n"
            f"💰 **Malipo ya Kila Mwezi:** TZS {monthly_payment_str}\n"
            f"Jumla ya Riba: TZS {total_interest_str}\n"
            f"Jumla ya Kulipa: TZS {total_payment_str}\n\n"
            f"Tafadhali angalia skrini yako ya WhatsApp kwa muhtasari na hatua inayofuata."
        )
        
        send_meta_whatsapp_message(from_number, message_text)
        logger.critical(f"💬 Sent loan results to {from_number} successfully.")
        
    except ValueError:
        logger.error(f"❌ Calculation failed for flow data: Invalid numeric input.")
        send_meta_whatsapp_message(from_number, "Samahani, tafadhali jaza nambari sahihi kwa hesabu.")
    except Exception as e:
        logger.error(f"❌ General error in sending loan results: {e}")
        send_meta_whatsapp_message(from_number, "Samahani, hitilafu imetokea wakati wa kutuma matokeo.")


async def whatsapp_menu(data: dict, user_data: dict = None):
    """
    Handles regular text messages and stores the session data upon contact.
    """
   
    from_number = str(data.get("From") or "")
    if not from_number.startswith("+"):
        from_number = "+" + from_number
        
    payload = data.get("Body")
    
    # --- Handle Regular Text Message Fallback ---
    if isinstance(payload, str):
        user_text = payload.strip().upper()
        
        initial_contact_words = ["MENU", "MAMBO", "HI", "HELLO", "ANZA", "MWANZO"]
        
        # 🎯 STORAGE: Store the number and message (using await for the async function)
        if user_text in initial_contact_words and from_number:
            session_id = await store_session_data(from_number, payload)
            logger.critical(f"💾 Session stored. ID: {session_id}")
        
        # Simple text logic (main menu access)
        if user_text in initial_contact_words:
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
 
    # --- Handle Unexpected Flow Payload ---
    if isinstance(payload, dict):
        logger.critical("⚠️ whatsapp_menu received an unexpected dictionary payload. Ignoring flow data.")
        send_meta_whatsapp_message(
            from_number,
            "Samahani, nimepoteza mawasiliano na mfumo wa huduma. Tafadhali tuma 'menu' kuanza tena."
        )

    return JSONResponse({"status": "ok"})