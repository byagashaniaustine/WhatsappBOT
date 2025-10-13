import os
import uuid
import logging
import requests
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
    file_type: str
) -> str | None:
    """
    Downloads a file from Twilio or Google Drive,
    uploads it to Supabase Storage,
    and stores metadata in the wHatsappUsers table.
    """
    try:
        if not file_url:
            raise ValueError("Missing file URL or file ID.")

        # --- Detect Google Drive or raw ID ---
        if not (file_url.startswith("http://") or file_url.startswith("https://")):
            # Google Forms often send only the file ID
            logger.info("📄 Detected raw Google Drive file ID — building direct link...")
            download_url = f"https://drive.google.com/uc?id={file_url}"
        elif "drive.google.com" in file_url or "docs.google.com" in file_url:
            logger.info("📂 Detected Google Drive link — normalizing...")
            if "uc?id=" in file_url:
                download_url = file_url
            elif "file/d/" in file_url:
                file_id = file_url.split("/file/d/")[1].split("/")[0]
                download_url = f"https://drive.google.com/uc?id={file_id}"
            else:
                raise ValueError("Unrecognized Google Drive URL format.")
        else:
            download_url = file_url  # Twilio or other direct links

        logger.info(f"🌍 Final download URL: {download_url}")

        # --- Download file from URL ---
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if "api.twilio.com" in download_url else None
        response = requests.get(download_url, auth=auth, timeout=30)
        response.raise_for_status()
        file_data = response.content

        # --- Determine extension ---
        if not file_type:
            file_type = response.headers.get("Content-Type", "")
        ext = file_type.split("/")[-1] if "/" in file_type else "pdf"

        if file_type not in IMAGE_TYPES + [PDF_TYPE]:
            logger.warning(f"⚠️ Unrecognized MIME type ({file_type}) — forcing generic extension")
            ext = "dat"

        # --- Generate filename ---
        filename = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # --- Upload to Supabase bucket ---
        upload_result = supabase.storage.from_("whatsapp_files").upload(filename, file_data)
        if upload_result is not None:
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        # --- Get public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)
        logger.info(f"✅ File successfully uploaded to Supabase: {public_url}")

        # --- Insert metadata into database ---
        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_url": public_url,
            "file_type": file_type
        }

        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        if not getattr(result, "data", None):
            logger.warning(f"⚠️ Metadata insert may have failed: {result}")

        return public_url

    except Exception as e:
        logger.exception(f"❌ Error storing file for {user_phone}: {str(e)}")
        return None
