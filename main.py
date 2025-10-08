import logging
import mimetypes
from fastapi import FastAPI, Request, UploadFile
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

        # --- Extract basic info ---
        from_number: str = str(data.get("From") or "")
        if not from_number:
            logger.warning("Missing 'From' number in request")
            return PlainTextResponse("OK")

        user_id = str(data.get("user_id"))
        user_name = str(data.get("user_name"))
        flow_type = str(data.get("flow_type"))

        # --- Handle file upload if present ---
        uploaded_file = str(data.get("Media"))  # can be UploadFile or string URL
        file_url: str | None = None
        file_type: str | None = None

        if uploaded_file:
            if isinstance(uploaded_file, UploadFile):
                file_url = uploaded_file.filename
                file_type = uploaded_file.content_type
            elif isinstance(uploaded_file, str):
                file_url = uploaded_file
                file_type = None  # unknown MIME type
            else:
                logger.warning(f"Unsupported Media type: {type(uploaded_file)}")

        if file_url:
            # Process the uploaded file
            result = process_file_upload(
                user_id=user_id,
                user_name=user_name,
                user_phone=from_number,
                flow_type=flow_type,
                file_url=file_url,
                file_type=file_type or "",
            )
            logger.info(f"File upload processed: {result}")
            return PlainTextResponse("OK")

        # --- If no file, treat as normal text message ---
        await whatsapp_menu(data)
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error handling WhatsApp webhook: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)
