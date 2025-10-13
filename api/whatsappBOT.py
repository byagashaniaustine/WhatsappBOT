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
                    "Ni kipimo kinachoonyesha uaminifu wako wa kifedha. "
                    "Benki hutumia alama hii kuamua kama unastahili kukopeshwa. "
                    "Lipa kwa wakati na tumia mikopo kwa uangalifu ili kuboresha alama yako."
                )
            },
            "2": {
                "title": "Uwezo wa Mikopo (Credit Bandwidth)",
                "description": (
                    "Ni kiwango cha fedha ambacho unaweza kukopeshwa kulingana na hali yako ya kifedha na historia ya ulipaji. "
                    "Kadri unavyolipa kwa wakati na kuwa na alama nzuri ya mkopo, ndivyo uwezo wako wa kukopa unavyoongezeka."
                )
            },
            "3": {
                "title": "Nakopesheka!!",
                "description": (
                    "Kwa huduma ya Nakopesheka, tafadhali jaza fomu hii ya Google kwa taarifa zako na uambatanishe ya nyaraka za malipo na miamala za miezi isiopungua miezi 3:\n"
                    "📄 Google Form: google form:https://docs.google.com/forms/d/e/1FAIpQLScctiesPi8OaDu2tVW-Ke396v7XJmY43m01BXE-E3ov58Ph0g/viewform?usp=header"
                )
            },
            "4": {
                "title": "Kikokotoo cha Mkopo (Loan Calculator)",
                "description": (
                    "Ili kukokotoa mkopo, tafadhali jaza fomu hii ya Google na weka kiasi cha pesa cha marejesho,mda wa marejesho,na kiasi cha riba:\n"
                    "💰 Google Form: https://forms.gle/EXAMPLE_LOAN_CALCULATOR"
                )
            },
            "5": {
                "title": "Aina za Mikopo",
                "description": (
                    "Mikopo inaweza kugawanyika kwa njia mbili: kwa riba au kwa lengo/dhamana. "
                    "Mfano: Fixed, Variable, Floating, Capped, Mkopo wa Simu, Gari, Nyumba, Biashara, Elimu, Haraka."
                )
            },
            "6": {
                "title": "Huduma za Nilipo",
                "description": (
                    "Huduma zinazotolewa sasa ni pamoja na: kununua bidhaa ndogo, malipo ya kidijitali, gharama za dharura, mikopo ya muda mfupi."
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
