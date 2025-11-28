import os
import uuid
import logging
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)



SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("❌ Supabase credentials missing. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"


async def store_session_data(
    phone_number: str,
    message: str,
) -> Optional[str]:
    """
    Creates a new UUID session row in Whatsapp_sessions.
    Returns the session_id string.
    """
    if not phone_number:
        logger.error("❌ phone_number missing. Session not saved.")
        return None

    session_id = str(uuid.uuid4())

    session_record = {
        "session_id": session_id,
        "phone_number": phone_number,
        "latest_message": message,
        "status": "active"
    }

    try:
        response = supabase.table("whatsapp_sessions").insert(session_record).execute()

        if getattr(response, "data", None):
            logger.info(f"✅ Session stored for {phone_number} (ID: {session_id})")
            return session_id

        logger.error("❌ Supabase insert returned no data.")
        return None

    except Exception as e:
        logger.error(f"❌ Failed to store session: {e}")
        return None


async def get_session_phone_by_id(session_id: str) -> Optional[str]:
    """
    Retrieves the phone number tied to a session_id.
    """
    try:
        response = (
            supabase.table("whatsapp_sessions")
            .select("phone_number")
            .eq("session_id", session_id)
            .single()
            .execute()
        )

        if getattr(response, "data", None):
            phone = response.data.get("phone_number")
            logger.info(f"📲 Retrieved phone ({phone}) for session: {session_id}")
            return phone

        return None

    except Exception as e:
        logger.error(f"❌ Error retrieving phone by session ID: {e}")
        return None


def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_name: str,
    file_data: bytes,
    mime_type: str,
) -> dict | None:
    """
    Uploads user file to Supabase Storage + logs metadata.
    """
    try:
        supabase_path = f"{user_id}/{file_name}"

        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError(f"🚫 Unsupported file type: {mime_type}")

        upload_result = supabase.storage.from_("whatsapp_files").upload(
            supabase_path,
            file_data,
            {"content-type": mime_type},
        )

        public_url = supabase.storage.from_("whatsapp_files").get_public_url(
            supabase_path
        )

        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_type": mime_type,
            "file_url": public_url,
        }

        supabase.table("wHatsappUsers").insert(metadata).execute()

        return {
            "file_url": public_url,
            "file_type": mime_type,
        }

    except Exception as e:
        logger.exception(f"❌ File storage failed for {user_phone}: {e}")
        return None
