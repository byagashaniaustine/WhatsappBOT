import logging
import mimetypes
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import process_file_upload

logger = logging.getLogger("whatsapp_app")
app = FastAPI()


@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    """
    Handles incoming WhatsApp webhook requests.
    Supports both:
      - Normal text messages → triggers whatsapp_menu
      - Flow form submissions with file uploads → triggers process_file_upload
    """
    try:
        form_data = await request.form()
        data = dict(form_data)

        from_number = str(data.get("From") or "")
        if not from_number:
            logger.warning("Missing 'From' number in request")
            return PlainTextResponse("OK")

        user_id = str(data.get("user_id") or "")
        user_name = str(data.get("user_name") or "")
        flow_type = str(data.get("flow_type") or "")

        # --- Check for media upload ---
        num_media = str(data.get("NumMedia", 0))
        if int(num_media) > 0:
            file_url = str(data.get("MediaUrl0") or "")
            file_type = str(data.get("MediaContentType0") or "")

            if file_url:
                result = process_file_upload(
                    user_id=user_id,
                    user_name=user_name,
                    user_phone=from_number,
                    flow_type=flow_type or "upload_documents",
                    file_url=file_url,
                    file_type=file_type,
                )
                logger.info(f"File upload processed: {result}")
                return PlainTextResponse("OK")

        # --- Otherwise treat as text message ---
        await whatsapp_menu(data)
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error handling WhatsApp webhook: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)
