
from fastapi.responses import PlainTextResponse
from services.twilio import send_message
import logging

logger = logging.getLogger("myapp")

async def whatsapp_menu(data: dict):
    """
    Handle incoming WhatsApp text messages and return credit/loan tips menu.
    
    :param data: Dictionary from Twilio webhook with keys like 'From' and 'Body'
    :return: FastAPI PlainTextResponse
    """
    try:
        from_number = data.get("From", "")
        incoming_msg = data.get("Body", "").strip().lower()

        logger.info(f"📩 Incoming WhatsApp message from {from_number}: {incoming_msg}")

        # Menu options dictionary
        menu = {
            "1": (
                "*Improving Credit Score Tips:*\n"
                "- Pay bills on time ✅\n"
                "- Keep credit usage below 30%\n"
                "- Limit applying for too many loans\n"
                "- Check your credit report regularly"
            ),
            "2": (
                "*Qualify for a Loan:*\n"
                "- Maintain a stable income source\n"
                "- Build a good repayment history\n"
                "- Reduce existing debt before applying\n"
                "- Prepare all required documents early"
            ),
            "3": (
                "*Smart Debt Repayment:*\n"
                "- Pay more than the minimum if possible\n"
                "- Focus on high-interest debt first (avalanche method)\n"
                "- Avoid unnecessary new loans\n"
                "- Create a realistic repayment plan"
            ),
            "4": (
                "*Common Mistakes to Avoid:*\n"
                "- Missing payment deadlines\n"
                "- Using all available credit\n"
                "- Taking too many short-term loans\n"
                "- Ignoring your credit report"
            ),
            "5": "Our financial coach will reach out to you soon!"
        }

        # Default reply if user requests menu
        if incoming_msg in ["hi", "hello", "start", "menu", ""]:
            reply_text = (
                " *Welcome to Credit/Loan Tips Bot!*\n"
                " Choose a topic to learn about:\n\n"
                "1️⃣ How to improve your credit score\n"
                "2️⃣ How to qualify for a loan\n"
                "3️⃣ Smart ways to repay debt\n"
                "4️⃣ Avoiding common credit mistakes\n"
                "5️⃣ Talk to a financial coach"
            )
        elif incoming_msg in menu:
            reply_text = menu[incoming_msg]
        else:
            reply_text = "I didn't get that. Please reply with *menu* to see the topics again."

        # Send response via Twilio
        send_message(to=from_number, body=reply_text)
        logger.info(f"Sent menu response to {from_number}")

        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception("Error in whatsapp_menu:")
        return PlainTextResponse("Internal Server Error", status_code=500)
