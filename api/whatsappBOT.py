from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
# 🎯 CORRECTED IMPORTS: Using the ID-based functions defined in the service file.
from services.supabase import store_session_data, get_session_phone_by_id
import logging

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)


def calculate_loan(principal: float, duration: int, rate: float):
    # ... (calculate_loan body remains unchanged) ...
    
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
    # ... (Function remains the same, used to generate Flow UI response) ...
    
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

async def whatsapp_handler(
    data: dict, 
    principal: float = None, 
    duration: int = None, 
    rate: float = None
):
    """
    Handles: 
    1. Initial text messages (stores session, sends menu).
    2. Synchronous loan calculation/message sending (if P, D, R are passed).
    """

    from_number = str(data.get("From") or "")
    if not from_number.startswith("+"):
        from_number = "+" + from_number
        
    payload = data.get("Body")
    
    
    # ----------------------------------------------------------------------
    # 1. LOAN CALCULATION (SYNCHRONOUSLY TRIGGERED BY FLOW DATA)
    # ----------------------------------------------------------------------
    if principal is not None and duration is not None and rate is not None:
        # The from_number is passed in 'data' dictionary from main.py
        
        logger.critical(f"✅ Executing SYNC Loan Calculation: P={principal}, D={duration}, R={rate} user: {from_number}")
        
        try:
            monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)
            
            # Format and build message
            message_text = (
                f"Habari!\n"
                f"Matokeo ya mkopo wako (TZS {principal:,.0f} kwa {duration} miezi) yamekamilika:\n\n"
                f"💰 **Malipo ya Kila Mwezi:** TZS {monthly_payment:,.0f}\n"
                f"Jumla ya Riba: TZS {total_interest:,.0f}\n"
                f"Jumla ya Kulipa: TZS {total_payment:,.0f}\n\n"
                f"Matokeo haya yatumwa kwa njia ya ujumbe kama matokeo ya maombi yako ya Flow."
            )
            
            # 🎯 ACTION: Send WhatsApp message synchronously
            send_meta_whatsapp_message(from_number, message_text)
            logger.critical(f"💬 Sent sync loan results to {from_number}")
            
            return JSONResponse({"status": "ok", "message": "Calculation message sent"})
            
        except ValueError as e:
            logger.error(f"❌ Calculation failed due to bad input: {e}")
            send_meta_whatsapp_message(from_number, "Samahani, tafadhali jaza nambari sahihi kwa hesabu.")
            return JSONResponse({"status": "error", "message": "Invalid input"})
            
        except Exception as e:
            logger.error(f"❌ General error in sending loan results: {e}")
            send_meta_whatsapp_message(from_number, "Samahani, hitilafu imetokea wakati wa kutuma matokeo.")
            return JSONResponse({"status": "error", "message": "Internal error"})
 
    # ----------------------------------------------------------------------
    # 2. INITIAL GREETING/SESSION INITIATION (Text message)
    # ----------------------------------------------------------------------
    if isinstance(payload, str):
        user_text = payload.strip().upper()
        
        initial_contact_words = ["MENU", "MAMBO", "HI", "HELLO", "ANZA", "MWANZO", "HOLA", "HEY"]
        
        if user_text in initial_contact_words and from_number:
            # 🎯 ACTION: Store session immediately
            session_id = await store_session_data(phone_number=from_number, message=payload) 
            logger.critical(f"💾 Session data stored. ID: {session_id}")
            
            # Send initial menu template
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
        logger.critical("⚠️ whatsapp_handler received an unexpected dictionary payload. Ignoring flow data.")
        send_meta_whatsapp_message(
            from_number,
            "Samahani, nimepoteza mawasiliano na mfumo wa huduma. Tafadhali tuma 'menu' kuanza tena."
        )

    return JSONResponse({"status": "ok"})