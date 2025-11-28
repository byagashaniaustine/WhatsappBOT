import uuid # <-- NEW: Import uuid for session token generation
import logging
from typing import Optional # <-- NEW: Import Optional for clearer type hints

from fastapi.responses import JSONResponse
from services.meta import send_meta_whatsapp_message, send_manka_menu_template
from services.supabase import store_session_data, get_session_phone_by_id # Assumed to be imported
# NOTE: We assume 'store_session_data' has been modified to accept an optional 'session_id' (the UUID)

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.DEBUG)


def calculate_loan(principal: float, duration: int, rate: float):
    """
    Calculate monthly payment, total payment, and total interest for a loan.
    
    Args:
        principal: Loan amount
        duration: Loan duration in months
        rate: Monthly interest rate as a percentage
        
    Returns:
        tuple: (monthly_payment, total_payment, total_interest)
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
    This function is called to prepare the LOAN_RESULT screen data.
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
    from_number: str,
    principal: Optional[float] = None, # Added Optional type hint
    duration: Optional[int] = None,    # Added Optional type hint
    rate: Optional[float] = None,      # Added Optional type hint
    user_text: Optional[str] = None    # Added Optional type hint
):
    """
    Unified WhatsApp message handler.
    """
    
    # Ensure phone number has + prefix
    if not from_number.startswith("+"):
        from_number = "+" + from_number
    
    logger.critical(f"📱 whatsapp_menu called for: {from_number}")
    
    # ========================================================================
    # MODE 1: LOAN CALCULATION (from Flow background task)
    # ========================================================================
    if principal is not None and duration is not None and rate is not None:
        logger.critical(f"🧮 LOAN CALCULATION MODE activated")
        # ... (Calculation and sending logic remains the same) ...
        
        try:
            # Perform calculation
            monthly_payment, total_payment, total_interest = calculate_loan(
                principal, duration, rate
            )
            
            # Format message in Swahili
            msg = (
                f"Habari!\n"
                f"Matokeo ya mkopo wako (TZS {principal:,.0f} kwa {duration} miezi):\n\n"
                f"💰 Malipo ya Kila Mwezi: TZS {monthly_payment:,.0f}\n"
                f"💵 Jumla ya Kulipa: TZS {total_payment:,.0f}\n"
                f"📈 Jumla ya Riba: TZS {total_interest:,.0f}"
            )
            
            # Send the message
            send_meta_whatsapp_message(from_number, msg)
            
            logger.critical(f"✅ Loan calculation results sent to {from_number}")
            
            return JSONResponse({
                "status": "ok",
                "message": "calculation sent",
                "to": from_number
            })
            
        except ValueError as ve:
            logger.error(f"❌ Invalid loan parameters: {ve}")
            send_meta_whatsapp_message(
                from_number,
                "Samahani, thamani ulizoweka si sahihi. Tafadhali jaribu tena."
            )
            return JSONResponse({"status": "error", "message": "invalid parameters"})
            
        except Exception as e:
            logger.error(f"❌ Calculation failed: {e}", exc_info=True)
            send_meta_whatsapp_message(
                from_number,
                "Samahani, tatizo limetokea wakati wa kukokotoa mkopo."
            )
            return JSONResponse({"status": "error", "message": "calculation error"})
    
    # ========================================================================
    # MODE 2: TEXT MESSAGE HANDLING (Start Flow Session with UUID)
    # ========================================================================
    elif user_text:
        logger.critical(f"💬 TEXT MESSAGE MODE activated")
        
        # Normalize user input
        user_text_normalized = user_text.strip().upper()
        
        # Check if it's an initiation keyword
        initiation_keywords = ["MENU", "MAMBO", "HI", "HELLO", "ANZA", "MWANZO", "HOLA", "HEY"]
        
        if user_text_normalized in initiation_keywords:
            logger.critical(f"🎯 Initiation keyword detected: {user_text_normalized}")
            
            try:
                # 1. GENERATE UNIQUE FLOW TOKEN (UUID)
                new_flow_token = str(uuid.uuid4())
                logger.critical(f"🆕 Generated new flow_token (UUID): {new_flow_token}")

                # 2. STORE PHONE NUMBER AGAINST THIS UUID (The dot connection)
                # NOTE: This assumes store_session_data is modified to accept session_id
                session_id = await store_session_data(
                    phone_number=from_number, 
                    message=user_text, 
                    session_id=new_flow_token
                )
                logger.critical(f"💾 Phone stored against UUID/token: {session_id}")
                
                # 3. SEND MENU TEMPLATE, EMBEDDING THE UUID
                # This ensures the UUID returns in the 'flow_token' field of the webhook.
                send_manka_menu_template(to=from_number, flow_token=new_flow_token)
                
                logger.critical(f"✅ Menu template sent to {from_number}, token embedded.")
                
                return JSONResponse({
                    "status": "ok",
                    "session_id": session_id,
                    "message": "menu sent"
                })
                
            except Exception as e:
                logger.error(f"❌ Error processing initiation: {e}", exc_info=True)
                send_meta_whatsapp_message(
                    from_number,
                    "Samahani, tatizo limetokea. Tafadhali jaribu tena."
                )
                return JSONResponse({"status": "error", "message": "session error"})
        
        # Handle unrecognized text
        else:
            logger.critical(f"⚠️ Unrecognized text message: {user_text}")
            
            send_meta_whatsapp_message(
                from_number,
                f"Samahani, sikuelewi '{user_text}'. Tuma 'menu' kupata huduma."
            )
            
            # Also send menu template as fallback (using a generic token)
            send_manka_menu_template(to=from_number, flow_token="fallback")
            
            return JSONResponse({
                "status": "ok",
                "message": "fallback response sent"
            })
    
    # ========================================================================
    # MODE 3: INVALID CALL (no parameters provided)
    # ========================================================================
    else:
        logger.error("❌ whatsapp_menu called with no valid parameters")
        return JSONResponse({
            "status": "error",
            "message": "no valid parameters provided"
        })