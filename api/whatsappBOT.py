# whatsappBOT.py

import logging
from services.twilio import send_message, trigger_twilio_flow, send_list_message_template 
from fastapi.responses import PlainTextResponse
from datetime import datetime, timezone

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
            # OPTION 3 now goes directly to the Content Template
            "3": {"title": "Nakopesheka!!", "action": "send_nakopesheka_list"}, 
            "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "action": "open_flow_loan_calculator"},
            "5": {"title": "Aina za Mikopo", "description": "Pata maelezo kuhusu..."},
            "6": {"title": "Huduma za Nilipo", "description": "Huduma zinazotolewa sasa..."}
        }
        
        # --- 1. Show main menu (Initial text response or 'menu' command) ---
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
            
            # Check for actions (Flows or List Messages)
            if "action" in item:
                action_type = item["action"]
                
                # --- LOGIC FOR OPTION 3: SEND LIST MESSAGE TEMPLATE ---
                if action_type == "send_nakopesheka_list":
                    
                    # Create dynamic date/time for the template variables
                    now_utc = datetime.now(timezone.utc)
                    
                    # The template requires {{date}} and {{time}}
                    list_variables = {
                        "date": now_utc.strftime("%d %b, %Y"), # e.g., 09 Oct, 2025
                        "time": now_utc.strftime("%I:%M %p UTC")  # e.g., 01:51 PM UTC
                    }
                    
                    send_list_message_template(
                        user_phone=from_number,
                        template_key="nakopesheka_list_menu",
                        variables=list_variables
                    )
                    logger.info(f"Sent Quick Reply Template for option 3 to {from_number}")
                    return PlainTextResponse("OK")
                
                # --- Existing Logic for Flow Actions (e.g., Option 4) ---
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