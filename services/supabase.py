import os
import requests
import uuid
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("Supabase URL or service role key not set!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Allowed types
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png"]
PDF_TYPE = "application/pdf"


def store_file(user_id: str, user_name: str, user_phone: str, flow_type: str , file_url: str , file_type: str ) -> str | None:
    """
    Stores metadata in Supabase about a file uploaded via Twilio Flow.

    Parameters:
    - user_id: unique user identifier
    - user_name: full name of the user
    - user_phone: user's phone number
    - flow_type: type of Twilio Flow (optional)
    - file_url: public URL of uploaded file (optional)
    - file_type: media type (image/pdf) (optional)

    Returns:
    - Public URL of the uploaded file if provided, else None
    """
    public_url = None

    # Handle file upload if file_url is provided
    if file_url:
        if file_type not in IMAGE_TYPES + [PDF_TYPE]:
            raise ValueError("Unsupported file type. Only images and PDFs allowed.")

        # Download file from Twilio
        response = requests.get(file_url, auth=(str(TWILIO_ACCOUNT_SID), str(TWILIO_AUTH_TOKEN)))
        if response.status_code != 200:
            raise Exception(f"Failed to download file from Twilio: {response.status_code}")
        file_data = response.content

        # Determine file extension
        if file_type in IMAGE_TYPES:
            ext = file_type.split("/")[-1]
        elif file_type == PDF_TYPE:
            ext = "pdf"
        else:
            ext = "dat"

        # Generate unique filename
        filename = f"{user_id}/{uuid.uuid4().hex[:8]}.{ext}"

        # Upload to Supabase Storage
        upload_res = supabase.storage.from_("whatsapp_files").upload(filename, file_data)
        if not hasattr(upload_res, "path") or not upload_res.path:
            raise Exception(f"Supabase upload failed: {upload_res}")

        public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)

    # Insert metadata in Supabase DB
    insert_res = supabase.table("WHatsappUsers").insert({
        "user_id": user_id,
        "user_name": user_name,
        "user_phone": user_phone,
        "flow_type": flow_type,
        "file_url": public_url
    }).execute()

    if not insert_res or not getattr(insert_res, "data", None):
        raise Exception(f"Supabase DB insert failed: {insert_res}")

    return public_url
