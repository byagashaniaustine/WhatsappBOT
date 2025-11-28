import os
import requests
import logging
from services.gemini import analyze_file_with_gemini  # fallback

logger = logging.getLogger(__name__)

MANKA_API_KEY = os.environ.get("MANKA_API_KEY")
MANKA_ENDPOINT = os.environ.get("MANKA_ENDPOINT")

if not MANKA_API_KEY or not MANKA_ENDPOINT:
    logger.warning("MANKA_API_KEY or MANKA_ENDPOINT not set. Only Gemini fallback will be functional.")

def analyze_pdf(file_data: bytes, filename: str, user_fullname: str) -> str:
    """
    Attempts analysis with Manka. Falls back to Gemini on failure.
    """
    try:
        if not MANKA_API_KEY or not MANKA_ENDPOINT:
            raise EnvironmentError("Manka environment variables are missing.")

        # Strip any newlines/whitespace from API key
        clean_api_key = MANKA_API_KEY.strip()

        headers = {
            "Authorization": f"Bearer {clean_api_key}",
        }

        data = {"fullname": user_fullname}
        files = {"file": (filename, file_data, "application/pdf")}

        response = requests.post(
            str(MANKA_ENDPOINT),
            headers=headers,
            data=data,
            files=files,
            timeout=60
        )

        if not response.ok:
            logger.error(f"MANKA FAILED (HTTP {response.status_code}): {response.text[:100]}")
            return analyze_file_with_gemini(file_data, filename)

        response_data = response.json()
        affordability_data = response_data.get("affordability_scores")

        if affordability_data is None:
            logger.error("Manka response missing 'affordability_scores' key.")
            return analyze_file_with_gemini(file_data, filename)

        # Process Manka results
        if isinstance(affordability_data, str):
            return (
                f"Taarifa hizo hazitoshi kutafuta uwezo wa mkopo (INSUFFICIENT DATA)\n"
                f"---------------------------------------------\n\n"
                f"Hatukuweza kujua viwango vyako vya mkopo kwa sababu,Taarifa zilizokusanywa ni za chini ya miezi 3 :\n"
                f"Tafadhali wasilisha taarifa inayoonyesha *historia ya miezi 3 kamili au na zaidi ya miamala.*"
            )

        elif isinstance(affordability_data, dict):
            high_risk = affordability_data.get("high", 0.0)
            medium_risk = affordability_data.get("moderate", 0.0)
            low_risk = affordability_data.get("low", 0.0)
            max_credit = max(high_risk, medium_risk, low_risk)

            return (
                f"TZS {'{0:,.0f}'.format(max_credit)} (Kulingana na uchambuzi wa taarifa zako, Kiwango chako cha Juu Kabisa)\n\n"
                f"High: TZS {'{0:,.0f}'.format(high_risk)}\n"
                f"Medium: TZS {'{0:,.0f}'.format(medium_risk)}\n"
                f"Low: TZS {'{0:,.0f}'.format(low_risk)}\n\n"
                f"Tunapendekeza uanze na kiwango cha chini kwa urejeshaji wa haraka; kiwango cha mkopo kitakavyoongezeka kadiri unavyorejesha."
            )

        else:
            logger.error(f"Unexpected data type: {type(affordability_data)}")
            return analyze_file_with_gemini(file_data, filename)

    except requests.exceptions.Timeout:
        logger.error("Manka API timed out.")
        return analyze_file_with_gemini(file_data, filename)

    except EnvironmentError as e:
        logger.error(f"Manka Config Error: {e}")
        return analyze_file_with_gemini(file_data, filename)

    except Exception as e:
        logger.exception(f"General Error analyzing PDF with Manka: {e}")
        return analyze_file_with_gemini(file_data, filename)
