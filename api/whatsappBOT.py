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
async def whatsapp_menu(
    data: dict,
    principal: float = None,
    duration: int = None,
    rate: float = None
):
    """
    Single unified logic:
    - User text triggers session creation
    - Inside that block, if principal/duration/rate exist → perform calculation immediately
    - Otherwise show menu
    - Fallback for bad text
    """

    if data:
        current_from_number = str(data.get("From") or "")
        payload = data.get("Body")

        if not current_from_number.startswith("+"):
            current_from_number = "+" + current_from_number

        if isinstance(payload, str):
            user_text = payload.strip().upper()

            initial_words = ["MENU", "MAMBO", "HI", "HELLO", "ANZA", "MWANZO", "HOLA", "HEY"]

            # ----------------------------------------------------------
            # 🎯 MAIN INITIATION: STORE SESSION HERE
            # ----------------------------------------------------------
            if user_text in initial_words and current_from_number:

                # 1. Store session
                session_id = await store_session_data(current_from_number, payload)
                logger.critical(f"💾 New session stored: {session_id}")

                # ------------------------------------------------------
                # 🎯 NESTED SECTION: If P, D, R passed → DO CALC HERE
                # ------------------------------------------------------
                if (
                    session_id 
                    and principal is not None 
                    and duration is not None 
                    and rate is not None
                ):
                    # Fetch phone number using session_id
                    from_number = await get_session_phone_by_id(session_id)

                    if not from_number:
                        logger.error(f"❌ Missing phone for session {session_id}")
                        return JSONResponse({"status": "error", "message": "recipient number missing"})

                    logger.critical(
                        f"📞 Retrieved phone {from_number} for calculation using session {session_id}"
                    )

                    try:
                        monthly_payment, total_payment, total_interest = calculate_loan(
                            principal, duration, rate
                        )

                        msg = (
                            f"Habari!\n"
                            f"Matokeo ya mkopo wako (TZS {principal:,.0f} kwa {duration} miezi):\n\n"
                            f"💰 Malipo ya Kila Mwezi: TZS {monthly_payment:,.0f}\n"
                            f"💵 Jumla ya Kulipa: TZS {total_payment:,.0f}\n"
                            f"📈 Jumla ya Riba: TZS {total_interest:,.0f}"
                        )

                        send_meta_whatsapp_message(from_number, msg)

                        logger.critical(
                            f"📨 Loan results sent to {from_number} inside initiation block"
                        )

                        return JSONResponse({
                            "status": "ok",
                            "session_id": session_id,
                            "message": "calculation sent"
                        })

                    except Exception as e:
                        logger.error(f"❌ Calculation failed: {e}")
                        send_meta_whatsapp_message(
                            from_number,
                            "Samahani, tatizo limetokea wakati wa kukokotoa mkopo."
                        )
                        return JSONResponse({"status": "error", "message": "calc error"})

                # ------------------------------------------------------
                # If no P,D,R → just send menu template (normal behavior)
                # ------------------------------------------------------
                send_manka_menu_template(to=current_from_number)

                return JSONResponse({
                    "status": "ok",
                    "session_id": session_id,
                    "message": "menu sent"
                })

            # ----------------------------------------------------------
            # ⚠️ FALLBACK TEXT
            # ----------------------------------------------------------
            else:
                send_meta_whatsapp_message(
                    current_from_number,
                    f"Samahani, sikuelewi '{payload}'. Tuma 'menu' kupata huduma."
                )
                send_manka_menu_template(to=current_from_number)

                return JSONResponse({
                    "status": "ok",
                    "message": "fallback"
                })

    return JSONResponse({"status": "ok"})
