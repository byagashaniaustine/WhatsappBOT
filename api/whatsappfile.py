import requests
from fastapi.responses import PlainTextResponse
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message
import os

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

IMAGE_TYPES = {"image/jpeg", "image/png"}
PDF_TYPE = "application/pdf"


def extract_filename_and_extension(url: str, content_type: str) -> tuple[str, str]:
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
    ext = ext_map.get(content_type)
    if not ext:
        raise ValueError(f"Unsupported media type: {content_type}")

    clean_url = url.split("?")[0]
    filename_with_ext = clean_url.split("/")[-1]

    if "." not in filename_with_ext or filename_with_ext.endswith("."):
        filename = f"file{ext}"
        return filename, ext.strip(".")
    return filename_with_ext, ext.strip(".")


async def whatsapp_file(data: dict):
    from_number = str(data.get("From"))
    twilio_file_url = data.get("MediaUrl0")
    content_type = data.get("MediaContentType0", "")
    user_fullname = data.get("user_name") or from_number.split(":")[-1]

    if not twilio_file_url:
        send_message(to=from_number, body="⚠️ Hakuna faili lilipokelewa. Tafadhali jaribu tena.")
        return PlainTextResponse("No file")

    if content_type not in IMAGE_TYPES.union({PDF_TYPE}):
        send_message(
            to=from_number,
            body="⚠️ Faili hili halijaungwa mkono. Tuma PDF au picha (JPG/PNG)."
        )
        return PlainTextResponse("Unsupported file type")

    try:
        # Process images
        if content_type in IMAGE_TYPES:
            analysis_result = analyze_image(twilio_file_url)

        # Process PDF
        else:
            file_response = requests.get(
                twilio_file_url,
                stream=True,
                auth=(str(TWILIO_ACCOUNT_SID),str(TWILIO_AUTH_TOKEN))
            )
            file_response.raise_for_status()
            file_data = file_response.content
            filename, _ = extract_filename_and_extension(twilio_file_url, content_type)
            analysis_result = analyze_pdf(
                file_data=file_data,
                filename=filename,
                user_fullname=user_fullname
            )

    except Exception as e:
        analysis_result = f"⚠️ Tatizo lililotokea: {str(e)}"

    # Truncate for Twilio message limit
    MAX_CHARS = 1500
    if len(analysis_result) > MAX_CHARS:
        analysis_result = analysis_result[:MAX_CHARS] + "\n\n[... Message truncated ...]"

    send_message(to=from_number, body=analysis_result)
    return PlainTextResponse("OK")
