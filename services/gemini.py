import os
import requests
import logging
from google import genai
from google.genai.errors import APIError
from google.genai.types import Part

logger = logging.getLogger(__name__)

try:
    # Attempt to retrieve API key and initialize client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not found.")
    client = genai.Client(api_key=api_key)
except Exception as e:
    # Raise a clear error if initialization fails
    raise EnvironmentError(
        f"Failed to initialize Gemini Client. Ensure your API key is set correctly. Error: {e}"
    )

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png"]
MODEL_NAME = "gemini-2.5-flash"

def analyze_image(image_url: str) -> str:
    try:
        clean_url_for_check = image_url.split("?")[0]
        ext = clean_url_for_check.split(".")[-1].lower()
        if ext == 'png':
            mime_type = 'image/png'
        elif ext in ['jpg', 'jpeg']:
            mime_type = 'image/jpeg'
        else:
            # Ujumbe kwa Kiswahili: Umbizo la picha haliruhusiwi
            return "⚠️ Umbizo la picha haliungwi mkono. Tumia jpg/jpeg/png tu."

        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status() 
        image_bytes = image_response.content
        image_part = Part.from_bytes(data=image_bytes, mime_type=mime_type)

        # Prompt kwa Kiswahili: Kuomba maelezo ya picha yatolewe kwa Kiswahili
        prompt = "Fafanua picha hii kwa lugha ya Kiswahili, usizidi herufi 400."
        contents = [
            prompt,
            image_part, 
        ]

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
        )

        # 5. Hakikisha jibu linarejeshwa, ikiwa jibu ni tupu, rudisha ujumbe wa Kiswahili.
        return response.text or "⚠️ Gemini haikurejesha maelezo yoyote."

    except requests.exceptions.RequestException as req_e:
        # Kushughulikia hitilafu za kupakua picha kutoka kwa kiungo
        return f"⚠️ Imeshindwa kupakua picha kutoka kwa kiungo: {type(req_e).__name__} - {str(req_e)}"
    except APIError as e:
        # Kushughulikia hitilafu mahususi za Gemini API
        return f"⚠️ Hitilafu ya API ya Gemini: {str(e)}"
    except Exception as e:
        # Kushughulikia hitilafu zote za jumla
        logger.error(f"General Error analyzing image: {e}", exc_info=True)
        return f"⚠️ Hitilafu ya Jumla katika kuchambua picha: {str(e)}"
