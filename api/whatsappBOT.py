# whatsappBOT.py - REVISED CODE

import logging
from services.twilio import send_message, trigger_twilio_flow, send_list_message_template 
from fastapi.responses import PlainTextResponse
from datetime import datetime, timezone

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        from_number = from_number_full.replace("whatsapp:", "")
        
        # --- FIX FOR LOG NOISE ---
        if not from_number:
            logger.warning("No 'From' number provided (Likely a health check or malformed request)")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip().lower()

        user_id = str(data.get("user_id") or "")
        user_name = str(data.get("user_name") or "")

        main_menu = {
            "1": {
                "title": "Jifunze kuhusu Alama ya Mkopo (Credit Scoring)",
                "description": "Ni kipimo kinachoonyesha uaminifu wako wa kifedha — yaani jinsi unavyolipa mikopo. Benki hutumia alama hii kuamua kama unastahili kukopeshwa. Inategemea mambo kama historia ya malipo, kiasi cha madeni, muda wa matumizi ya mikopo, na maombi mapya ya mikopo. Ukiwa na alama ya juu, unaonekana mwaminifu zaidi; ukishuka, ni vigumu kupata mkopo. Lipa kwa wakati na tumia mikopo kwa uangalifu ili kuboresha alama yako."
            },
            "2": {
                "title": "Uwezo wa Mikopo (Credit Bandwidth)",
                "description": "Ni kiwango cha juu cha fedha ambacho unaweza kukopeshwa kulingana na hali yako ya kifedha na historia ya ulipaji. Kadri unavyolipa kwa wakati na kuwa na alama nzuri ya mkopo, ndivyo uwezo wako wa kukopa unavyoongezeka. Ukiwa na madeni mengi au historia mbaya ya malipo, uwezo huu hupungua."
            },
            "3": {
                "title": "Nakopesheka!!",
                "action": "send_nakopesheka_list"
            },
            "4": {
                "title": "Kikokotoo cha Mkopo (Loan Calculator)",
                "action": "open_flow_loan_calculator"
            },
            "5": {
                "title": "Aina za Mikopo",
                "description": (
                    "Mikopo inaweza kugawanyika kwa njia mbili kuu:\n\n"
                    "**Kulingana na Riba:**\n"
                    "1. Fixed Loan – Riba hubaki ile ile, malipo ya kila mwezi hayabadiliki.\n"
                    "2. Variable Loan – Riba inaweza kubadilika kulingana na soko, malipo yanaweza kupanda au kushuka.\n"
                    "3. Floating Loan – Riba hubadilika mara kwa mara kulingana na viwango vya benki.\n"
                    "4. Capped Loan – Riba hubadilika lakini haizidi kiwango kilichowekwa.\n\n"
                    "**Kulingana na Lengo/Dhamana:**\n"
                    "1. Mkopo wa Simu – Mkopo wa kununua simu au vifaa vya kidijitali.\n"
                    "2. Mkopo wa Gari – Mkopo wa kununua gari, mara nyingi kwa dhamana ya gari hilo.\n"
                    "3. Mkopo wa Nyumba – Kwa kununua au kujenga nyumba, mara nyingi ni mkopo wa muda mrefu.\n"
                    "4. Mkopo wa Biashara – Kwa wajasiriamali au kampuni kusaidia kuendesha au kukuza biashara.\n"
                    "5. Mkopo wa Elimu – Husaidia kugharamia ada au mahitaji ya shule/chuo.\n"
                    "6. Mkopo wa Haraka – Kiasi kidogo cha mkopo cha dharura kinachotolewa haraka."
                )
            },
            "6": {
                "title": "Huduma za Nilipo",
                "description": (
                    "Huduma zinazoweza kutolewa kwa mkopo kupitia app hii kwa sasa ni pamoja na:\n"
                    "- Kununua bidhaa ndogo za kila siku\n"
                    "- Malipo ya huduma za kidijitali (kama internet, TV, au simu)\n"
                    "- Gharama za dharura au matengenezo madogo\n"
                    "- Mikopo ya muda mfupi kwa matumizi ya kifamilia\n\n"
                    "Baadaye huduma hizi zitaongezwa na kuwa maalumu zaidi."
                )
            }
        }

        # --- 1. Show main menu (Initial text response or 'menu' command) ---
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

        # --- 2. Handle Main Menu Selection (Check 1, 2, 3, 4, 5, 6) ---
        elif incoming_msg in main_menu:
            item = main_menu[incoming_msg]
            
            # Check for actions (Flows or List Messages)
            if "action" in item:
                action_type = item["action"]
                
                # --- LOGIC FOR OPTION 3: SEND LIST MESSAGE TEMPLATE ---
                if action_type == "send_nakopesheka_list":
                    
                    now_utc = datetime.now(timezone.utc)
                    
                    list_variables = {
                        "1": now_utc.strftime("%d %b, %Y"),
                        "2": now_utc.strftime("%I:%M %p UTC")
                    }
                    
                    send_list_message_template(
                        user_phone=from_number,
                        template_key="nakopesheka_list_menu",
                        variables=list_variables
                    )
                    logger.info(f"Sent Quick Reply Template for option 3 to {from_number}")
                    return PlainTextResponse("OK")
                
                else:
                    trigger_twilio_flow(
                        user_phone=from_number,
                        flow_type=action_type,
                        user_name=user_name,
                        user_id=user_id
                    )
                    logger.info(f"Triggered Flow '{action_type}' for {from_number}")
                    return PlainTextResponse("OK")

            # Other informative options (e.g., option 1, 2, 5, 6)
            reply_text = f"*{item.get('title')}*\n{item.get('description')}"
            send_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Fallback ---
        send_message(to=from_number_full, body="Samahani, sikuelewi. Jibu na neno 'menu' ili kuona huduma zetu.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)
