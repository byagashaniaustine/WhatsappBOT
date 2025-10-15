import os
import requests
import logging

logger = logging.getLogger(__name__)

MANKA_API_KEY = os.environ.get("MANKA_API_KEY")
MANKA_ENDPOINT = os.environ.get("MANKA_ENDPOINT") 

if not MANKA_API_KEY or not MANKA_ENDPOINT:
    raise EnvironmentError("MANKA_API_KEY or MANKA_ENDPOINT not set!")

def analyze_pdf(file_data: bytes, filename: str, user_fullname: str) -> str:
    """
    Sends a PDF file to the Manka API for affordability analysis and returns 
    the result status or an error message in Swahili.
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {MANKA_API_KEY}",
        }

        data = {
            "fullname": user_fullname, 
        }

        files = {
            'file': (filename, file_data, 'application/pdf') 
        }

        response = requests.post(
            str(MANKA_ENDPOINT), 
            headers=headers, 
            data=data,          
            files=files,          
            timeout=60
        )
        
        if not response.ok:
            error_message = f"Manka API returned HTTP {response.status_code}."
            
            try:
                details = response.json()
                error_content = details.get("message") or details.get("error") or "Unknown API Error"
                error_message += f" Details: {error_content}"
            except requests.exceptions.JSONDecodeError:
                error_message += f" Body: Non-JSON response received. Starts with: '{response.text[:30]}...'"
                
            logger.error(f"MANKA FAILED: {error_message}")
            return f"⚠️ Manka Processing Failed: {error_message}. Please check API key and endpoint."
        
        response_data = response.json()
        affordability_data = None
        
        if isinstance(response_data, dict):
            logger.warning(response_data)
            affordability_data = response_data.get('affordability_scores')
            
            if affordability_data is None:
                logger.error("Manka returned a dictionary but was missing the expected 'affordability_scores' key.")
                # CORRECTED SWHILI TRANSLATION for missing key
                return "⚠️ Hitilafu ya Mfumo: Muundo wa uchambuzi si sahihi: 'affordability_scores' inakosekana. Tafadhali wasiliana na huduma kwa wateja."
                
        else:
            logger.error(f"Unexpected top-level data structure: {type(response_data)}. Full response data: {response_data}")
            # Corrected SWHILI TRANSLATION for unexpected top-level structure
            return "⚠️ Hitilafu ya Mfumo: Manka amerudisha muundo wa data wa ngazi ya juu usiotarajiwa. Tafadhali wasiliana na huduma kwa wateja."

        if isinstance(affordability_data, str):
            logger.warning(f"Affordability calculation notice received: {affordability_data}")
            
            # Swahili message for INSUFFICIENT DATA
            return (
                f"❌ Hali ya Kufuzu kwa Mkopo: DATA HAITOSHI (INSUFFICIENT DATA)\n"
                f"---------------------------------------------\n\n"
                f"Hatukuweza kutoa ofa ya mkopo kwa sababu:\n"
                f"*{affordability_data}.*\n\n"
                f"Ili kufuzu, tafadhali wasilisha taarifa inayoonyesha *kiwango cha chini cha miezi 3 kamili* ya historia ya miamala."
            )
            
        elif isinstance(affordability_data, dict):
            # Safe retrieval with defaults in case of missing keys, preventing calculation errors
            high_risk = affordability_data.get('high', 0.0)
            medium_risk = affordability_data.get('moderate', 0.0)
            low_risk = affordability_data.get('low', 0.0)
            
            max_credit = max(high_risk, medium_risk, low_risk)
            
            # Swahili message for QUALIFIED
            report = (
                f"✅ Hali ya Kufuzu kwa Mkopo: UMEKUBALIKA (QUALIFIED)\n"
                f"---------------------------------------------\n\n"
                f"Kulingana na uchambuzi wa taarifa zako, unakubalika kupata mkopo usiozidi:\n\n"
                f"TZS {'{0:,.0f}'.format(max_credit)} (Uwezo wa Juu Kabisa wa Ofa)\n\n"
                f"Viwango vya Mikopo Kina:\n"
                f"--- 1. Kiwango cha Hatari Juu (High Risk): TZS {'{0:,.0f}'.format(high_risk)}\n"
                f"--- 2. Kiwango cha Hatari ya Kati (Moderate Risk): TZS {'{0:,.0f}'.format(medium_risk)}\n"
                f"--- 3. Kiwango cha Hatari Chini (Low Risk): TZS {'{0:,.0f}'.format(low_risk)}\n\n"
                f"Tunapendekeza uanze na ofa ya kiwango cha hatari chini kwa ajili ya idhini ya haraka."
            )

            return report

        else:
            logger.error(f"Unexpected data type for affordability scores: {type(affordability_data)}. Full response data: {response_data}")
            return "⚠️ System Error: Affordability data type invalid. Please contact support."


    except requests.exceptions.Timeout:
        logger.error("Manka API timed out.")
        return "⚠️ Manka Processing Failed: The API timed out. Please try again later."
    except Exception as e:
        logger.exception(f"General Error analyzing PDF.")
        return f"⚠️ General System Error analyzing PDF: {type(e).__name__}: {str(e)}"
