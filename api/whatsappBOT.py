import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_flow


logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)


NAKOPESHEKA_START_SCREEN = "LOAN_APPLICATION"
CALCULATOR_START_SCREEN = "ELIGIBILITY_CHECK"


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
        "description": "Bonyeza kitufe kujaza taarifa zako ili tuangalie kama unastahili mkopo.",
        "flow_id": "760682547026386",  # Draft version ID
        "flow_cta": "Anza Fomu ya Mkopo",
        "flow_body_text": "Jaza taarifa zako ili kuanza mchakato wa uchambuzi."
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": "Tumia kikokotoo kujua kiwango cha mkopo kinachokufaa kulingana na mapato yako.",
        "flow_id": "1623606141936116",  # Draft version ID
        "flow_cta": "Angalia kiwango chako cha mkopo",
        "flow_body_text": "Jaza mapato yako, muda, na riba ili kupata matokeo."
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

# ---------------------------------
# LOAN CALCULATOR HELPER
# ---------------------------------
def calculate_max_loan(repayment_capacity: float, duration_months: int, annual_rate_percent: float) -> float:
    """Hesabu kiasi cha juu cha mkopo kulingana na uwezo wa kulipa, muda, na riba."""
    if annual_rate_percent == 0:
        return repayment_capacity * duration_months

    periodic_rate = (annual_rate_percent / 100) / 12
    try:
        numerator = 1 - math.pow(1 + periodic_rate, -duration_months)
        return repayment_capacity * (numerator / periodic_rate)
    except Exception:
        return 0.0

async def process_loan_calculator_flow(from_number: str, form_data: dict):
    """Process Loan Calculator Flow submission."""
    if not from_number.startswith("+"):
        from_number = "+" + from_number

    try:
        repayment_capacity = float(form_data.get("kipato_mwezi", 0))
        duration_months = int(form_data.get("muda_miezi", 0))
        annual_rate_percent = float(form_data.get("riba_mwaka", 0))

        max_loan = calculate_max_loan(repayment_capacity, duration_months, annual_rate_percent)

        message = (
            "✅ *Matokeo ya Kikokotoo cha Mkopo*\n\n"
            f"➡️ Uwezo wa kulipa (PMT): *Tsh {repayment_capacity:,.0f}*\n"
            f"➡️ Muda wa Mkopo: *{duration_months} miezi*\n"
            f"➡️ Riba ya mwaka: *{annual_rate_percent}%*\n\n"
            f"Kiasi cha juu cha mkopo kinachokadiriwa ni:\n💰 *Tsh {max_loan:,.0f}*"
        )

    except Exception as e:
        logger.error(f"❌ Error processing loan calculator flow: {e}")
        message = "❌ Samahani, kuna hitilafu katika kuchakata data. Tafadhali jaribu tena."

    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"📩 Loan Calculator results sent to {from_number}")
    return PlainTextResponse("OK")


async def process_nakopesheka_flow(from_number: str, form_data: dict):
    """Process Nakopesheka Flow submission."""
    if not from_number.startswith("+"):
        from_number = "+" + from_number

    full_name = form_data.get("full_name", "Mteja")

    message = (
        f"✅ Habari {full_name}!\n\n"
        "Tafadhali tuma PDF au picha za nyaraka zako (ID, salary slip, n.k.) "
        "ili tufanye uchambuzi na kuendelea na ombi lako la mkopo."
    )

    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"📩 Nakopesheka instructions sent to {from_number}")
    return PlainTextResponse("OK")


async def whatsapp_menu(data: dict):
    """Handle incoming WhatsApp messages and route to proper menu option or flow."""
    try:
        from_number_full = str(data.get("From") or "")
        if from_number_full and not from_number_full.startswith("+"):
            from_number_full = "+" + from_number_full

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # --- MAIN MENU TRIGGERS ---
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_list = "\n".join([f"*{key}* - {value['title']}" for key, value in main_menu.items()])
            reply = f"👋 *Karibu kwenye Huduma za Mikopo za Manka!*\n\nChagua huduma kwa kutuma namba:\n\n{menu_list}"
            send_meta_whatsapp_message(to=from_number_full, body=reply)
            return PlainTextResponse("OK")

        # --- USER SELECTION ---
        if incoming_msg in main_menu:
            item = main_menu[incoming_msg]

            # --- IF SELECTION HAS FLOW (3 or 4) ---
            if "flow_id" in item:
                start_screen_id = NAKOPESHEKA_START_SCREEN if incoming_msg == "3" else CALCULATOR_START_SCREEN
                flow_payload = {"screen": start_screen_id, "data": {}}

                send_meta_whatsapp_flow(
                    to=from_number_full,
                    flow_id=item["flow_id"],
                    flow_cta=item["flow_cta"],
                    flow_body_text=item.get("flow_body_text", "Tuma taarifa zako."),
                    flow_header_text=item.get("title", "Huduma ya Mikopo"),
                    flow_footer_text="Taarifa yako ni siri.",
                    flow_action_payload=flow_payload,
                    flow_mode="draft"  # Draft mode for testing
                )
                return PlainTextResponse("OK")

            # --- SIMPLE TEXT RESPONSE OPTIONS ---
            message = f"*{item['title']}*\n\n{item['description']}"
            send_meta_whatsapp_message(to=from_number_full, body=message)
            return PlainTextResponse("OK")

        # --- UNKNOWN INPUT ---
        send_meta_whatsapp_message(
            to=from_number_full,
            body="⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena."
        )
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(
            to=data.get("From"),
            body="❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'."
        )
        return PlainTextResponse("Internal Server Error", status_code=500)
