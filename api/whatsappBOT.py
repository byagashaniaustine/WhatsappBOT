import logging
import math
from services.meta import send_meta_whatsapp_message
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("whatsapp_app")

# --- PLACEHOLDER FOR LOAN CALCULATION LOGIC ---
async def loan_calc(data: dict):
    """
    Handles the initiation of the loan calculation process. 
    This is where the bot would ask for the required parameters (repayment amount, duration, rate).
    """
    from_number_full = str(data.get("From") or "")
    
    # Standardize number to E.164 format (Meta prefers +<CountryCode><Number>)
    if from_number_full and not from_number_full.startswith("+"):
        # We assume the number is a complete international number but just missing the '+' prefix.
        from_number_full = "+" + from_number_full

    # MESSAGE TRANSLATED TO SWAHILI
    message = (
        "✍️ *Kikokotoo cha Mkopo*:\n"
        "Tafadhali tuma maelezo yako ya kikokotoo katika muundo huu ili kufanya ukokotozi:\n"
        "*Kiasi: [uwezo wa kulipa], Muda: [miezi], Riba: [asilimia ya mwaka]*\n\n"
        "Mfano: *Kiasi: 200000, Muda: 12, Riba: 18*"
    )
    send_meta_whatsapp_message(to=from_number_full, body=message)
    logger.info(f"Loan calculator prompt sent to {from_number_full}")
    return PlainTextResponse("OK")

# --- WHATSAPP MENU DATA (Translated to Swahili) ---
main_menu = {
    "1": {
        "title": "Jifunze kuhusu Alama ya Mikopo (Credit Scoring)",
        "description": (
            "Hii ni kipimo kinachoonyesha **uaminifu wako wa kifedha** na historia yako ya ulipaji wa mikopo ya zamani. "
            "Alama nzuri ni *muhimu sana* kwa sababu inakupa fursa ya kupata **mikopo haraka zaidi**, kwa **viwango vya riba vya chini**, "
            "na kwa **kiasi kikubwa zaidi** kutoka taasisi za kifedha. Kudumisha alama nzuri kunahitaji ulipaji wa deni kwa wakati "
            "na kutotumia zaidi ya kikomo chako cha mkopo."
        )
    },
    "2": {
        "title": "Upana wa Mikopo (Credit Bandwidth)",
        "description": (
            "Upana wa Mikopo unaonyesha **kiasi cha juu zaidi** cha mkopo ambacho taasisi za kifedha zinaweza kukupa. "
            "Kiasi hiki huhesabiwa kwa kuchambua *mapato yako*, *madeni yako ya sasa*, na *historia yako ya ulipaji*. "
            "Upana mkubwa wa mikopo hukupa uwezo wa kujadiliana vizuri na kuchukua mikopo mikubwa zaidi kwa ajili ya uwekezaji au miradi mikubwa."
        )
    },
    "3": {
        "title": "Nakopesheka!!",
        "description": (
            "🔥 **Tuma Taarifa Zako za Kifedha:**\n"
            "Ili kuanza mchakato wa *Nakopesheka*, tafadhali **ambatanisha** faili ya PDF au picha iliyo na *taarifa zako za miamala/malipo* (Taarifa ya Benki/Taarifa za M-Pesa) kwa **angalau miezi mitatu (3)**. \n\n"
            "Mfumo wetu utaichambua kiotomatiki na kukupa jibu."
        )
    },
    "4": {
        "title": "Kikokotoo cha Mkopo",
        "description": (
            "Tumia kikokotoo chetu cha mkopo kujua kiasi gani cha mkopo unachostahili kulingana na uwezo wako wa kulipa kila mwezi, muda wa mkopo, na kiwango cha riba.\n"
            "Tuma neno *CALC* ili kuanza mchakato wa kuingiza vigezo vya kikokotoo."
        )
    },
    "5": {
        "title": "Aina za Mikopo",
        "description": (
            "Mikopo huwekwa katika makundi kulingana na **Dhamana/Madhumuni** na **Aina ya Kiwango cha Riba**.\n"
            "   * **Mikopo kulingana na Madhumuni/Dhamana:** Hii ni pamoja na **Mkopo wa Nyumba** (muda mrefu, riba ya chini), "
            "**Mkopo wa Biashara** (kwa upanuzi wa biashara), **Mkopo wa Elimu** (kwa masomo), na **Mkopo wa Haraka/Simu ya Mkononi** (kwa mahitaji ya ghafla, muda mfupi).\n"
            "   * **Mikopo kulingana na Aina ya Kiwango cha Riba:** Hii ni pamoja na **Kiwango Kisichobadilika** (riba haibadilika katika muda wote), "
            "**Kiwango Kinachobadilika** (riba inayobadilika kulingana na soko), n.k. Kuelewa aina hizi hukusaidia kuchagua mkopo unaofaa zaidi."
        )
    },
    "6": {
        "title": "Huduma za Nilipo (Where I Am)",
        "description": (
            "Huduma zinazotolewa kwa sasa ni pamoja na: manunuzi madogo, malipo ya kidijitali, gharama za dharura, mikopo ya muda mfupi."
        )
    }
}


