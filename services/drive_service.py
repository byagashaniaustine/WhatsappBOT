import io
import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not service_account_json:
    raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not set")

service_account_info = json.loads(service_account_json)
# Convert literal \n to real newlines
service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

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
