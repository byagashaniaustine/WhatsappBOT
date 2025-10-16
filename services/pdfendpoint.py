import os
import requests
import logging
from services.gemini import analyze_file_with_gemini  # <-- import from gemini.py

logger = logging.getLogger(__name__)


MANKA_API_KEY = os.environ.get("MANKA_API_KEY")
MANKA_ENDPOINT = os.environ.get("MANKA_ENDPOINT") 

if not MANKA_API_KEY or not MANKA_ENDPOINT:
    logger.warning("MANKA_API_KEY or MANKA_ENDPOINT not set. Only Gemini fallback will be functional.")

def analyze_pdf(file_data: bytes, filename: str, user_fullname: str) -> str:
    """
    Attempts analysis with Manka. If Manka fails with a non-recoverable error 
    (HTTP failure or structural error), it uses Gemini as a fallback.
    """
    try:
        # 1. Check Manka configuration
        if not MANKA_API_KEY or not MANKA_ENDPOINT:
            raise EnvironmentError("Manka environment variables are missing.")

        headers = {
            "Authorization": f"Bearer {MANKA_API_KEY}",
        }

        data = {"fullname": user_fullname}
        files = {'file': (filename, file_data, 'application/pdf')}

        # 2. Send request to Manka API
        response = requests.post(
            str(MANKA_ENDPOINT),
            headers=headers,
            data=data,
            files=files,
            timeout=60
        )

        # 3. HTTP Error → Fallback
        if not response.ok:
            logger.error(f"MANKA FAILED (HTTP {response.status_code}): {response.text[:100]}")
            return analyze_file_with_gemini(file_data, filename)

        response_data = response.json()
        affordability_data = response_data.get('affordability_scores')

        # 4. Missing structure → Fallback
        if affordability_data is None:
            logger.error("Manka response missing 'affordability_scores' key.")
            return analyze_file_with_gemini(file_data, filename)

        # 5. Handle Manka results
        if isinstance(affordability_data, str):
            return (
                f"❌ Hali ya Kufuzu kwa Mkopo: DATA HAITOSHI (INSUFFICIENT DATA)\n"
                f"---------------------------------------------\n\n"
                f"Hatukuweza kutoa ofa ya mkopo kwa sababu:\n"
                f"*{affordability_data}.*\n\n"
                f"Tafadhali wasilisha taarifa inayoonyesha *historia ya miezi 3 kamili ya miamala.*"
            )

        elif isinstance(affordability_data, dict):
            high_risk = affordability_data.get('high', 0.0)
            medium_risk = affordability_data.get('moderate', 0.0)
            low_risk = affordability_data.get('low', 0.0)
            max_credit = max(high_risk, medium_risk, low_risk)

            return (
                f"✅ Hali ya Kufuzu kwa Mkopo: UMEKUBALIKA (QUALIFIED)\n"
                f"---------------------------------------------\n\n"
                f"Kulingana na uchambuzi wa taarifa zako, unakubalika kupata mkopo usiozidi:\n\n"
                f"TZS {'{0:,.0f}'.format(max_credit)} (Uwezo wa Juu Kabisa wa Ofa)\n\n"
                f"Viwango vya Hatari:\n"
                f"--- High Risk: TZS {'{0:,.0f}'.format(high_risk)}\n"
                f"--- Moderate Risk: TZS {'{0:,.0f}'.format(medium_risk)}\n"
                f"--- Low Risk: TZS {'{0:,.0f}'.format(low_risk)}\n\n"
                f"Tunapendekeza uanze na kiwango cha hatari chini kwa idhini ya haraka."
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
