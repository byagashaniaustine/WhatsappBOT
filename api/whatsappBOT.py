import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_flow

logger = logging.getLogger("whatsapp_app")

def calculate_max_loan_principal(repayment_capacity: float, duration_months: int, annual_rate_percent: float) -> float:
    """
    Calculates the maximum loan amount based on repayment ability, duration, and interest rate.
    """
    if annual_rate_percent == 0:
        return repayment_capacity * duration_months

    monthly_rate = (annual_rate_percent / 100) / 12
    try:
        numerator = 1 - math.pow(1 + monthly_rate, -duration_months)
        principal = repayment_capacity * (numerator / monthly_rate)
        return round(principal, 2)
    except Exception as e:
        logger.error(f"Error in loan calculation: {e}")
        return 0.0


def send_whatsapp_flow_nakopesheka(to_number: str):
    """
    Sends the 'Nakopesheka' Flow (Eligibility Form) to the user.
    """
    logger.info(f"🚀 Sending Nakopesheka Flow to {to_number}")
    return send_meta_whatsapp_flow(
        to=to_number,
        flow_id="760682547026386",  # 👈 Flow ID from Meta (Nakopesheka)
        screen="ELIGIBILITY_SCREEN",
        cta_text="ANZA NAKOPESHEKA"
    )


def send_whatsapp_flow_calc(to_number: str):
    """
    Sends the 'Loan Calculator' Flow to the user.
    """
    logger.info(f"📊 Sending Loan Calculator Flow to {to_number}")
    return send_meta_whatsapp_flow(
        to=to_number,
        flow_id="1623606141936116",  # 👈 Flow ID from Meta (Kikokotoo)
        screen="LOAN_CALCULATOR",
        cta_text="JAZA KIKOKOTOI"
    )
# =====================================================
async def process_loan_calculator(from_number: str, form_data: dict):
    """
    Handles submission from the 'Loan Calculator' Flow.
    Performs loan computation and sends back estimated loan amount.
    """
    try:
        # Extract values from form data
        repayment_capacity = float(form_data.get("RepaymentAmount", 200000))
        duration_months = int(form_data.get("DurationMonths", 12))
        annual_rate_percent = float(form_data.get("AnnualRate", 18))

        # Compute max loan
        max_loan_amount = calculate_max_loan_principal(
            repayment_capacity, duration_months, annual_rate_percent
        )

        # Prepare result message
        message = (
            "📊 *Matokeo ya Kikokotoo cha Mkopo*\n\n"
            f"➡️ Uwezo wa kulipa (kila mwezi): *Tsh {repayment_capacity:,.0f}*\n"
            f"➡️ Muda wa Mkopo: *{duration_months} miezi*\n"
            f"➡️ Riba ya mwaka: *{annual_rate_percent}%*\n\n"
            f"💰 *Kiasi cha juu cha mkopo kinachokadiriwa:* Tsh {max_loan_amount:,.0f}"
        )

    except Exception as e:
        logger.error(f"❌ Error processing loan calculator flow: {e}")
        message = "⚠️ Samahani, hitilafu imetokea wakati wa kuchakata kikokotoo."

    # Send result to user
    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"✅ Loan Calculator result sent to {from_number}")
    return PlainTextResponse("OK")


async def process_nakopesheka_flow(from_number: str, form_data: dict):
    try:
        # Extract user's name (or fallback to number)
        user_name = form_data.get("FullName") or from_number

        # Respond asking for documents
        response_text = (
            f"✅ Asante, {user_name}! \n"
            "Tafadhali tuma PDF au picha zinazohusiana na taarifa zako za kifedha "
            "ili tuchambue Manka API. Utapokea majibu baada ya uchambuzi."
        )

    except Exception as e:
        logger.error(f"❌ Error in Nakopesheka flow prep: {e}")
        response_text = (
            "⚠️ Samahani, hitilafu imetokea wakati wa kuchakata taarifa zako. "
            "Tafadhali jaribu tena."
        )

    # Send prompt to user
    send_meta_whatsapp_message(to=from_number, body=response_text)
    logger.info(f"📩 Nakopesheka prompt sent to {from_number}")
    return PlainTextResponse("OK")

main_menu = {
    "1": {
        "title": "Alama ya Mikopo (Credit Scoring)",
        "description": (
            "Alama ya Mikopo inaonyesha uaminifu wako wa kifedha. "
            "Alama nzuri hukusaidia kupata mikopo kwa urahisi zaidi."
        )
    },
    "2": {
        "title": "Upana wa Mikopo (Credit Bandwidth)",
        "description": "Inaonyesha kiwango cha juu cha mkopo unachoweza kukopa kulingana na kipato chako."
    },
    "3": {
        "title": "Nakopesheka!! (Fomu ya Uhalali)",
        "description": "Bonyeza kitufe kujaza taarifa zako ili tuangalie kama unastahili mkopo."
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": "Tumia kikokotoo kujua kiwango cha mkopo kinachokufaa kulingana na mapato yako."
    },
    "5": {
        "title": "Aina za Mikopo",
        "description": "Kuna mikopo ya biashara, elimu, nyumba, na mikopo ya dharura."
    },
    "6": {
        "title": "Huduma za Nilipo (Where I Am)",
        "description": "Huduma za karibu nawe: mikopo midogo, malipo, na mikopo ya haraka."
    }
}


async def whatsapp_menu(data: dict):
    """
    Main menu and text-based WhatsApp command handler.
    """
    try:
        from_number_full = str(data.get("From") or "")
        if from_number_full and not from_number_full.startswith("+"):
            from_number_full = "+" + from_number_full

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # 👋 Main Menu
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            reply = (
                "👋 *Karibu kwenye Huduma za Mikopo za Manka!*\n\n"
                "Chagua huduma kwa kutuma namba:\n\n"
                "1️⃣ Alama ya Mikopo\n"
                "2️⃣ Upana wa Mikopo\n"
                "3️⃣ Nakopesheka!! (Fomu)\n"
                "4️⃣ Kikokotoo cha Mkopo\n"
                "5️⃣ Aina za Mikopo\n"
                "6️⃣ Huduma Nilipo"
            )
            send_meta_whatsapp_message(to=from_number_full, body=reply)
            return PlainTextResponse("OK")

        # 🔢 Menu Selections
        if incoming_msg in main_menu:
            selection = incoming_msg

            if selection == "3":
                return send_whatsapp_flow_nakopesheka(from_number_full)

            elif selection == "4":
                return send_whatsapp_flow_calc(from_number_full)

            else:
                item = main_menu[selection]
                message = f"*{item['title']}*\n{item['description']}"
                send_meta_whatsapp_message(to=from_number_full, body=message)
                return PlainTextResponse("OK")

        # ⚠️ Unknown Command
        send_meta_whatsapp_message(
            to=from_number_full,
            body="⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena."
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            to=data.get("From"),
            body="❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return PlainTextResponse("Internal Error", status_code=500)
