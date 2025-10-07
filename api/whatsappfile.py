import requests
import os
from fastapi.responses import PlainTextResponse
from services.gemini import analyze_image
from services.pdfendpoint import analyze_pdf
from services.twilio import send_message

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

IMAGE_TYPES = {"image/jpeg", "image/png"}
PDF_TYPE = "application/pdf"


def extract_filename_and_extension(url: str, content_type: str) -> tuple[str, str]:
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
    ext = ext_map.get(content_type)
    if not ext:
        raise ValueError(f"Unsupported media type: {content_type}")

    try:
        clean_url = url.split("?")[0]
        filename_with_ext = clean_url.split("/")[-1]

        if "." not in filename_with_ext or filename_with_ext.endswith("."):
            filename = f"file{ext}"
            return filename, ext.strip(".")

        return filename_with_ext, ext.strip(".")
    except Exception:
        raise ValueError("Could not parse a valid filename from the provided media URL.")


async def whatsapp_file(data):
    from_number = data.get("From")
    twilio_file_url = data.get("MediaUrl0")
    content_type = data.get("MediaContentType0", "")
    user_fullname = data.get("user_name") or from_number.split(":")[-1]

    if not twilio_file_url:
        send_message(to=from_number, body="⚠️ Hakuna faili lililopokelewa. Tafadhali jaribu tena.")
        return PlainTextResponse("No file")

    supported_types = IMAGE_TYPES.union({PDF_TYPE})
    if content_type not in supported_types:
        send_message(
            to=from_number,
            body="⚠️ Faili hili halijaungwa mkono. Tuma PDF au picha (JPG/PNG)."
        )
        return PlainTextResponse("Unsupported file type")

    analysis_result = "⚠️ Tatizo lisilotarajiwa limejitokeza."
    error_to_user = None

    try:
        # PDF download requires Twilio credentials
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise EnvironmentError("Twilio credentials SID/TOKEN missing.")

        if content_type in IMAGE_TYPES:
            analysis_result = analyze_image(twilio_file_url)

        elif content_type == PDF_TYPE:
            file_response = requests.get(
                twilio_file_url,
                stream=True,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            )
            file_response.raise_for_status()
            file_data = file_response.content
            filename, _ = extract_filename_and_extension(twilio_file_url, content_type)

            analysis_result = analyze_pdf(
                file_data=file_data,
                filename=filename,
                user_fullname=user_fullname
            )

    except ValueError as ve:
        error_to_user = str(ve)
    except requests.exceptions.RequestException as re:
        error_to_user = f"⚠️ Tatizo la kupakua faili/API request: {str(re)}"
    except EnvironmentError as ee:
        error_to_user = f"⚠️ Tatizo la mazingira: {str(ee)}. Angalia environment variables."
    except Exception as e:
        error_to_user = f"⚠️ Tatizo lisilotarajiwa: {str(e)}"

    # Final message to send user
    final_message = error_to_user if error_to_user else analysis_result

    # Truncate for Twilio message limit
    MAX_TWILIO_CHARS = 1500
    if len(final_message) > MAX_TWILIO_CHARS:
        final_message = (
            final_message[:MAX_TWILIO_CHARS]
            + "\n\n[... Message truncated due to Twilio limit ...]"
        )

    send_message(to=from_number, body=final_message)
    return PlainTextResponse("OK")
