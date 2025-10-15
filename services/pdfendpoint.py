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
                error_content = details.get("message") or details.get("error") or "Hitilafu Isiyojulikana ya API"
                error_message += f" Maelezo: {error_content}"
            except requests.exceptions.JSONDecodeError:
                error_message += f" Sehemu ya Jibu: Jibu lisilo la JSON lilipokewa. Linaanza na: '{response.text[:30]}...'"
                
            logger.error(f"MANKA FAILED: {error_message}")
            
            # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
            return (
                f"⚠️ *Kushindwa Kusindika na Manka*: Hatukuweza kukamilisha uchambuzi wa hati yako."
                f"\n\nMaelezo ya ndani: {error_content}. Tafadhali thibitisha Ufunguo wa API (API Key) na MANKA_ENDPOINT."
            )
            # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---
        
        response_data = response.json()
        affordability_data = None
        
        if isinstance(response_data, dict):
            logger.warning(response_data)
            affordability_data = response_data.get('affordability_scores')
            
            if affordability_data is None:
                logger.error("Manka returned a dictionary but was missing the expected 'affordability_scores' key.")
                # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
                return "⚠️ *Hitilafu ya Mfumo*: Muundo wa uchambuzi haufai. Sehemu ya 'affordability_scores' haipo. Tafadhali wasiliana na usaidizi."
                # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---

        else:
            logger.error(f"Unexpected top-level data structure: {type(response_data)}. Full response data: {response_data}")
            # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
            return "⚠️ *Hitilafu ya Mfumo*: Manka imerejesha muundo wa data usiotarajiwa. Tafadhali wasiliana na usaidizi."
            # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---

        if isinstance(affordability_data, str):
            logger.warning(f"Affordability calculation notice received: {affordability_data}")
            
            # --- UJUMBE WA DATA HAIKUTOSHA KWA KISWAHILI ---
            return (
                f"*❌ Hali ya Kustahili Mkopo: DATA HAIKUTOSHA*\n"
                f"*---------------------------------------------*\n\n"
                f"Hatukuweza kukamilisha utaratibu wa kutoa mkopo kwa sababu:\n"
                f"*{affordability_data}.*\n\n"
                f"Ili kustahili, tafadhali tuma taarifa inayoonyesha *kiwango cha chini cha miezi 3 kamili* ya miamala yako."
            )
            # --- MWISHO UJUMBE WA DATA HAIKUTOSHA KWA KISWAHILI ---
            
        elif isinstance(affordability_data, dict):
            high_risk = affordability_data.get('high_risk', 0.0)
            medium_risk = affordability_data.get('medium_risk', 0.0)
            low_risk = affordability_data.get('low_risk', 0.0)
        
            max_credit = max(high_risk, medium_risk, low_risk)
            
            # --- UJUMBE WA MAFANIKIO KWA KISWAHILI ---
            report = (
                f"*✅ Hali ya Kustahili Mkopo: UMESTAHILI*\n"
                f"*---------------------------------------------*\n\n"
                f"Kulingana na uchambuzi wa taarifa yako, *unastahili kupata mkopo* hadi kiwango cha:\n\n"
                f"*{'TZS {0:,.0f}'.format(max_credit)}* (Kiwango cha Juu cha Mkopo)\n\n"
                f"*Viainisho vya Mikopo Vya Kina:*\n"
                f"--- 1. *Hatari Kubwa*: TZS {high_risk:,.0f}\n"
                f"--- 2. *Hatari ya Kati*: TZS {medium_risk:,.0f}\n"
                f"--- 3. *Hatari Ndogo*: TZS {low_risk:,.0f}\n\n"
                f"Tunapendekeza kuanza na mkopo wa Hatari Ndogo kwa idhini ya haraka."
            )
            # --- MWISHO UJUMBE WA MAFANIKIO KWA KISWAHILI ---

            return report

        else:
            logger.error(f"Unexpected data type for affordability scores: {type(affordability_data)}. Full response data: {response_data}")
            # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
            return "⚠️ *Hitilafu ya Mfumo*: Aina ya data ya uchambuzi haifanyi kazi. Tafadhali wasiliana na usaidizi."
            # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---


    except requests.exceptions.Timeout:
        logger.error("Manka API timed out.")
        # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
        return "⚠️ *Kushindwa Kusindika na Manka*: Muunganisho wa API umeisha muda (timed out). Tafadhali jaribu tena baada ya muda mfupi."
        # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---
    except Exception as e:
        logger.exception(f"General Error analyzing PDF.")
        # --- UJUMBE WA HITILAFU KWA KISWAHILI ---
        return f"⚠️ *Hitilafu ya Mfumo Mkuu*: Kulikuwa na shida ya jumla wakati wa kuchambua hati. Tafadhali wasiliana na usaidizi."
        # --- MWISHO UJUMBE WA HITILAFU KWA KISWAHILI ---
