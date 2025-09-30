import os
import requests
import logging

# Set up basic logging
logger = logging.getLogger(__name__)

# Environment variables are loaded once at module import
MANKA_API_KEY = os.environ.get("MANKA_API_KEY")
MANKA_ENDPOINT = os.environ.get("MANKA_ENDPOINT") 

if not MANKA_API_KEY or not MANKA_ENDPOINT:
    # This will cause the application to crash on startup if variables are missing
    raise EnvironmentError("MANKA_API_KEY or MANKA_ENDPOINT not set!")

def analyze_pdf(file_data: bytes, filename: str, user_fullname: str) -> str:
    """
    Sends a PDF file to the Manka Affordability API for credit scoring analysis
    and formats the resulting risk tiers into a user-facing report.
    """
    
    try:
        # 1. Prepare Request Headers and Data
        headers = {
            "Authorization": f"Bearer {MANKA_API_KEY}",
        }

        data = {
            "fullname": user_fullname, 
        }

        files = {
            # Manka expects the file under the 'file' field
            'file': (filename, file_data, 'application/pdf') 
        }

        # 2. Make the API Call to the Affordability Endpoint
        response = requests.post(
            MANKA_ENDPOINT, 
            headers=headers, 
            data=data,           
            files=files,         
            timeout=60 # Set a generous timeout for file processing
        )
        
        # 3. Handle HTTP Errors (Non-200 Status Codes)
        if not response.ok:
            error_message = f"Manka API returned HTTP {response.status_code}."
            
            try:
                # Attempt to extract detailed error message from JSON response
                details = response.json()
                error_content = details.get("message") or details.get("error") or "Unknown API Error"
                error_message += f" Details: {error_content}"
            except requests.exceptions.JSONDecodeError:
                # API returned a non-JSON body (e.g., HTML error page)
                error_message += f" Body: Non-JSON response received. Starts with: '{response.text[:30]}...'"
                
            logger.error(f"MANKA FAILED: {error_message}")
            return f"⚠️ Manka Processing Failed: {error_message}"
        
        # 4. Handle Successful Response (200 OK)
        result = response.json()
        
        # Check if the expected credit scores are present in the JSON result
        high_risk = result.get('high_risk', 0.0)
        medium_risk = result.get('medium_risk', 0.0)
        low_risk = result.get('low_risk', 0.0)

        if not any([high_risk, medium_risk, low_risk]):
             logger.warning(f"Manka returned valid 200, but no credit scores found. Response: {result}")
             return "⚠️ Manka Analysis Complete, but no specific credit score data was returned. Please try another statement."

        # 5. Format the Loan Offer Report for WhatsApp
        
        # The highest risk is the maximum credit amount
        max_credit = max(high_risk, medium_risk, low_risk)
        
        report = (
            f"*💰 Financial Statement Analysis Report*\n"
            f"*----------------------------------*\n\n"
            f"Based on your statement analysis, you are *eligible for credit* up to:\n\n"
            f"*{'TZS {0:,.0f}'.format(max_credit)}* (Max Potential Offer)\n\n"
            f"*Detailed Credit Tiers:*\n"
            f"--- 1. *High Risk* Limit: TZS {high_risk:,.0f}\n"
            f"--- 2. *Moderate Risk* Limit: TZS {medium_risk:,.0f}\n"
            f"--- 3. *Low Risk* Limit: TZS {low_risk:,.0f}\n\n"
            f"We recommend starting with a low-risk offer for fast approval."
        )

        return report

    except requests.exceptions.Timeout:
        logger.error("Manka API timed out.")
        return "⚠️ Manka API timed out. Please try again later."
    except Exception as e:
        logger.exception(f"General Error analyzing PDF.")
        return f"⚠️ General System Error analyzing PDF: {type(e).__name__}: {str(e)}"
