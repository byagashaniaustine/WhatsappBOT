import io
import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load service account info from environment variable
service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not service_account_json:
    raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not set in environment")

service_account_info = json.loads(service_account_json)
# Convert literal \n to real newlines in private_key
service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Initialize Google Drive service
try:
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )
    drive_service = build("drive", "v3", credentials=credentials)
    logger.info("✅ Google Drive service initialized successfully.")
except Exception as e:
    logger.exception(f"❌ Failed to initialize Google Drive service: {e}")
    drive_service = None

def get_file_metadata(file_id: str):
    """Fetch file name and MIME type from Google Drive"""
    if not drive_service:
        raise RuntimeError("Drive service not initialized")
    try:
        file = drive_service.files().get(fileId=file_id, fields="name, mimeType").execute()
        return file["name"], file["mimeType"]
    except Exception as e:
        logger.exception(f"❌ Error fetching metadata for file ID {file_id}: {e}")
        raise

def download_file_from_drive(file_id: str) -> bytes:
    """Download file content from Google Drive as bytes"""
    if not drive_service:
        raise RuntimeError("Drive service not initialized")
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.info(f"⬇️ Download progress: {int(status.progress() * 100)}%")
        fh.seek(0)
        return fh.read()
    except Exception as e:
        logger.exception(f"❌ Error downloading file from Drive (ID: {file_id}): {e}")
        raise
