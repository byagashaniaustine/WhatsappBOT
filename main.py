import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import math
from typing import Dict, Any
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload # handles Supabase storage & analysis

from services.twilio import send_message

logger = logging.getLogger("whatsapp_app")
app = FastAPI()

# Placeholder for store_loan_result if not imported
def store_loan_result(data: Dict[str, Any]):
    """Placeholder function for storing loan results, assumes implementation elsewhere."""
    logger.info(f"Storing loan result data: {data}")

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    try:
        data = await request.form()
        payload = dict(data)

        from_number = str(payload.get("From") or "")
        if not from_number:
            logger.warning("⚠️ Missing 'From' number in request")
            return PlainTextResponse("OK")

        # Call WhatsApp menu
        await whatsapp_menu(payload)
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error handling WhatsApp webhook: {e}")
        return PlainTextResponse("Internal Server Error", status_code=500)

@app.post("/google-form-webhook/")
async def google_form_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"📨 Received Google Form data: {data}")

        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone") or data.get("phone_number")
        file_id = data.get("file_url")

        if not phone:
            raise ValueError("Phone number missing from form submission.")

        # --- Process file via whatsappfile.py ---
        if file_id:
            result = process_file_upload(
                user_id=email or "unknown",
                user_name=name or "unknown",
                user_phone=phone,
                flow_type="google_form_upload",
                drive_file_id=file_id
            )
            logger.info(f"File processed: {result}")
        else:
            # If no file, just send acknowledgement
            send_message(
                to_phone=phone,
                message=f"Halo {name}, tumepokea taarifa zako. Hakuna faili lililowasilishwa."
            )
            result = {"status": "success", "message": "No file submitted."}

        return JSONResponse({"status": "success", "data": result})

    except Exception as e:
        logger.exception(f"❌ Error processing form submission: {e}")
        return JSONResponse({"status": "error", "details": str(e)}, status_code=500)

@app.post("/loan-calculator/")
async def loan_calculator(request: Request):
    """
    Calculates the maximum possible Principal (Loan Amount) a user can get 
    based on their comfortable Monthly Repayment capacity, Term, and Rate.
    """
    data = {} # Initialize data outside try for error handling access
    try:
        data = await request.json()
        logger.info(f"📨 Loan calculation data received: {data}")

        # 1. EXTRACT USER INFO
        user_phone = data.get("phone")
        user_name = data.get("name", "Mteja")
        
        # Essential validation for feedback
        if not user_phone:
             # This check fails if the key 'phone' is missing or its value is None/empty string
             return JSONResponse({"status": "error", "details": "Missing phone number for feedback. Check if 'phone' key exists in payload."}, status_code=400)

        # 2. EXTRACT & CONVERT CALCULATION PARAMETERS using normal float parsing
        
        # Safely get string values for validation
        monthly_repayment_capacity_str = data.get("amount")
        duration_str = data.get("duration_months")
        rate_str = data.get("rate")

        # Explicitly check for missing parameters before attempting float conversion
        if not monthly_repayment_capacity_str:
             raise ValueError("Monthly repayment capacity ('amount') is missing or empty.")
        if not duration_str:
             raise ValueError("Loan duration ('duration_months') is missing or empty.")
        if not rate_str:
             raise ValueError("Interest rate ('rate') is missing or empty.")

        # Convert using normal float() function. This will raise a ValueError if the string is non-numeric.
        monthly_repayment_capacity = float(monthly_repayment_capacity_str)
        # Convert duration via float() then int() to handle both string and potential float input
        duration = int(float(duration_str))
        rate = float(rate_str) # Annual Rate (%)

        logger.info(f"📊 Extracted values: Capacity={monthly_repayment_capacity}, Duration={duration}, Rate={rate}")

        # 3. PERFORM INVERTED AMORTIZATION CALCULATION
        
        if duration <= 0:
            raise ValueError("Duration (loan term) must be greater than zero months.")
        
        # Convert annual percentage rate (R) to monthly decimal rate (r)
        monthly_rate = (rate / 100) / 12

        if monthly_rate == 0:
            # Simple calculation if interest is zero
            principal = monthly_repayment_capacity * duration
            total_interest = 0
            
        else:
            # Inverted Amortization Formula to solve for Principal (P):
            # P = M * [ (1 + r)^n - 1 ] / [ r * (1 + r)^n ]
            
            # Common factor: (1 + r)^n
            common_factor = math.pow((1 + monthly_rate), duration)

            # Calculate Principal (P)
            principal = monthly_repayment_capacity * ((common_factor - 1) / (monthly_rate * common_factor))
            
            # Calculate Total Metrics
            total_payment = monthly_repayment_capacity * duration
            total_interest = total_payment - principal

        # 4. PREPARE RESULT OBJECT
        total_payment = monthly_repayment_capacity * duration
        
        result_data = {
            "principal_calculated": principal, # The maximum loan amount the user can get
            "monthly_repayment_capacity": monthly_repayment_capacity, # Input (M)
            "total_interest": total_interest,
            "total_payment": total_payment,
            "duration_months": duration,
            "rate": rate,
            "name": user_name,
            "phone": user_phone,
            "flow_type": data.get("flow_type", "loan_calculator")
        }
        logger.info(f"💰 Loan calculation result: {result_data}")
        
        # 5. FORMAT AND SEND FEEDBACK MESSAGE (IN SWAHILI)
        result_message = (
            f"Habari {user_name},\n\n"
            f"Matokeo ya kiwango cha mkopo unaoweza kupata:\n"
            f"----------------------------------\n"
            f"Uwezo Wako wa Kurejesha Kila Mwezi: {monthly_repayment_capacity:,.2f}\n"
            f"Kiwango cha Riba: {rate:,.2f}%\n"
            f"Muda wa Mkopo: {duration} miezi\n\n"
            f"🚀 *Kiwango cha Juu cha Mkopo Unachoweza Kupata (Principal):* {principal:,.2f}\n"
            f"Jumla ya Marejesho (kwa miezi {duration}): {total_payment:,.2f}\n"
            f"Jumla ya Riba Uliyolipa: {total_interest:,.2f}"
        )

        send_message(user_phone, result_message)
        
        # 6. STORE RESULT
        store_loan_result(result_data)
        
        # 7. RETURN SUCCESS
        return JSONResponse({"status": "success", "message": "Affordability calculated and feedback sent.", "data": result_data})

    except ValueError as ve:
        error_msg = f"Invalid loan data provided. Details: {str(ve)}"
        logger.exception(f"❌ Value Error in loan calculation: {error_msg}")
        # Send error message in Swahili
        error_swahili = "❌ Samahani: Tafadhali hakikisha viwango vyote ni namba sahihi na muda wa mkopo ni zaidi ya sifuri."
        send_message(data.get("phone", ""), error_swahili)
        return JSONResponse({"status": "error", "details": error_msg}, status_code=400)

    except Exception as e:
        logger.exception(f"❌ Critical Error calculating loan: {e}")
        # Send critical error message in Swahili
        error_swahili = "❌ Samahani, kuna tatizo kubwa la kiufundi limetokea wakati wa kuhesabu mkopo. Tafadhali jaribu tena baadaye."
        send_message(data.get("phone", ""), error_swahili)
        return JSONResponse({"status": "error", "details": str(e)}, status_code=500)
