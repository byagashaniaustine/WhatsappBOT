import io
import logging
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


logger = logging.getLogger(__name__)

service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

try:
    credentials = service_account.Credentials.from_service_account_file(
       service_account_info, scopes=SCOPES
    )
    drive_service = build("drive", "v3", credentials=credentials)
    logger.info("✅ Google Drive service initialized successfully.")
except Exception as e:
    logger.exception(f"❌ Failed to initialize Google Drive service: {e}")
    drive_service = None


def get_file_metadata(file_id: str):
    try:
        file = drive_service.files().get(fileId=file_id, fields="name, mimeType").execute()
        return file["name"], file["mimeType"]
    except Exception as e:
        logger.exception(f"❌ Error fetching file metadata for ID {file_id}: {e}")
        raise


def download_file_from_drive(file_id: str) -> bytes:
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