# --- MAIN WHATSAPP MENU HANDLER ---
async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        
        # ⚠️ CRITICAL FIX: Standardize number to E.164 format (Meta requires +<CountryCode><Number>)
        if from_number_full and not from_number_full.startswith("+"):
            from_number_full = "+" + from_number_full
            
        if not from_number_full or from_number_full == "+": # Check for empty or just "+"
            logger.warning("Missing 'From' number in request after standardization.")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip()
        incoming_msg_lower = incoming_msg.lower()

        # --- Show main menu (SWAHILI TRANSLATION) ---
        if incoming_msg_lower in ["hi", "hello", "start", "menu","main menu", "yo","good morning","good evening","anza","good afternoon","habari","mambo"]:
            reply_text = (
                " *Karibu kwenye Huduma za Mikopo za Manka*\n"
                " Chagua huduma unayopenda kuhudumiwa:\n\n"
                "1️⃣ Jifunze kuhusu Alama ya Mikopo\n"
                "2️⃣ Upana wa Mikopo\n"
                "3️⃣ Nakopesheka!!\n"
                "4️⃣ Kikokotoo cha Mkopo\n"
                "5️⃣ Aina za Mikopo\n"
                "6️⃣ Huduma zinazotolewa kwa Mikopo"
            )
            send_meta_whatsapp_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Handle specific commands/selections ---
        
        # Option 4 Direct Trigger Command
        if incoming_msg_lower == "calc":
            return await loan_calc(data)

        # Handle menu selection 
        elif incoming_msg_lower in main_menu:
            selection = incoming_msg_lower
            
            # 3. Nakopesheka!! (Instruct user to send file/media upload)
            if selection == "3":
                item = main_menu[selection]
                reply_text = f"*{item['title']}*\n\n{item['description']}"
                send_meta_whatsapp_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")
                
            # 4. Loan Calculator (Call the loan calculation initiation function)
            elif selection == "4":
                return await loan_calc(data)

            # All other menu options (1, 2, 5, 6) just send the description
            else:
                item = main_menu[selection]
                reply_text = f"*{item['title']}*\n{item['description']}"
                send_meta_whatsapp_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")

        # --- Fallback (SWAHILI TRANSLATION) ---
        send_meta_whatsapp_message(to=from_number_full, body="Samahani, sielewi. Jibu kwa 'menu' au 'anza' ili kuona huduma zetu.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")

        try:
            # Safely send a user-friendly error message if sender info is available (SWAHILI TRANSLATION)
            from_number_safe = locals().get("from_number_full", None)
            if from_number_safe:
                send_meta_whatsapp_message(
                    to=from_number_safe,
                    body="❌ Samahani, hitilafu ya kiufundi imetokea. Tafadhali jaribu tena au tuma 'menu'."
                )
        except Exception as inner_error:
            logger.warning(f"⚠️ Failed to send error message: {inner_error}")
            pass  # Suppress further errors

        return PlainTextResponse("Internal Server Error", status_code=500)