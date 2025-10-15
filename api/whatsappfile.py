import logging
import mimetypes
import requests
import uuid 
import os # Import necessary for environment variable access
from typing import Optional
from services.supabase import store_file
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message
# Google Drive services zimeondolewa

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
ALLOWED_PDF_TYPE = "application/pdf"

# --- Authentication Setup ---
# Pata Twilio credentials kutoka environment variables kwa ajili ya uthibitishaji wa kupakua media
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
# --- End Authentication Setup ---


def process_file_upload(user_id, user_name, user_phone, flow_type, media_url: str, mime_type: str):
    try:
        logger.info(f"File MIME: {mime_type}, URL: {media_url}")

        # UKAGUZI WA UTHIBITISHAJI
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            error_msg = "Kosa la Usalama: Vigezo vya uthibitishaji vya Twilio (SID/Token) havikupatikana."
            logger.error(f"❌ {error_msg}")
            send_message(user_phone, f"❌ {error_msg}")
            return {"status": "error", "message": error_msg}


        # 1. Pakua data ya faili kutoka Twilio media URL na AUTHENTICATION
        # Hii sasa inatumia Basic Auth (SID:Token)
        response = requests.get(
            media_url, 
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        )
        response.raise_for_status() # Leta hitilafu kwa status codes mbaya (4xx au 5xx)
        file_data = response.content
        
        # Tengeneza jina la faili la kipekee
        ext = mimetypes.guess_extension(mime_type) if mime_type else ".bin"
        file_name = f"{user_id}_{uuid.uuid4()}{ext}"
        
        analysis_summary = None
        
        # --- 2. Fanya Uchambuzi kulingana na aina ya MIME ---
        if mime_type == ALLOWED_PDF_TYPE:
            logger.info("Starting PDF analysis (Manka financial analysis)...")
            # Tumia huduma ya uchambuzi wa PDF
            result = analyze_pdf(file_data, file_name, user_name)
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            analysis_summary = f"📄 *Uchambuzi wa PDF umekamilika! (Manka Financial Analysis)*\n\n{summary}"
        
        elif mime_type in ALLOWED_IMAGE_TYPES:
            logger.info("Starting image analysis (Gemini Manka financial analysis)...")
            # Tumia huduma ya uchambuzi wa picha ya Gemini (kwa taarifa za kifedha)
            result = analyze_image(file_data, mime_type) 
            summary = result.get("summary") if isinstance(result, dict) else str(result)
            analysis_summary = f"📸 *Uchambuzi wa Picha umekamilika! (Gemini Financial Analysis)*\n\n{summary}"

        else:
            message = f"⚠️ Aina ya faili hili ({mime_type}) haikubaliki. Tafadhali tuma PDF au Picha (JPG/PNG/WEBP)."
            send_message(user_phone, message)
            return {"status": "unsupported", "message": message}
            
        # --- 3. Hifadhi kwenye Supabase ---
        logger.info("Starting file storage in Supabase...")
        
        stored_result = store_file(
            user_id=user_id,
            user_name=user_name,
            user_phone=user_phone,
            flow_type=flow_type,
            file_data=file_data,
            mime_type=mime_type,
            file_name=file_name 
        )
        
        if not stored_result or 'file_url' not in stored_result:
             raise Exception("Kushindwa kuhifadhi faili na kupata URL ya umma.")
             
        stored_url = stored_result['file_url']
        logger.info(f"File stored successfully at URL: {stored_url}")

        # 4. Tuma ujumbe wa mwisho kwa mtumiaji
        final_message = analysis_summary if analysis_summary else "✅ Faili limepakia na kuhifadhiwa. Uchambuzi umefanyika."
        send_message(user_phone, final_message)
        
        return {"status": "success", "summary": final_message, "file_url": stored_url}

    except requests.exceptions.HTTPError as he:
        # Kushughulikia hitilafu ikiwa upakuaji wa Twilio unashindwa (k.m., 401 Unauthorized)
        error_msg = f"Kosa la kupakua faili (HTTP {he.response.status_code}): Inawezekana kiungo kimeisha muda au kuna shida katika uthibitishaji (Twilio Credentials)."
        logger.exception(f"❌ HTTP Error downloading file: {he}")
        send_message(user_phone, f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}
        
    except Exception as e:
        logger.exception(f"❌ Hitilafu katika kuchakata faili: {e}")
        send_message(user_phone, f"❌ Samahani, hitilafu imetokea wakati wa kuchambua au kuhifadhi faili lako: {str(e)}")
        return {"status": "error", "message": str(e)}
