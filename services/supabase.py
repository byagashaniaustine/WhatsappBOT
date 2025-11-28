import os
import uuid
import logging
from supabase import create_client, Client
from typing import Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)



SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("❌ Supabase credentials missing. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
PDF_TYPE = "application/pdf"




logger = logging.getLogger("whatsapp_app")

async def store_flow_session(flow_token: str, phone_number: str):
    """
    Store Flow session data linking flow_token to phone number.
    This allows us to retrieve the phone number during Flow interactions.
    
    Args:
        flow_token: The flow_token from WhatsApp Flow
        phone_number: User's phone number (with + prefix)
        
    Returns:
        str: The flow_token if successful, None otherwise
    """
    try:
        from services.supabase import supabase
        
        # Store with expiration time (Flow sessions typically last 10-15 minutes)
        expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        
        data = {
            "flow_token": flow_token,
            "phone_number": phone_number,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at
        }
        
        result = supabase.table("flow_sessions").upsert(data).execute()
        
        if result.data:
            logger.critical(f"✅ Flow session stored: {flow_token} -> {phone_number}")
            return flow_token
        else:
            logger.error(f"❌ Failed to store Flow session: {flow_token}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error storing Flow session: {e}", exc_info=True)
        return None


async def get_flow_session_phone(flow_token: str):
    """
    Retrieve phone number for a given flow_token.
    
    Args:
        flow_token: The flow_token from WhatsApp Flow
        
    Returns:
        str: Phone number if found, None otherwise
    """
    try:
        from services.supabase import supabase
        
        result = supabase.table("flow_sessions").select("phone_number").eq("flow_token", flow_token).single().execute()
        
        if result.data:
            phone = result.data.get("phone_number")
            logger.critical(f"✅ Retrieved phone for flow_token {flow_token}: {phone}")
            return phone
        else:
            logger.warning(f"⚠️ No phone found for flow_token: {flow_token}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error retrieving Flow session phone: {e}", exc_info=True)
        return None


async def cleanup_expired_flow_sessions():
    """
    Clean up expired Flow sessions (optional maintenance function).
    You can call this periodically or let the database handle it with a policy.
    """
    try:
        from services.supabase import supabase
        
        now = datetime.utcnow().isoformat()
        
        result = supabase.table("flow_sessions").delete().lt("expires_at", now).execute()
        
        if result.data:
            logger.info(f"🗑️ Cleaned up {len(result.data)} expired Flow sessions")
            
    except Exception as e:
        logger.error(f"❌ Error cleaning up Flow sessions: {e}", exc_info=True)
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
