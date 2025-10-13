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
    Downloads a file from Twilio or a public link,
    uploads it to Supabase Storage,
    and stores metadata in the wHatsappUsers table.
    """
    try:
        # --- Validate inputs ---
        if not file_url:
            raise ValueError("Missing file URL.")
        if file_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError(f"Unsupported file type: {file_type}")

        # --- Download file ---
        response = requests.get(file_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=30)
        response.raise_for_status()
        file_data = response.content

        # --- Generate filename ---
        ext = file_type.split("/")[-1] if "/" in file_type else "dat"
        filename = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # --- Upload to Supabase bucket ---
        upload_result = supabase.storage.from_("whatsapp_files").upload(filename, file_data)
        if upload_result is not None:
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        # --- Get public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)
        logger.info(f"🌍 File available at: {public_url}")

        # --- Store metadata ---
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
            logger.warning(f"⚠️ Failed to insert metadata into Supabase: {result}")

        return public_url

    except Exception as e:
        logger.exception(f"❌ Error storing file for user {user_phone}: {str(e)}")
        return None
