import logging
import mimetypes
import requests

from services.supabase import store_file
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message

logger = logging.getLogger(__name__)

def process_file_upload(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_url: str,
    file_type: str
):
    """
    Handles WhatsApp file uploads (images or PDFs) submitted through Flow Forms.

    - Stores file in Supabase
    - Analyzes via Gemini or MANKA API
    - Sends result back via WhatsApp
    """

    try:
        # --- Detect file type ---
        mime_type = file_type or mimetypes.guess_type(file_url)[0] or ""
        is_pdf = "pdf" in mime_type.lower()
        is_image = any(ext in mime_type.lower() for ext in ["image", "jpeg", "png", "jpg", "webp"])

        logger.info(f"Processing file from {user_phone}: {mime_type}")

        # --- Store file in Supabase ---
        stored_path = store_file(file_url, user_id)
        logger.info(f"File stored at: {stored_path}")

        # --- Download file content ---
        response = requests.get(file_url)
        response.raise_for_status()
        file_data = response.content

        # --- Prepare filename ---
        filename = file_url.split("/")[-1] or "uploaded_file"

        # --- Analyze file content ---
        if is_image:
            logger.info("Analyzing image via Gemini...")
            analysis_result = analyze_image(file_url)

            if isinstance(analysis_result, dict):
                summary = analysis_result.get("summary", "No summary generated.")
            else:
                summary = str(analysis_result)

            response_text = (
                f"📸 *Image analyzed successfully!*\n\n"
                f"**Summary:** {summary}"
            )

        elif is_pdf:
            logger.info("Analyzing PDF via MANKA API...")
            analysis_result = analyze_pdf(file_data, filename, user_name)

            if isinstance(analysis_result, dict):
                summary = analysis_result.get("summary", "No summary generated.")
            else:
                summary = str(analysis_result)

            response_text = (
                f"📄 *PDF analyzed successfully!*\n\n"
                f"{summary}"
            )

        else:
            logger.warning(f"Unsupported file type: {mime_type}")
            response_text = (
                f"⚠️ Unsupported file type: {mime_type}.\n"
                f"Please upload an image or PDF document."
            )

        # --- Send WhatsApp confirmation ---
        send_message(user_phone, response_text)

        return {
            "status": "success",
            "file_type": mime_type,
            "stored_path": stored_path,
            "response_text": response_text
        }

    except Exception as e:
        logger.exception(f"Error processing file upload for {user_phone}: {str(e)}")
        error_text = f"❌ Error analyzing your file: {str(e)}"
        send_message(user_phone, error_text)

        return {"status": "error", "message": str(e)}
