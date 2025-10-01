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
            return "⚠️ Unsupported image format. Use jpg/jpeg/png only."

        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status() 
        image_bytes = image_response.content
        image_part = Part.from_bytes(data=image_bytes, mime_type=mime_type)

        prompt = "Describe this image in detail maximum 400 characters."
        contents = [
            prompt,
            image_part, 
        ]

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
        )

        # 5. Ensure a string is always returned, handling potential None from response.text
        return response.text or "⚠️ Gemini returned an empty response text."

    except requests.exceptions.RequestException as req_e:
        # Handle errors during the image fetching process (e.g., URL not found, network error)
        return f"⚠️ Failed to fetch image from URL: {type(req_e).__name__} - {str(req_e)}"
    except APIError as e:
        # Handle specific Gemini API errors
        return f"⚠️ Gemini API Error: {str(e)}"
    except Exception as e:
        # Handle all other general errors
        logger.error(f"General Error analyzing image: {e}", exc_info=True)
        return f"⚠️ General Error analyzing image: {str(e)}"
