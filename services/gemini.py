import os
from google import genai
from google.genai.errors import APIError


try:
      api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not found.")
    client = genai.Client(api_key=api_key) 
except Exception as e:
    raise EnvironmentError(f"Failed to initialize Gemini Client. Ensure your API key is set correctly. Error: {e}")

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png"]
MODEL_NAME = "gemini-2.5-flash"

def analyze_image(image_url: str) -> str:
    try:
        clean_url_for_check = image_url.split('?')[0]
        
        ext = clean_url_for_check.split(".")[-1].lower() 
        
        # Check extension
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return "⚠️ Unsupported image format. Use jpg/jpeg/png only."

        # The full original URL (with tokens) is used for the API call
        prompt = "Describe this image in detail."
        contents = [
            prompt,
            image_url  # Use the original URL (e.g., with ?token=...)
        ]

        # Call the API
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
        )

        # Return the text result
        return response.text

    except APIError as e:
        return f"⚠️ Gemini API Error: {str(e)}"
    except Exception as e:
        return f"⚠️ General Error analyzing image: {str(e)}"