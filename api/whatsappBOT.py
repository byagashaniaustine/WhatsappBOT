# whatsappBOT.py
import logging
from services.twilio import send_message, trigger_twilio_flow
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number:
            logger.warning("No 'From' number provided")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip().lower()

        menu = {
            "1": {"title": "Historia ya Mikopo (Credit Scoring)", "description": "Jua alama yako ya mikopo na historia yako ya malipo kutoka CRB."},
            "2": {"title": "Uwezo wa Mikopo (Credit Bandwidth)", "description": "Pata tathmini ya uwezo wako wa kifedha kulingana na historia ya mikopo na mapato."},
            "3": {"title": "Wasilisha Nyaraka kwa Uhakiki", "action": "open_flow_upload_documents"},
            "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "action": "open_flow_loan_calculator"},
            "5": {"title": "Aina za Mikopo", "description": "Pata maelezo kuhusu mikopo mbalimbali kama Mkopo wa Biashara, Kijamii, Haraka, na Mali."},
            "6": {"title": "Huduma za Nilipo", "description": "Huduma zinazotolewa sasa: upimaji wa mikopo, ushauri wa kifedha, huduma za marejeleo ya CRB."}
        }

        # Show main menu
        if incoming_msg in ["hi", "hello", "start", "menu", ""]:
            reply_text = (
                " *Karibu katika huduma ya mikopo ya Manka*\n"
                " Chagua huduma ungependa uhudumiwe:\n\n"
                "1️⃣ Uhakiki Mikopo\n"
                "2️⃣ Kiwango cha Mkopo\n"
                "3️⃣ Wasilisha Nyaraka\n"
                "4️⃣ Kikokotoo cha Mkopo\n"
                "5️⃣ Aina za Mikopo\n"
                "6️⃣ Huduma za Mikopo"
            )
            send_message(to=from_number, body=reply_text)
            return PlainTextResponse("OK")

        # Handle menu selection
        elif incoming_msg in menu:
            item = menu[incoming_msg]

            # Options with flow
            if "action" in item:
                flow_action = item["action"]
                user_id = str(data.get("user_id") or "")
                user_name = str(data.get("user_name") or "")

                trigger_twilio_flow(
                    user_phone=from_number,
                    flow_type=flow_action,
                    user_name=user_name,
                    user_id=user_id
                )
                logger.info(f"Triggered Flow '{flow_action}' for {from_number}")
                return PlainTextResponse("OK")

            # Other options → send title + description
            reply_text = f"{item.get('title')}\n{item.get('description')}"
            send_message(to=from_number, body=reply_text)
            return PlainTextResponse("OK")

        # Fallback
        send_message(to=from_number, body="Jibu na neno 'menu' ili kuona huduma zetu")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {str(e)}")
        return PlainTextResponse("Internal Server Error", status_code=500)


def process_flow_input(user_text: str, flow_type: str) -> str:
    try:
        user_text_str = str(user_text)

        if flow_type == "loan_calculator":
            try:
                params = dict(pair.split("=") for pair in user_text_str.split("&"))
                payment = float(params.get("payment", 0))
                duration = int(params.get("duration", 0))
                interest_rate = float(params.get("interest_rate", 0)) / 100
            except Exception:
                return "⚠️ Tuma data kwa format sahihi: payment=VALUE&duration=VALUE&interest_rate=VALUE"

            if payment <= 0 or duration <= 0 or interest_rate < 0:
                return "⚠️ Thamani zisizo sahihi kwa malipo, muda, au riba."

            loan_amount = payment * duration if interest_rate == 0 else payment * (1 - (1 + interest_rate) ** (-duration)) / interest_rate
            loan_amount = round(loan_amount, 2)

            return (
                f"📊 Matokeo ya kikokotoo chako:\n"
                f"Malipo kila mwezi: {payment}\n"
                f"Muda (miezi): {duration}\n"
                f"Kiwango cha riba: {interest_rate*100}%\n"
                f"Kiasi cha mkopo unachoweza kumudu: {loan_amount}"
            )

        return "✅ Taarifa yako imepokelewa kikamilifu."

    except Exception as e:
        return f"⚠️ Tatizo limetokea: {str(e)}"
