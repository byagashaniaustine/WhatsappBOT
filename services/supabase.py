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
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png"]
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
    Downloads a WhatsApp file from Twilio, uploads it to Supabase Storage,
    and logs metadata in the 'WhatsappUsers' table.

    Returns: public file URL (or None if upload fails).
    """

    public_url = None

    try:
        # --- Step 1: Validate file URL & type ---
        if not file_url:
            raise ValueError("Missing file URL.")
        if file_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError(f"Unsupported file type: {file_type}")

        # --- Step 2: Download file from Twilio ---
        response = requests.get(file_url, auth=(str(TWILIO_ACCOUNT_SID),str(TWILIO_AUTH_TOKEN)))
        if response.status_code != 200:
            raise Exception(f"Failed to download file from Twilio: HTTP {response.status_code}")
        file_data = response.content

        # --- Step 3: Generate filename ---
        ext = file_type.split("/")[-1] if "/" in file_type else "dat"
        filename = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # --- Step 4: Upload to Supabase Storage bucket ---
        upload_response = supabase.storage.from_("whatsapp_files").upload(filename, file_data)

        # Supabase SDK returns None if successful, raises on error
        if upload_response is not None:
            logger.info(f"✅ File uploaded to Supabase: {filename}")

        # --- Step 5: Get public URL ---
        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)
        logger.info(f"🌍 Public file URL: {public_url}")

        # --- Step 6: Save metadata to table ---
        insert_data = {
            "user_id": user_id,
            "user_name": user_name,
            "user_phone": user_phone,
            "flow_type": flow_type,
            "file_url": public_url,
        }

        result = supabase.table("WhatsappUsers").insert(insert_data).execute()
        if not getattr(result, "data", None):
            logger.warning(f"⚠️ Failed to insert metadata into Supabase: {result}")

        return public_url

    except Exception as e:
        logger.exception(f"❌ Error storing file for user {user_phone}: {str(e)}")
        return None
