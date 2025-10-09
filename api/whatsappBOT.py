# whatsappBOT.py

import logging
# UPDATE: Include the new function in the import
from services.twilio import send_message, trigger_twilio_flow, send_list_message_template 
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        # Twilio sends 'whatsapp:+E164' in 'From'. We extract the number without the prefix.
        from_number_full = str(data.get("From") or "")
        from_number = from_number_full.replace("whatsapp:", "")
        
        if not from_number:
            logger.warning("No 'From' number provided")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # --- Main Menu Definitions ---
        main_menu = {
            "1": {"title": "Uhakiki wa Mikopo (Credit Scoring)", "description": "Jua alama yako ya mikopo na historia yako ya malipo kutoka kwa bodi ya mkopo."},
            "2": {"title": "Uwezo wa Mikopo (Credit Bandwidth)", "description": "Pata tathmini ya uwezo wako wa kifedha kulingana na historia ya mikopo na mapato."},
            "3": {"title": "Nakopesheka!!", "submenu": True}, # <-- This option will trigger the List Message
            "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "action": "open_flow_loan_calculator"},
            "5": {"title": "Aina za Mikopo", "description": "Pata maelezo kuhusu mikopo mbalimbali kama Mkopo wa Biashara, Kijamii, Haraka, na Mali."},
            "6": {"title": "Huduma za Nilipo", "description": "Huduma zinazotolewa sasa: upimaji wa mikopo, ushauri wa kifedha, huduma za marejeleo ya CRB."}
        }

        # --- Nakopesheka Submenu Definitions (Still needed for handling replies) ---
        nakopesheka_submenu = {
            "1": {"title": "Napataje Mkopo", "description": "Hapa kuna vidokezo na mwongozo wa jinsi ya kupata mkopo kwa urahisi na usalama."},
            "2": {"title": "Wasilisha Nyaraka", "action": "open_flow_upload_documents"}
        }
        
        user_id = str(data.get("user_id") or "")
        user_name = str(data.get("user_name") or "")


        # --- Show main menu (Initial text response or 'menu' command) ---
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
            # Use the full number for Twilio send_message utility
            send_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Handle Main Menu Selection ---
        elif incoming_msg in main_menu:
            item = main_menu[incoming_msg]

            # Handle "Nakopesheka" submenu (sends the new List Message)
            if item.get("submenu"):
                # Define variables for the List Message Template
                list_variables = {
                    "1": user_name or "mteja"  # Example variable for a greeting
                }
                
                # Send the List Message Template using the helper function
                send_list_message_template(
                    user_phone=from_number,
                    template_key="nakopesheka_list_menu", # Key for the List Template SID
                    variables=list_variables
                )
                logger.info(f"Sent Nakopesheka List Menu to {from_number}")
                return PlainTextResponse("OK")

            # Options with flow
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

            # Other options → send title + description
            reply_text = f"*{item.get('title')}*\n{item.get('description')}"
            send_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Handle Nakopesheka Submenu Selection ---
        # NOTE: If you use the List Message template, the incoming_msg might be the 
        # Item ID from the template (e.g., 'get_loan', 'submit_docs') instead of '1' or '2'. 
        # You will need to update this logic if you use descriptive IDs in your template.
        elif incoming_msg in ["1", "2"]:
            if incoming_msg == "1":
                # Napataje Mkopo content
                reply_text = (
                    "💡 Vidokezo vya kupata mkopo:\n"
                    "- Hakikisha una historia nzuri ya malipo.\n"
                    "- Pata ushauri kutoka kwa mashirika yanayohakikishwa.\n"
                    "- Weka mpango wa malipo unaoweza kushughulika.\n"
                    "- Epuka madeni yasiyo rasmi."
                )
                send_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")
                
            elif incoming_msg == "2":
                # Wasilisha Nyaraka → trigger Flow
                flow_action = "open_flow_upload_documents"
                trigger_twilio_flow(
                    user_phone=from_number,
                    flow_type=flow_action,
                    user_name=user_name,
                    user_id=user_id
                )
                logger.info(f"Triggered Flow '{flow_action}' for {from_number}")
                return PlainTextResponse("OK")

        # --- Fallback ---
        send_message(to=from_number_full, body="Jibu na neno 'menu' ili kuona huduma zetu")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)