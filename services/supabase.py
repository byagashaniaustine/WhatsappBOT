import os
import uuid
import logging
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)

# --- Supabase Setup ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Tumia EnvironmentError badala ya ValueError kwa ajili ya vigezo vinavyokosekana
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
    file_name: str,    # <-- NEW: Kupokea jina la faili lililotengenezwa na mtoa wito (whatsappfile.py)
    file_data: bytes, 
    mime_type: str, 
) -> dict | None:
    """
    Hupakia data ya faili kwenye Supabase Storage na kuhifadhi metadata yake katika jedwali.

    Args:
        user_id (str): Kitambulisho cha mtumiaji.
        user_name (str): Jina la mtumiaji.
        user_phone (str): Namba ya simu.
        flow_type (str): Aina ya mtiririko.
        file_name (str): Jina kamili la kipekee la faili (k.m., 'user_id_uuid.ext').
        file_data (bytes): Data ya faili.
        mime_type (str): Aina ya MIME ya faili.
    """
    try:
        # Njia ya Supabase Storage: {user_id}/{file_name}
        supabase_path = f"{user_id}/{file_name}"
        logger.info(f"📄 Preparing file for storage at path: {supabase_path} ({mime_type})")

        # --- Check supported types ---
        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            # Hii ni kinga, kwani upakuaji unapaswa kuangalia kwanza.
            raise ValueError(f"Unsupported file type: {mime_type}")

        # --- Upload to Supabase bucket ---
        # Specify the content-type header for correct serving
        upload_result = supabase.storage.from_("whatsapp_files").upload(
            supabase_path, 
            file_data,
            {'content-type': mime_type} 
        )
        if upload_result is not None and not isinstance(upload_result, dict):
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
            "file_type": mime_type, 
            "file_url": public_url, 
        }

        # Jedwali la "wHatsappUsers" linatumika kwa metadata
        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        
        # Hakikisha metadata imehifadhiwa
        if not (getattr(result, "data", None) and len(result.data) > 0):
            logger.warning("⚠️ Metadata not stored properly in Supabase.")

        return {
            "file_url": public_url,
            "file_type": mime_type,
        }

    except Exception as e:
        logger.exception(f"❌ Error storing file for {user_phone}: {e}")
        return None
