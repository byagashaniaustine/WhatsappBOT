from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from api.whatsappBOT import whatsapp_menu, process_flow_input as handle_flow_text
from api.whatsappfile import whatsapp_file
from services.twilio import send_message
from services.supabase import store_file  # Supabase metadata storage
import logging

logger = logging.getLogger("whatsapp_webhook")

app = FastAPI()


@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    try:
        content_type = request.headers.get("content-type", "")

        # -------------------------
        # JSON request → Flow data
        # -------------------------
        if "application/json" in content_type:
            flow_data = await request.json()

            user_id = flow_data.get("user_id", "")
            user_name = flow_data.get("user_name", "")
            user_phone = flow_data.get("user_phone", "")
            file_url = flow_data.get("file_url")        # Optional
            file_type = flow_data.get("file_type")      # Optional
            user_text = flow_data.get("user_text")      # Optional structured input
            flow_type = flow_data.get("flow_type", None)

            # -------------------------
            # File uploaded → store & analyze
            # -------------------------
            if file_url:
                try:
                    public_url = store_file(
                        user_id=user_id,
                        user_name=user_name,
                        user_phone=user_phone,
                        flow_type=flow_type,
                        file_url=file_url,
                        file_type=file_type
                    )

                    whatsapp_file_data = {
                        "From": user_phone,
                        "MediaUrl0": public_url,
                        "MediaContentType0": file_type or "",
                        "user_name": user_name
                    }

                    analysis_result = await whatsapp_file(whatsapp_file_data)
                    return {"status": "success", "message": analysis_result}
                except Exception as e:
                    logger.exception("Error storing/analyzing file")
                    return {"status": "error", "message": str(e)}

            # -------------------------
            # Structured text (loan calculator / other flows)
            # -------------------------
            elif user_text:
                try:
                    analysis_result = handle_flow_text(user_text, flow_type)
                    send_message(to=user_phone, body=analysis_result)
                    return {"status": "success", "message": analysis_result}
                except Exception as e:
                    logger.exception("Error handling flow text")
                    return {"status": "error", "message": str(e)}

            return {"status": "error", "message": "No data received from Flow."}

        # -------------------------
        # FormData → Normal WhatsApp messages
        # -------------------------
        else:
            form_data = await request.form()
            form_dict = dict(form_data)
            return await whatsapp_menu(form_dict)

    except Exception as e:
        logger.exception("Unhandled exception in webhook")
        # Always respond 200 OK to Twilio to avoid 502
        return PlainTextResponse("OK")
