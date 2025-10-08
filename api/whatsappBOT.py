from fastapi.responses import PlainTextResponse
from services.twilio import send_message, trigger_twilio_flow
import logging

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        # Ensure From and Body are strings
        from_number = str(data.get("From", ""))
        incoming_msg = str(data.get("Body", "")).strip().lower()

        logger.info(f"📩 Incoming WhatsApp message from {from_number}: {incoming_msg}")

        # Menu options dictionary
        menu = {
            "1": {
                "title": "Historia ya Mikopo (Credit Scoring)",
                "description": "Jua alama yako ya mikopo na historia yako ya malipo kutoka CRB. Hii hukusaidia kuelewa nafasi yako ya kupata mikopo mipya."
            },
            "2": {
                "title": "Uwezo wa Mikopo (Credit Bandwidth)",
                "description": "Pata tathmini ya uwezo wako wa kifedha. Hapa utaona kiwango cha juu cha mkopo unaoweza kupata kulingana na historia yako ya mikopo na mapato yako."
            },
            "3": {
                "title": "Wasilisha Nyaraka kwa Uhakiki",
                "action": "open_flow_upload_documents"
            },
            "4": {
                "title": "Kikokotoo cha Mkopo (Loan Calculator)",
                "action": "open_flow_loan_calculator"
            },
            "5": {
                "title": "Aina za Mikopo",
                "description": "Pata maelezo kuhusu mikopo mbalimbali kama Mkopo wa Biashara, Mkopo wa Kijamii, Mkopo wa Haraka, na Mkopo wa Mali."
            },
            "6": {
                "title": "Huduma za Nilipo",
                "description": "Huduma zinazotolewa kwa sasa: upimaji wa mikopo, ushauri wa kifedha, na huduma za marejeleo ya CRB. Tafuta huduma inayokufaa zaidi."
            }
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
            logger.info(f"Sent menu response to {from_number}")
            return PlainTextResponse("OK")

        # Handle menu options
        elif incoming_msg in menu:
            item = menu[incoming_msg]

            # Options 3 & 4 → trigger Twilio Flow only
            if "action" in item:
                flow_action = item["action"]

                # Build dynamic parameters from user input / webhook
                if flow_action == "open_flow_upload_documents":
                    parameters = {
                        "user_id": data.get("user_id"),
                        "user_name": data.get("user_name"),
                        "user_phone": from_number,
                        "flow_type": "upload_documents"
                    }
                elif flow_action == "open_flow_loan_calculator":
                    parameters = {
                        "payment": data.get("payment"),
                        "duration": data.get("duration"),
                        "interest_rate": data.get("interest_rate")
                    }
                else:
                    parameters = {}

                trigger_twilio_flow(user_number=from_number, action=flow_action, parameters=parameters)
                logger.info(f"Triggered Twilio Flow '{flow_action}' for {from_number}")
                return PlainTextResponse("OK")

            # Other options → send title + description
            reply_text = f"{item.get('title')}\n{item.get('description')}"
            send_message(to=from_number, body=reply_text)
            logger.info(f"Sent menu response to {from_number}")
            return PlainTextResponse("OK")

        # Default fallback
        else:
            reply_text = "Jibu na neno 'menu' ili kuona huduma zetu"
            send_message(to=from_number, body=reply_text)
            return PlainTextResponse("OK")

    except Exception as e:
        logger.exception("Error in whatsapp_menu:")
        return PlainTextResponse("Internal Server Error", status_code=500)


def process_flow_input(user_text: str, flow_type: str) -> str:
    """
    Handles structured Twilio Flow inputs, including reverse loan calculator.
    """
    try:
        user_text_str = str(user_text)

        if flow_type == "loan_calculator":
            # Expect user_text like: "payment=50000&duration=12&interest_rate=2"
            try:
                params = dict(pair.split("=") for pair in user_text_str.split("&"))
                payment = float(params.get("payment", 0))
                duration = int(params.get("duration", 0))
                interest_rate = float(params.get("interest_rate", 0)) / 100
            except Exception:
                return "⚠️ Tafadhali tuma data kwa format sahihi: payment=VALUE&duration=VALUE&interest_rate=VALUE"

            if payment <= 0 or duration <= 0 or interest_rate < 0:
                return "⚠️ Tafadhali weka thamani sahihi kwa malipo, muda na riba."

            if interest_rate == 0:
                loan_amount = payment * duration
            else:
                loan_amount = payment * (1 - (1 + interest_rate) ** (-duration)) / interest_rate

            loan_amount = round(loan_amount, 2)

            return (
                f"📊 Matokeo ya kikokotoo chako cha mkopo:\n"
                f"Malipo unayoweza kufanya kila mwezi: {payment}\n"
                f"Muda wa malipo (miezi): {duration}\n"
                f"Kiwango cha riba: {interest_rate*100}%\n"
                f"Kiasi cha mkopo unachoweza kumudu: {loan_amount}"
            )

        return "✅ Taarifa yako imepokelewa kikamilifu."

    except Exception as e:
        return f"⚠️ Tatizo limetokea: {str(e)}"
