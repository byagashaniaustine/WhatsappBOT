import os
import uuid
import logging
import requests
import mimetypes
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# --- Environment Variables ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("❌ Supabase credentials are missing (URL or Service Role Key).")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Allowed File Types ---
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"


def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_url: str,
    file_type: str | None = None
) -> str | None:
    """
    Downloads a file from a public or Twilio-protected URL, uploads it to Supabase Storage,
    and stores metadata in the wHatsappUsers table.
    Works with both Twilio media links and Google Form/Drive links.
    """
    try:
        if not file_url:
            raise ValueError("Missing file URL.")

        # --- Detect Google Drive or public link ---
        is_google_drive = "drive.google.com" in file_url or "docs.google.com" in file_url
        is_twilio_media = "api.twilio.com" in file_url

        # --- Resolve Google Drive direct download link ---
        if is_google_drive:
            logger.info("📂 Detected Google Drive file source")
            if "uc?id=" in file_url:
                download_url = file_url
            elif "file/d/" in file_url:
                file_id = file_url.split("/file/d/")[1].split("/")[0]
                download_url = f"https://drive.google.com/uc?id={file_id}"
            else:
                raise ValueError("Unrecognized Google Drive URL format.")
        else:
            download_url = file_url

        # --- Guess MIME type if not provided ---
        guessed_type, _ = mimetypes.guess_type(download_url)
        file_type = file_type or guessed_type or "application/octet-stream"

        # --- Download file ---
        logger.info(f"⬇️ Downloading file from: {download_url}")
        if is_twilio_media:
            response = requests.get(download_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=30)
        else:
            response = requests.get(download_url, timeout=30)

        response.raise_for_status()
        file_data = response.content

        # --- Prepare filename & extension ---
        ext = mimetypes.guess_extension(file_type) or ".dat"
        filename = f"{flow_type}/{user_id}_{uuid.uuid4().hex[:8]}{ext}"

        # --- Upload to Supabase ---
        logger.info(f"☁️ Uploading file {filename} to Supabase...")
        upload_result = supabase.storage.from_("whatsapp_files").upload(filename, file_data)

        if upload_result is not None:
            logger.warning(f"⚠️ Upload response: {upload_result}")

        # --- Public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)
        logger.info(f"🌍 File stored at: {public_url}")

        # --- Store metadata ---
        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_url": public_url,
            "file_type": file_type,
        }

        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        if not getattr(result, "data", None):
            logger.warning(f"⚠️ Failed to insert metadata: {result}")

        return public_url

    except Exception as e:
        logger.exception(f"❌ Error storing file for {user_phone}: {str(e)}")
        return None
