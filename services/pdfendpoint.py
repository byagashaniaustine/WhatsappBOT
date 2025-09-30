import os
import requests

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
                
            return f"⚠️ Manka Processing Failed: {error_message}"
        
        result = response.json()
        
        return result.get("summary") or result.get("text") or "⚠️ Manka returned no summary."

    except requests.exceptions.Timeout:
        return "⚠️ Manka API timed out. Please try again later."
    except Exception as e:
        return f"⚠️ General Error analyzing PDF: {type(e).__name__}: {str(e)}"