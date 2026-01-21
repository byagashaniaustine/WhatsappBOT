import uuid 
import logging
from typing import Optional 

from fastapi.responses import JSONResponse
# *** MODIFIED: Importing send_quick_reply_message ***
from services.meta import send_meta_whatsapp_message, send_manka_menu_template, send_quick_reply_message 
from services.supabase import store_session_data, get_session_phone_by_id 

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)


def calculate_loan(principal: float, duration: int, rate: float):
    """
    Calculate monthly payment, total payment, and total interest for a loan.
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
    Generate Flow UI response for loan calculation results.
    """
    # Retrieve Input Data
    principal = float(user_data.get("principal", 0))
    duration = int(user_data.get("duration", 0))
    rate = float(user_data.get("rate", 0))
    from_number = str(user_data.get("from_number") or "") 
    
    logger.critical(f"✅ Executing Loan Calculation: P={principal}, D={duration}, R={rate} user: {from_number}")

    # Perform Calculation
    try:
        monthly_payment, total_payment, total_interest = calculate_loan(principal, duration, rate)
    except ValueError as e:
        logger.error(f"❌ Calculation failed due to bad input: {e}")
        return {"screen": "MAIN_MENU", "data": {"error": "Invalid input"}}

    # Format and Return Flow Response (for the Flow UI)
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

async def whatsapp_menu(
    payload: str # Accepts the full dict/json payload
):
    """
    Unified WhatsApp message handler. Now primarily focuses on Flow initiation from text.
    Payload expected to contain: {"from_number": "+...", "body": "hi"}
    """
    
    from_number = payload.get("from_number")
    user_text = payload.get("body")
    
    if not from_number or not user_text:
        logger.error("❌ whatsapp_menu received incomplete payload.")
        return 

    # Ensure phone number has + prefix (Redundant check but safe)
    if not from_number.startswith("+"):
        from_number = "+" + from_number
    
    logger.critical(f"📱 whatsapp_menu called for: {from_number} with text: {user_text}")
    
    
    # ========================================================================
    # MODE 2: TEXT MESSAGE HANDLING (Start Flow Session with UUID)
    # ========================================================================
    
    # Normalize user input
    user_text_normalized = user_text.strip().upper()
    
    # Check if it's an initiation keyword
    initiation_keywords = ["MENU", "MAMBO", "HI", "HELLO", "ANZA", "MWANZO", "HOLA", "START", "HEY","NIAMBIE","SALAM"]
    
    if user_text_normalized in initiation_keywords:
        logger.critical(f"🎯 Initiation keyword detected: {user_text_normalized}")
        
        try:
            # 1. GENERATE UNIQUE FLOW TOKEN (UUID)
            new_flow_token = str(uuid.uuid4())
            logger.critical(f"🆕 Generated new flow_token (UUID): {new_flow_token}")

            # 2. STORE PHONE NUMBER AGAINST THIS UUID (The dot connection)
            # Assuming store_session_data is defined as an async function
            session_id = await store_session_data(
                phone_number=from_number, 
                message=user_text, 
                session_id=new_flow_token
            )
            logger.critical(f"💾 Phone stored against UUID/token: {session_id}")
            
            # 3. SEND MENU TEMPLATE, EMBEDDING THE UUID
            # CRITICAL: send_manka_menu_template must be async and imported/defined
            await send_manka_menu_template(to=from_number, flow_token=new_flow_token)
            
            logger.critical(f"✅ Menu template sent to {from_number}, token embedded.")
            
        except Exception as e:
            logger.error(f"❌ Error processing initiation: {e}")
            await send_meta_whatsapp_message(
                from_number,
                "Samahani, tatizo limetokea. Tafadhali jaribu tena."
            )
    
    # Handle unrecognized text
    else:
        logger.critical(f"⚠️ Unrecognized text message: {user_text}")
        
        await send_meta_whatsapp_message(
            from_number,
            f"Samahani, sikuelewi '{user_text}'. Tuma 'MENU', 'MAMBO', 'HI', 'HELLO', 'ANZA', 'MWANZO', 'HOLA', 'START', 'HEY','NIAMBIE','SALAM' kupata huduma."
        )
       