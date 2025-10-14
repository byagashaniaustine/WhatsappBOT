import os
import uuid
import logging
from supabase import create_client, Client
from services.drive_service import get_file_metadata, download_file_from_drive  # 👈 use your existing Drive module

logger = logging.getLogger(__name__)

# --- Supabase Setup ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("❌ Supabase credentials missing.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supported types ---
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"


def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_id: str,
) -> dict | None:
    """
    Fetch file from Google Drive (via file_id),
    upload to Supabase Storage,
    and store metadata.
    """
    try:
        # --- Get file info from Drive ---
        file_name, mime_type = get_file_metadata(file_id)
        logger.info(f"📄 File fetched: {file_name} ({mime_type})")

        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError(f"Unsupported file type: {mime_type}")

        # --- Download actual file bytes ---
        file_data = download_file_from_drive(file_id)

        # --- Define path & extension ---
        ext = mime_type.split("/")[-1]
        supabase_path = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # --- Upload to Supabase bucket ---
        upload_result = supabase.storage.from_("whatsapp_files").upload(
            supabase_path, file_data
        )
        if upload_result is not None:
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        # --- Get public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(
            supabase_path
        )
        logger.info(f"✅ File stored successfully: {public_url}")

        # --- Save metadata in DB ---
        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_id": file_id,
            "file_url": public_url,
            "file_type": mime_type,
        }

        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        if not getattr(result, "data", None):
            logger.warning("⚠️ Metadata not stored properly in Supabase.")

        return {
            "file_url": public_url,
            "file_type": mime_type,
        }

    except Exception as e:
        logger.exception(f"❌ Error storing Google Form file for {user_phone}: {e}")
        return None
