import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_flow, generate_flow_token

logger = logging.getLogger("whatsapp_app")

# ------------------ Flow Senders ------------------

def send_whatsapp_flow_calc(to_number: str):
    """Send Kikokotoo cha Mkopo Flow"""
    logger.info(f"📊 Sending Loan Calculator FLOW to {to_number}")
    flow_token = generate_flow_token(flow_id="1623606141936116", to=to_number)
    return send_meta_whatsapp_flow(
        to=to_number,
        flow_id="1623606141936116",
        flow_token=flow_token,
        flow_cta="Angalia kiwango chako cha mkopo",
        screen="ELIGIBILITY_CHECK"
    )

def send_whatsapp_flow_nakopesheka(to_number: str):
    """Send Nakopesheka Flow"""
    logger.info(f"🚀 Sending Nakopesheka FLOW to {to_number}")
    flow_token = generate_flow_token(flow_id="760682547026386", to=to_number)
    return send_meta_whatsapp_flow(
        to=to_number,
        flow_id="760682547026386",
        flow_token=flow_token,
        flow_cta="Anza Fomu ya Mkopo",
        screen="LOAN_APPLICATION"
    )

# ------------------ Loan Calculator ------------------

def calculate_max_loan_principal(repayment_capacity: float, duration_months: int, annual_rate_percent: float) -> float:
    """Calculate max loan based on repayment, duration, and interest."""
    if annual_rate_percent == 0:
        return repayment_capacity * duration_months
    periodic_rate = (annual_rate_percent / 100) / 12
    try:
        numerator = 1 - math.pow(1 + periodic_rate, -duration_months)
        principal = repayment_capacity * (numerator / periodic_rate)
        return principal
    except Exception:
        return 0.0

async def process_loan_calculator(from_number: str, form_data: dict):
    """Process Loan Calculator submission"""
    if not from_number.startswith("+"):
        from_number = "+" + from_number
    try:
        repayment_capacity = float(form_data.get("kipato_mwezi", 0))
        duration_months = int(form_data.get("muda_miezi", 0))
        annual_rate_percent = float(form_data.get("riba_mwaka", 0))

        max_loan = calculate_max_loan_principal(repayment_capacity, duration_months, annual_rate_percent)

        message = (
            "✅ *Matokeo ya Kikokotoo cha Mkopo*\n\n"
            f"➡️ Uwezo wa kulipa (PMT): *Tsh {repayment_capacity:,.0f}*\n"
            f"➡️ Muda wa Mkopo: *{duration_months} miezi*\n"
            f"➡️ Riba ya mwaka: *{annual_rate_percent}%*\n\n"
            f"Kiasi cha juu cha mkopo kinachokadiriwa ni:\n"
            f"💰 *Tsh {max_loan:,.0f}*"
        )
    except Exception as e:
        logger.error(f"❌ Error processing loan calculator: {e}")
        message = "❌ Samahani, kuna hitilafu katika kuchakata data. Tafadhali jaribu tena."

    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"📩 Loan result sent to {from_number}")
    return PlainTextResponse("OK")

# ------------------ Nakopesheka ------------------

async def process_nakopesheka_flow(from_number: str, form_data: dict):
    """Process Nakopesheka submission"""
    if not from_number.startswith("+"):
        from_number = "+" + from_number

    full_name = form_data.get("full_name", "Mteja")
    message = (
        f"✅ Habari {full_name}!\n\n"
        "Tafadhali tuma PDF au picha za nyaraka zako (ID, salary slip, n.k.) "
        "ili tufanye uchambuzi na kuendelea na ombi lako la mkopo."
    )

    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"📩 Nakopesheka instruction sent to {from_number}")
    return PlainTextResponse("OK")

# ------------------ Main Menu ------------------

main_menu = {
    "1": {"title": "Alama ya Mikopo (Credit Scoring)", "description": "Alama ya Mikopo inaonyesha uaminifu wako wa kifedha. Alama nzuri hukusaidia kupata mikopo kwa urahisi zaidi."},
    "2": {"title": "Upana wa Mikopo (Credit Bandwidth)", "description": "Inaonyesha kiwango cha juu cha mkopo unachoweza kukopa kulingana na kipato chako."},
    "3": {"title": "Nakopesheka!! (Fomu ya Uhalali)", "description": "Bonyeza kitufe kujaza taarifa zako ili tuangalie kama unastahili mkopo."},
    "4": {"title": "Kikokotoo cha Mkopo (Loan Calculator)", "description": "Tumia kikokotoo kujua kiwango cha mkopo kinachokufaa kulingana na mapato yako."},
    "5": {"title": "Aina za Mikopo", "description": "Kuna mikopo ya biashara, elimu, nyumba, na mikopo ya dharura."},
    "6": {"title": "Huduma za Nilipo (Where I Am)", "description": "Huduma za karibu nawe: mikopo midogo, malipo, na mikopo ya haraka."}
}

# ------------------ WhatsApp Menu Handler ------------------

async def whatsapp_menu(data: dict):
    """Main menu and WhatsApp command handler."""
    try:
        from_number = str(data.get("From") or "")
        if from_number and not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # 👋 Welcome / Main Menu
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            reply = "👋 *Karibu kwenye Huduma za Mikopo za Manka!*\n\nChagua huduma kwa kutuma namba:\n"
            for k, v in main_menu.items():
                reply += f"{k}. {v['title']}\n"
            send_meta_whatsapp_message(to=from_number, body=reply)
            return PlainTextResponse("OK")

        # 🔢 Menu Selections
        if incoming_msg in main_menu:
            selection = incoming_msg
            if selection == "3":
                return send_whatsapp_flow_nakopesheka(from_number)
            elif selection == "4":
                return send_whatsapp_flow_calc(from_number)
            else:
                item = main_menu[selection]
                message = f"*{item['title']}*\n{item['description']}"
                send_meta_whatsapp_message(to=from_number, body=message)
                return PlainTextResponse("OK")

        # ⚠️ Unknown Command
        send_meta_whatsapp_message(
            to=from_number,
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
