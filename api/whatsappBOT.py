import logging
from services.twilio import send_message
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("whatsapp_app")

async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        from_number = from_number_full.replace("whatsapp:", "")

        if not from_number:
            logger.warning("Missing 'From' number in request")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip().lower()
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
            "Kwa huduma ya Nakopesheka, tafadhali jaza fomu hii ya Google kwa taarifa zako na uambatanishe ya nyaraka za malipo na miamala za miezi isiopungua miezi 3:\n"
            "📄 Google Form: google form:https://docs.google.com/forms/d/e/1FAIpQLSdOL1-gUYj8SG_D9o06Qq_pMFBJVc_ihHzLtF8TUmeA0_QDvA/viewform?usp=header"
        )
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": (
            "Ili kukokotoa mkopo, tafadhali jaza fomu hii ya Google na weka kiasi cha pesa cha marejesho,mda wa marejesho,na kiasi cha riba:\n"
            "💰 Google Form: https://docs.google.com/forms/d/e/1FAIpQLSdHiaWEqm9w9LqK71ipdCks6nQpZ-2ZszyLhYkFpuCxkbh98w/viewform?usp=header"
        )
    },
    "5": {
        "title": "Aina za Mikopo",
        "description": (
            "Mikopo huwekwa katika kategoria kulingana na **Dhamana/Lengo** na **Aina ya Riba**.\n"
            "   * **Mikopo Kulingana na Lengo/Dhamana:** Hujumuisha **Mkopo wa Nyumba** (kwa muda mrefu, riba ya chini), "
            "**Mkopo wa Biashara** (kupanua biashara), **Mkopo wa Elimu** (kwa masomo),
    )
    }
    }
    
        # --- Show main menu ---
        if incoming_msg in ["hi", "hello", "start", "menu", ""]:
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

        # --- Handle menu selection ---
        elif incoming_msg in main_menu:
            item = main_menu[incoming_msg]
            reply_text = f"*{item['title']}*\n{item['description']}"
            send_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Fallback ---
        send_message(to=from_number_full, body="Samahani, sikuelewi. Jibu na neno 'menu' ili kuona huduma zetu.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)
