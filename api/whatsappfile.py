import logging
import mimetypes
import requests
from typing import Optional

from services.supabase import store_file
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
ALLOWED_PDF_TYPE = "application/pdf"


def process_file_upload(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_url: str,
    file_type: Optional[str] = None
) -> dict:
    """
    Handles file uploads from Google Forms or WhatsApp flows:
      - Stores file in Supabase
      - Analyzes image via Gemini or PDF via MANKA API
      - Sends analysis summary via WhatsApp
    """
    try:
        # --- Validate required fields ---
        if not all([user_id, user_name, user_phone, flow_type, file_url]):
            raise ValueError("Missing required parameters for file processing.")

        # --- Detect MIME type ---
        mime_type = file_type or mimetypes.guess_type(file_url)[0] or ""
        mime_type = mime_type.lower()
        is_pdf = mime_type == ALLOWED_PDF_TYPE
        is_image = mime_type in ALLOWED_IMAGE_TYPES

        logger.info(f"Processing file for {user_phone} | MIME: {mime_type}")

        # --- Store file in Supabase ---
        stored_url = store_file(
            user_id=user_id,
            user_name=user_name,
            user_phone=user_phone,
            flow_type=flow_type,
            file_url=file_url,
            file_type=mime_type
        )
        if not stored_url:
            raise ValueError("Failed to store file in Supabase.")

        logger.info(f"✅ File stored at: {stored_url}")

        # --- Download file for analysis ---
        response = requests.get(stored_url, timeout=30)
        response.raise_for_status()
        file_data = response.content
        filename = stored_url.split("/")[-1] or "uploaded_file"

        # --- Analyze file content ---
        if is_image:
            logger.info("Analyzing image via Gemini...")
            analysis_result = analyze_image(stored_url)
            summary = analysis_result.get("summary") if isinstance(analysis_result, dict) else str(analysis_result)
            response_text = f"📸 *Image analyzed successfully!*\n\n**Summary:** {summary}"

        elif is_pdf:
            logger.info("Analyzing PDF via MANKA API...")
            analysis_result = analyze_pdf(file_data, filename, user_name)
            summary = analysis_result.get("summary") if isinstance(analysis_result, dict) else str(analysis_result)
            response_text = f"📄 *PDF analyzed successfully!*\n\n{summary}"

        else:
            logger.warning(f"Unsupported file type: {mime_type}")
            response_text = f"⚠️ Unsupported file type: {mime_type}. Please upload an image or PDF."

        # --- Send WhatsApp confirmation ---
        send_message(user_phone, response_text)

        return {
            "status": "success",
            "file_type": mime_type,
            "stored_url": stored_url,
            "response_text": response_text
        }

    except Exception as e:
        logger.exception(f"❌ Error processing file upload for {user_phone}: {e}")
        send_message(user_phone, f"❌ Error analyzing your file: {str(e)}")
        return {"status": "error", "message": str(e)}
