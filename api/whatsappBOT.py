import logging
import math
from services.twilio import send_message
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("whatsapp_app")

# --- PLACEHOLDER FOR LOAN CALCULATION LOGIC ---
async def loan_calc(data: dict):
    """
    Handles the initiation of the loan calculation process. 
    This is where the bot would ask for the required parameters (repayment amount, duration, rate).
    """
    from_number_full = str(data.get("From") or "")
    
    # Message instructing the user how to provide the input parameters
    message = (
        "✍️ *Kikokotoo cha Mkopo*:\n"
        "Tafadhali tuma taarifa zako za kikokotoo katika muundo huu ili kufanya hesabu:\n"
        "*Kiasi: [uwezo wa kurejesha], Muda: [miezi], Riba: [asilimia ya mwaka]*\n\n"
        "Mfano: *Kiasi: 200000, Muda: 12, Riba: 18*"
    )
    send_message(to=from_number_full, body=message)
    logger.info(f"Loan calculator prompt sent to {from_number_full}")
    return PlainTextResponse("OK")

# --- WHATSAPP MENU DATA (Updated) ---
main_menu = {
    "1": {
        "title": "Jifunze kuhusu Alama ya Mkopo (Credit Scoring)",
        "description": (
            "Ni kipimo kinachoonyesha **uaminifu wako wa kifedha** na rekodi yako ya ulipaji wa mikopo ya zamani. "
            "Alama nzuri ni *muhimu* sana kwa sababu inakupa fursa ya kupata **mikopo kwa haraka**, kwa **riba ndogo zaidi**, "
            "na kwa **viwango vya juu zaidi** kutoka kwa taasisi za kifedha. Kudumisha alama nzuri kunahitaji ulipaji wa deni "
            "kwa wakati na kutotumia zaidi ya kiwango chako cha mkopo."
        )
    },
    "2": {
        "title": "Uwezo wa Mikopo (Credit Bandwidth)",
        "description": (
            "Uwezo wa Mikopo huashiria **kiwango cha juu zaidi** cha mkopo ambao taasisi za kifedha zinaweza kukuachilia. "
            "Kiasi hiki huhesabiwa kwa kuchambua *kipato* chako, *madeni* yako ya sasa, na *historia yako ya ulipaji*. "
            "Uwezo mkubwa wa mikopo hukupa uwezo wa kujadiliana vyema na kuchukua mikopo mikubwa kwa ajili ya uwekezaji au miradi mikubwa."
        )
    },
    "3": {
        "title": "Nakopesheka!!",
        "description": (
            "🔥 **Tuma Taarifa Zako za Kifedha:**\n"
            "Ili kuanza mchakato wa *Nakopesheka*, tafadhali **ambatanisha** (attach) faili la PDF au picha lenye *taarifa zako za miamala/malipo* (Bank Statement/M-Pesa statements) za **miezi isiyopungua mitatu (3)**. \n\n"
            "Mfumo wetu utaichambua moja kwa moja na kukupa majibu."
        )
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": (
            "Tumia kikokotoo chetu cha mkopo kujua ni kiasi gani cha mkopo unastahili kupata kulingana na uwezo wako wa kurejesha kila mwezi, muda wa mkopo, na riba.\n"
            "Tuma neno *CALC* ili kuanza mchakato wa kuingiza vigezo vya kikokotoo."
        )
    },
    "5": {
        "title": "Aina za Mikopo",
        "description": (
            "Mikopo huwekwa katika kategoria kulingana na **Dhamana/Lengo** na **Aina ya Riba**.\n"
            "   * **Mikopo Kulingana na Lengo/Dhamana:** Hujumuisha **Mkopo wa Nyumba** (kwa muda mrefu, riba ya chini), "
            "**Mkopo wa Biashara** (kupanua biashara), **Mkopo wa Elimu** (kwa masomo), na **Mkopo wa Haraka/Simu** (kwa mahitaji ya ghafla, muda mfupi).\n"
            "   * **Mikopo Kulingana na Aina ya Riba:** Hizi ni pamoja na **Fixed Rate** (riba haibadiliki kwa muda wote), "
            "**Variable Rate** (riba inayobadilika kulingana na soko), n.k. Kuelewa aina hizi hukusaidia kuchagua mkopo unaofaa zaidi."
        )
    },
    "6": {
        "title": "Huduma za Nilipo",
        "description": (
            "Huduma zinazotolewa sasa ni pamoja na: kununua bidhaa ndogo, malipo ya kidijitali, gharama za dharura, mikopo ya muda mfupi."
        )
    }
}


# --- MAIN WHATSAPP MENU HANDLER ---
async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        from_number = from_number_full.replace("whatsapp:", "")

        if not from_number:
            logger.warning("Missing 'From' number in request")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip()
        incoming_msg_lower = incoming_msg.lower()

        # --- Show main menu ---
        if incoming_msg_lower in ["hi", "hello", "start", "menu","main menu", "yo","good morning","good evening","anza","good afternoon","habari","mambo"]:
            reply_text = (
                " *Karibu katika huduma ya mikopo ya Manka*\n"
                " Chagua huduma ungependa uhudumiwe:\n\n"
                "1️⃣ Jifunze kuhusu Alama za Mkopo\n"
                "2️⃣ Kiwango cha Mkopo\n"
                "3️⃣ Nakopesheka!!\n"
                "4️⃣ Kikokotoo cha Mkopo\n"
                "5️⃣ Aina za Mikopo\n"
                "6️⃣ Huduma zinazotolewa kwa Mkopo"
            )
            send_message(to=from_number_full, body=reply_text)
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
                send_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")
                
            # 4. Kikokotoo cha Mkopo (Call the loan calculation initiation function)
            elif selection == "4":
                # Instead of sending the full description, we call loan_calc to initiate the process immediately.
                return await loan_calc(data)

            # All other menu options (1, 2, 5, 6) just send the description
            else:
                item = main_menu[selection]
                reply_text = f"*{item['title']}*\n{item['description']}"
                send_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")

        # --- Fallback ---
        send_message(to=from_number_full, body="Samahani, sikuelewi. Jibu na neno 'menu','main menu','habari','mambo' au neno 'anza'  ili kuona huduma zetu.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")

        try:
            # Safely send a user-friendly error message if sender info is available
            from_number_safe = locals().get("from_number_full", None)
            if from_number_safe:
                send_message(
                    from_number_safe,
                    "❌ Samahani, kosa la kiufundi limetokea. Jaribu tena au tuma 'menu'."
                )
        except Exception as inner_error:
            logger.warning(f"⚠️ Failed to send error message: {inner_error}")
            pass  # Suppress further errors

        return PlainTextResponse("Internal Server Error", status_code=500)
