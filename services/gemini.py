import os
import requests
import logging
from google import genai
from google.genai.errors import APIError
from google.genai.types import Part
from typing import Union

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

# Note: Using the MIME types defined in the caller for consistency
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
MODEL_NAME = "gemini-2.5-flash"

# 🛑 FIX: Updated signature to accept file bytes and MIME type directly, 
# removing the need to fetch the file from a URL.
def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    try:
        # Check if the determined MIME type is supported
        if mime_type not in ALLOWED_IMAGE_TYPES:
            # Ujumbe kwa Kiswahili: Umbizo la picha haliruhusiwi
            exts = [t.split('/')[1] for t in ALLOWED_IMAGE_TYPES if t != 'image/jpg']
            return f"⚠️ Ingizo la picha la aina ya '{mime_type}' haliruhusiwi. Tumia moja ya: {', '.join(exts)}."

        # Create the image Part directly from the provided bytes and MIME type
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

        # Hakikisha jibu linarejeshwa, ikiwa jibu ni tupu, rudisha ujumbe wa Kiswahili.
        return response.text or "⚠️ Gemini haikurejesha maelezo yoyote."

    except APIError as e:
        # Kushughulikia hitilafu mahususi za Gemini API
        return f"⚠️ Hitilafu ya API ya Gemini"
    except Exception as e:
        # Kushughulikia hitilafu zote za jumla
        logger.error(f"General Error analyzing image: {e}", exc_info=True)
        return f"⚠️ Hitilafu ya Jumla katika kuchambua picha"
