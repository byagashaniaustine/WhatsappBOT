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

def store_file(file_url: str, user_id: str, content_type: str) -> str:
    """
    Downloads file from Twilio and uploads to Supabase Storage.
    Returns public URL.
    """
    # Validate type
    if content_type not in IMAGE_TYPES + [PDF_TYPE]:
        raise ValueError("Unsupported file type. Only images and PDFs allowed.")

    # Download file from Twilio
    response = requests.get(file_url, auth=(str(TWILIO_ACCOUNT_SID), str(TWILIO_AUTH_TOKEN)))
    if response.status_code != 200:
        raise Exception(f"Failed to download file from Twilio: {response.status_code}")
    file_data = response.content

    # Determine file extension
    if content_type in IMAGE_TYPES:
        ext = content_type.split("/")[-1]  # jpg/jpeg/png
    elif content_type == PDF_TYPE:
        ext = "pdf"

    # Generate unique filename
    original_name = os.path.basename(file_url).split("?")[0]
    name = os.path.splitext(original_name)[0]
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{user_id}/{name}_{unique_id}.{ext}"

    # Upload to Supabase
    upload_res = supabase.storage.from_("whatsapp_files").upload(filename, file_data)
    if not hasattr(upload_res, "path") or not upload_res.path:
        raise Exception(f"Supabase upload failed: {upload_res}")

    public_url = supabase.storage.from_("whatsapp_files").get_public_url(filename)

    # Insert metadata in DB
    insert_res = supabase.table("WHatsappUsers").insert({
        "user_id": user_id,
        "file_name": filename,
        "file_url": public_url,
        "file_type": ext,
    }).execute()

    if not insert_res or not getattr(insert_res, "data", None):
        raise Exception(f"Supabase DB insert failed: {insert_res}")

    return public_url
