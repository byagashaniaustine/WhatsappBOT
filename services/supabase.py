import os
import uuid
import logging
import mimetypes
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


def build_google_drive_url(file_id: str) -> str:
    """Convert Google Drive file ID to a direct download URL."""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_url_or_id: str,
    file_type: str | None = None
) -> str | None:
    try:
        if not file_url_or_id:
            raise ValueError("Missing file URL or ID.")

        # Convert Google Drive file ID to download URL
        file_url = file_url_or_id
        if not file_url_or_id.startswith("http"):
            file_url = build_google_drive_url(file_url_or_id)

        # Determine MIME type if not provided
        if not file_type:
            head_resp = requests.head(file_url, allow_redirects=True)
            file_type = head_resp.headers.get("Content-Type", "application/octet-stream")
        mime_type = file_type.lower()

        # Log unsupported types but continue
        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            logger.warning(f"⚠️ Unsupported MIME type: {mime_type}, storing anyway.")

        # Download the file
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        file_data = response.content

        # Generate a unique filename
        ext = mime_type.split("/")[-1] if "/" in mime_type else "dat"
        filename = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # Upload to Supabase Storage bucket
        upload_result = supabase.storage.from_("whatsapp_files").upload(filename, file_data)
        if upload_result is not None:
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        # Get public URL
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)
        logger.info(f"🌍 Public file URL: {public_url}")

        # Insert metadata
        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_url": public_url,
            "file_type": mime_type
        }
        supabase.table("wHatsappUsers").insert(metadata).execute()

        return public_url

    except Exception as e:
        logger.exception(f"❌ Error storing file for user {user_phone}: {str(e)}")
        return None
