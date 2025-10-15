import logging
import mimetypes
import requests
from typing import Optional
from services.supabase import store_file
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message
from services.drive_service import get_file_metadata, download_file_from_drive

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
ALLOWED_PDF_TYPE = "application/pdf"

def process_file_upload(user_id, user_name, user_phone, flow_type, drive_file_id):
    """
    Processes a file uploaded via Google Drive ID. 
    Analysis (PDF/Image) is performed BEFORE the file is stored in Supabase.
    """
    try:
        # 1. Get file metadata (using the Drive ID)
        file_name, mime_type = get_file_metadata(drive_file_id)
        logger.info(f"File name: {file_name}, MIME: {mime_type}")

        # 2. Download file bytes (Done once for analysis and storage)
        file_data = download_file_from_drive(drive_file_id)
        
        analysis_summary = None
        
        # --- 3. Analyze based on MIME type (Analysis runs BEFORE storage) ---
        if mime_type == ALLOWED_PDF_TYPE:
            logger.info("Starting PDF analysis...")
            result = analyze_pdf(file_data, file_name, user_name)
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            analysis_summary = f"📄 *PDF analyzed successfully!*\n\n{summary}"
        
        elif mime_type in ALLOWED_IMAGE_TYPES:
            logger.info("Starting image analysis using raw file data...")
            # NOTE: To fulfill the requirement of analyzing *before* storing, 
            # we are now passing the raw file bytes (file_data) to analyze_image(). 
            # The underlying `analyze_image` service must be capable of accepting 
            # bytes (e.g., as base64 data) instead of relying on a public URL.
            result = analyze_image(file_data)
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            analysis_summary = f"📸 *Image analyzed successfully!*\n\n{summary}"

        elif mime_type not in ALLOWED_IMAGE_TYPES and mime_type != ALLOWED_PDF_TYPE:
            message = f"⚠️ Unsupported file type: {mime_type}. Skipping storage."
            send_message(user_phone, message)
            return {"status": "unsupported", "message": message}
            
        # --- 4. Store in Supabase (Only if analysis/file type check passed) ---
        logger.info("Starting file storage in Supabase...")
        stored_result = store_file(
            user_id=user_id,
            user_name=user_name,
            user_phone=user_phone,
            flow_type=flow_type,
            drive_file_id=drive_file_id,
            file_data=file_data,
            mime_type=mime_type
       )
        
        if not stored_result or 'file_url' not in stored_result:
             # If analysis_summary was set, we preserve it, but send an error about storage.
             raise Exception("Failed to store file and retrieve public URL.")
             
        stored_url = stored_result['file_url']
        logger.info(f"File stored successfully at URL: {stored_url}")

        # 5. Send final message and return
        final_message = analysis_summary if analysis_summary else "✅ File uploaded and stored successfully. No analysis was required."
        send_message(user_phone, final_message)
        
        return {"status": "success", "summary": final_message}

    except Exception as e:
        logger.exception(f"❌ Error processing Drive file: {e}")
        send_message(user_phone, f"❌ Error analyzing or storing your file: {str(e)}")
        return {"status": "error", "message": str(e)}
