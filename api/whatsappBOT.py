from fastapi.responses import PlainTextResponse
from services.twilio import send_message, trigger_twilio_flow
import logging

logger = logging.getLogger("myapp")


async def whatsapp_menu(data: dict):
    try:
        from_number = data.get("From", "")
        incoming_msg = data.get("Body", "").strip().lower()

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
                "description": "Tuma hati zako (mfano: kitambulisho, slip ya mshahara) kupitia Twilio Flow ili zipitiwe na mfumo wetu kwa uhakiki.",
                "action": "open_flow_upload_documents"
            },
            "4": {
                "title": "Kikokotoo cha Mkopo (Loan Calculator)",
                "description": "Weka kiasi unachotaka kukopa, muda wa kulipa, na kiwango cha riba. Mfumo utahesabu jumla ya marejesho yako na malipo ya kila mwezi.",
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

        # Default reply if user requests menu
        if incoming_msg in ["hi", "hello", "start", "menu", ""]:
            reply_text = (
                " *Karibu katika huduma ya mikopo ya Manka*\n"
                " Chagua huduma ungependa uhudumiwe:\n\n"
                "1️⃣ Uhakiki Mikopo\n"
                "2️⃣ Kiwango cha Mkopo\n"
                "3️⃣ Nakopesheka!!\n"
                "4️⃣ Kikokotoo cha Mkopo\n"
                "5️⃣ Aina za Mikopo\n"
                "6️⃣ Huduma za Mikopo"
            )
        elif incoming_msg in menu:
            item = menu[incoming_msg]
            reply_text = f"{item.get('title')}\n{item.get('description')}"

            # If the menu option has an action, trigger the Twilio Flow
            if "action" in item:
                flow_action = item["action"]
                trigger_twilio_flow(user_number=from_number, action=flow_action)
                logger.info(f"Triggered Twilio Flow '{flow_action}' for {from_number}")

        else:
            reply_text = "Jibu na neno 'menu' ili kuona huduma zetu"

        # Send response via Twilio
        send_message(to=from_number, body=reply_text)
        logger.info(f"Sent menu response to {from_number}")

        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception("Error in whatsapp_menu:")
        return PlainTextResponse("Internal Server Error", status_code=500)


def process_flow_input(user_text: str, flow_type: str) -> str:
    """
    Handles structured Twilio Flow inputs, including reverse loan calculator.
    """
    try:
        if flow_type == "loan_calculator":
            # Expect user_text like: "payment=50000&duration=12&interest_rate=2"
            params = dict(pair.split("=") for pair in user_text.split("&"))
            payment = float(params.get("payment", 0))
            duration = int(params.get("duration", 0))
            interest_rate = float(params.get("interest_rate", 0)) / 100  # convert % to decimal

            # Validate inputs
            if payment <= 0 or duration <= 0 or interest_rate < 0:
                return "⚠️ Tafadhali weka thamani sahihi kwa malipo, muda na riba."

            # Reverse loan calculation (annuity formula)
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

        # Add handling for other Flow types here if needed
        return "✅ Taarifa yako imepokelewa kikamilifu."

    except Exception as e:
        logger.exception("Error in process_flow_input:")
        return f"⚠️ Tatizo limetokea: {str(e)}"
