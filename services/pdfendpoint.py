import os
import requests
import logging

logger = logging.getLogger(__name__)

MANKA_API_KEY = os.environ.get("MANKA_API_KEY")
MANKA_ENDPOINT = os.environ.get("MANKA_ENDPOINT") 

if not MANKA_API_KEY or not MANKA_ENDPOINT:
    raise EnvironmentError("MANKA_API_KEY or MANKA_ENDPOINT not set!")

def analyze_pdf(file_data: bytes, filename: str, user_fullname: str) -> str:
    
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
            MANKA_ENDPOINT, 
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
                return "⚠️ System Error: Analysis structure invalid. Missing 'affordability_scores'."

        else:
            logger.error(f"Unexpected top-level data structure: {type(response_data)}. Full response data: {response_data}")
            return "⚠️ System Error: Manka returned an unexpected top-level data structure. Please contact support."

        if isinstance(affordability_data, str):
            logger.warning(f"Affordability calculation notice received: {affordability_data}")
            
            return (
                f"*❌ Loan Qualification Status: INSUFFICIENT DATA*\n"
                f"*---------------------------------------------*\n\n"
                f"We were unable to process a credit offer because:\n"
                f"*{affordability_data}.*\n\n"
                f"To qualify, please submit a statement covering *a minimum of 3 full months* of transaction history."
            )
            
        elif isinstance(affordability_data, dict):
            high_risk = affordability_data.get('high_risk', 0.0)
            medium_risk = affordability_data.get('moderate_risk', 0.0)
            low_risk = affordability_data.get('low_risk', 0.0)
        
    

            max_credit = max(high_risk, medium_risk, low_risk)
            
            report = (
                f"*✅ Loan Qualification Status: QUALIFIED*\n"
                f"*---------------------------------------------*\n\n"
                f"Based on your statement analysis, you are *eligible for credit* up to:\n\n"
                f"*{'TZS {0:,.0f}'.format(max_credit)}* (Maximum Potential Offer)\n\n"
                f"*Detailed Credit Tiers:*\n"
                f"--- 1. *High Risk* Limit: TZS {high_risk:,.0f}\n"
                f"--- 2. *Moderate Risk* Limit: TZS {medium_risk:,.0f}\n"
                f"--- 3. *Low Risk* Limit: TZS {low_risk:,.0f}\n\n"
                f"We recommend starting with a low-risk offer for fast approval."
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
