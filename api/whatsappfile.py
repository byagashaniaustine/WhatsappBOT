import logging
import mimetypes
import requests
from typing import Optional
from services.supabase import store_file
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message
from services.drive_services import get_file_metadata, download_file_from_drive

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
ALLOWED_PDF_TYPE = "application/pdf"

logger = logging.getLogger(__name__)

def process_file_upload(user_id, user_name, user_phone, flow_type, file_id):
    try:
        # --- Get file metadata ---
        file_name, mime_type = get_file_metadata(file_id)
        logger.info(f"File name: {file_name}, MIME: {mime_type}")

        # --- Download file bytes ---
        file_data = download_file_from_drive(file_id)

        # --- Store in Supabase ---
        stored_url = store_file(
            user_id=user_id,
            user_name=user_name,
            user_phone=user_phone,
            flow_type=flow_type,
            file_url=file_name,  # or temporary path
            file_type=mime_type
        )

        # --- Analyze based on MIME type ---
        if mime_type == "application/pdf":
            result = analyze_pdf(file_data, file_name, user_name)
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            message = f"📄 *PDF analyzed successfully!*\n\n{summary}"
        elif mime_type.startswith("image/"):
            result = analyze_image(stored_url)
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            message = f"📸 *Image analyzed successfully!*\n\n{summary}"
        else:
            message = f"⚠️ Unsupported file type: {mime_type}"

        send_message(user_phone, message)
        return {"status": "success", "summary": message}

    except Exception as e:
        logger.exception(f"❌ Error processing Drive file: {e}")
        send_message(user_phone, f"❌ Error analyzing your file: {str(e)}")
        return {"status": "error", "message": str(e)}
