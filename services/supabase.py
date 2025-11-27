import os
import uuid
import logging
from supabase import create_client, Client
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# --- Supabase Setup ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("❌ Supabase credentials missing. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supported types ---
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"

# ----------------------------------------------------------------------
## 🎯 SESSION MANAGEMENT FUNCTIONS (Storage and Retrieval by ID) 🎯
# ----------------------------------------------------------------------

async def store_session_data(
    phone_number: str,
    message: str,
) -> Optional[str]: # Returns session_id
    """
    Stores a new session (UUID, phone, latest message) upon contact.
    Returns the generated session_id (UUID string) or None on failure.
    """
    if not supabase or not phone_number:
        logger.error("Supabase not available or Phone number is missing.")
        return None

    session_id = str(uuid.uuid4())
    
    data_to_store = {
        "session_id": session_id,
        "phone_number": phone_number,
        "latest_message": message,
        "status": "active"
    }

    try:
        response = supabase.table("whatsapp_sessions").insert(data_to_store).execute()
        
        if getattr(response, "data", None) and response.data:
            logger.critical(f"✅ Supabase: New session stored for {phone_number} with ID: {session_id}")
            return session_id 
        
        return None
    except Exception as e:
        logger.error(f"❌ Supabase session insertion failed for {phone_number}: {e}")
        return None


async def get_session_phone_by_id(session_id: str) -> Optional[str]: # Returns phone_number
    """
    Retrieves the phone number associated with a specific session_id (UUID).
    Used by the Flow background task (send_loan_results) to get the recipient.
    """
    if not supabase:
        logger.error("Supabase not available. Cannot retrieve session data by ID.")
        return None
        
    try:
        # Filter where session_id matches the provided ID and retrieve phone_number.
        response = supabase.table("whatsapp_sessions").select("phone_number").eq("session_id", session_id).single().execute()
        
        if getattr(response, "data", None):
            phone_number = response.data.get("phone_number")
            logger.critical(f"✅ Supabase: Phone number {phone_number} retrieved by ID: {session_id}")
            return phone_number 
            
        return None
    except Exception as e:
        logger.error(f"❌ Supabase retrieval failed for ID {session_id}: {e}")
        return None

# --- NOTE: Removed the unused get_latest_session_data() for clarity/security, keeping the ID retrieval ---

# ----------------------------------------------------------------------
## 🖼️ FILE STORAGE FUNCTION (Original, unmodified)
# ----------------------------------------------------------------------

def store_file(
    user_id: str,
    user_name: str,
    user_phone: str,
    flow_type: str,
    file_name: str,
    file_data: bytes, 
    mime_type: str, 
) -> dict | None:
    # ... (Logic remains the same) ...
    try:
        supabase_path = f"{user_id}/{file_name}"
        logger.info(f"📄 Preparing file for storage at path: {supabase_path} ({mime_type})")

        if mime_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError(f"Unsupported file type: {mime_type}")

        upload_result = supabase.storage.from_("whatsapp_files").upload(
            supabase_path, 
            file_data,
            {'content-type': mime_type} 
        )
        if upload_result is not None and not isinstance(upload_result, dict):
            logger.warning(f"⚠️ Unexpected upload response: {upload_result}")

        public_url = supabase.storage.from_("whatsapp_files").get_public_url(
            supabase_path
        )
        logger.info(f"✅ File stored successfully: {public_url}")

        metadata = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_type": mime_type, 
            "file_url": public_url, 
        }

        result = supabase.table("wHatsappUsers").insert(metadata).execute()
        
        if not (getattr(result, "data", None) and len(result.data) > 0):
            logger.warning("⚠️ Metadata not stored properly in Supabase.")

        return {
            "file_url": public_url,
            "file_type": mime_type,
        }

    except Exception as e:
        logger.exception(f"❌ Error storing file for {user_phone}: {e}")
        return None