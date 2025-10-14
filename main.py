# main.py
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload  # handles Supabase storage & analysis

from services.twilio import send_message

logger = logging.getLogger("whatsapp_app")
app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    """
    Handles incoming messages from Twilio WhatsApp.
    Menu logic and basic text interactions.
    """
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
                file_id=file_id
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


# -----------------------------------------------
# 3️⃣ LOAN CALCULATOR ROUTE
# -----------------------------------------------
@app.post("/loan-calculator/")
async def loan_calculator(request: Request):
    """
    Handles loan calculation requests.
    Expected JSON: { amount, duration_months, rate }
    """
    try:
        data = await request.json()
        logger.info(f"📨 Loan calculation data: {data}")

        amount = float(data.get("amount", 0))
        duration = int(data.get("duration_months", 0))
        rate = float(data.get("rate", 0))

        # Simple interest calculation
        interest = (amount * rate * duration) / 100
        total_payment = amount + interest

        result = {
            "principal": amount,
            "interest": interest,
            "total_payment": total_payment,
            "duration_months": duration,
            "rate": rate,
        }

        logger.info(f"💰 Loan calculation result: {result}")
        return JSONResponse({"status": "success", "data": result})

    except Exception as e:
        logger.exception(f"❌ Error calculating loan: {e}")
        return JSONResponse({"status": "error", "details": str(e)}, status_code=500)
