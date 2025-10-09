# whatsappBOT.py

import logging
# Ensure you import the new function
from services.twilio import send_message, trigger_twilio_flow, send_list_message_template 
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        from_number = from_number_full.replace("whatsapp:", "")
        
        if not from_number:
            logger.warning("No 'From' number provided")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip().lower()

        user_id = str(data.get("user_id") or "")
        user_name = str(data.get("user_name") or "")

        # --- Main Menu Definitions ---
        main_menu = {
            "1": {"title": "Uhakiki wa Mikopo (Credit Scoring)", "description": "Jua alama yako ya mikopo..."},
            "2": {"title": "Uwezo wa Mikopo (Credit Bandwidth)", "description": "Pata tathmini ya uwezo..."},
            "3": {"title": "Nakopesheka!!", "submenu": True}, 
            "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "action": "open_flow_loan_calculator"},
            "5": {"title": "Aina za Mikopo", "description": "Pata maelezo kuhusu..."},
            "6": {"title": "Huduma za Nilipo", "description": "Huduma zinazotolewa sasa..."}
        }

        # --- 1. Show main menu (hi, hello, start, menu) ---
        if incoming_msg in ["hi", "hello", "start", "menu", ""]:
            reply_text = (
                " *Karibu katika huduma ya mikopo ya Manka*\n"
                " Chagua huduma ungependa uhudumiwe:\n\n"
                "1️⃣ Uhakiki Mikopo\n"
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

            # Trigger the text Nakopesheka Submenu (when user sends "3")
            if item.get("submenu"): 
                # **REVERTED TO TEXT SUBMENU AS REQUESTED**
                reply_text = (
                    "📌 Nakopesheka Submenu:\n"
                    "1️⃣ Napataje Mkopo\n"
                    "2️⃣ Wasilisha Nyaraka\n"
                    "Tafadhali chagua 1 au 2."
                )
                send_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")

            # Options with flow (e.g., option 4)
            if "action" in item:
                flow_action = item["action"]
                trigger_twilio_flow(
                    user_phone=from_number,
                    flow_type=flow_action,
                    user_name=user_name,
                    user_id=user_id
                )
                logger.info(f"Triggered Flow '{flow_action}' for {from_number}")
                return PlainTextResponse("OK")

            # Other informative options (e.g., option 1, 2, 5, 6)
            reply_text = f"*{item.get('title')}*\n{item.get('description')}"
            send_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- 3. Handle Nakopesheka Submenu Selection (1 or 2) ---
        # This block executes only if the user is replying to the text submenu.
        elif incoming_msg in ["1", "2"]:
            
            # Action 1: Napataje Mkopo (Text Reply)
            if incoming_msg == "1":
                reply_text = (
                    "💡 Vidokezo vya kupata mkopo:\n"
                    "- Hakikisha una historia nzuri ya malipo.\n"
                    "- Pata ushauri kutoka kwa mashirika yanayohakikishwa.\n"
                    "- Weka mpango wa malipo unaoweza kushughulika.\n"
                    "- Epuka madeni yasiyo rasmi."
                )
                send_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")
                
            # Action 2: Wasilisha Nyaraka (SEND THE LIST MESSAGE TEMPLATE)
            elif incoming_msg == "2":
                
                list_variables = {"1": user_name or "mteja"}
                
                # **THIS IS THE NEW LOGIC:** Call the List Message function
                send_list_message_template(
                    user_phone=from_number,
                    template_key="nakopesheka_list_menu", # The List Template SID defined in services/twilio.py
                    variables=list_variables
                )
                logger.info(f"Sent Nakopesheka List Menu (Submenu option 2) to {from_number}")
                
                return PlainTextResponse("OK")

        # --- Fallback ---
        send_message(to=from_number_full, body="Samahani, sikuelewi. Jibu na neno 'menu' ili kuona huduma zetu.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)