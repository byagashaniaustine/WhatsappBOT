import os
import uuid
import logging
from supabase import create_client, Client
from typing import Optional

# NOTE: Removed get_file_metadata and download_file_from_drive imports
# as they are no longer needed inside this function.

logger = logging.getLogger(__name__)

# --- Supabase Setup ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Use a custom exception or standard ValueError/EnvironmentError
    raise EnvironmentError("❌ Supabase credentials missing. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supported types ---
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"


def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    drive_file_id: str, # The Google Drive ID (kept for logging/tracking)
    file_data: bytes,   # File bytes already downloaded by the caller (for efficiency)
    mime_type: str,     # MIME type already determined by the caller
) -> dict | None:
    try:
        logger.info(f"📄 Preparing file for storage: Drive ID {drive_file_id} ({mime_type})")

        # --- Check supported types ---
        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            # This check might be redundant if done by the caller, but serves as a safeguard
            raise ValueError(f"Unsupported file type: {mime_type}")

        # --- Define path & extension ---
        # Get extension from MIME type. Using a UUID for secure, unique pathing.
        ext = mime_type.split("/")[-1]
        supabase_path = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # --- Upload to Supabase bucket ---
        # Specify the content-type header for correct serving
        upload_result = supabase.storage.from_("whatsapp_files").upload(
            supabase_path, 
            file_data,
            {'content-type': mime_type} 
        )
        if upload_result is not None and not isinstance(upload_result, dict):
            # Supabase Python lib can return None/dict/Response depending on success/error
            # This check is safer than the original 'is not None'
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        # --- Get public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(
            supabase_path
        )
        logger.info(f"✅ File stored successfully: {public_url}")

        # --- Save metadata in DB (Matches your required table columns) ---
        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_type": mime_type, # Required column
            "file_url": public_url, # Required column
            # Consider adding "drive_file_id": drive_file_id for audit/tracking
        }

        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        
        # Check if the insert was successful based on the library's response structure
        if not (getattr(result, "data", None) and len(result.data) > 0):
            logger.warning("⚠️ Metadata not stored properly in Supabase.")

        return {
            "file_url": public_url,
            "file_type": mime_type,
        }

    except Exception as e:
        logger.exception(f"❌ Error storing file for {user_phone}: {e}")
        return None