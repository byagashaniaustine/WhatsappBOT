import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message, send_meta_whatsapp_flow

logger = logging.getLogger("whatsapp_app")

# --- FLOW SCREEN ID CONSTANTS ---
# These MUST match the 'id' field of the first screen in your Flow definitions
NAKOPESHEKA_START_SCREEN = "LOAN_APPLICATION" 
# Assuming a start screen ID for the Loan Calculator Flow.
# YOU MUST VERIFY this ID fr        om the Flow 1623606141936116's JSON.
CALCULATOR_START_SCREEN = "CALCULATOR_INPUT" 

# --- MAIN MENU CONFIG ---
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
        "flow_id": "760682547026386",
        "flow_cta": "Anza Fomu ya Mkopo",
        "flow_body_text": "Jaza taarifa zako ili kuanza mchakato wa uchambuzi."
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": "Tumia kikokotoo kujua kiwango cha mkopo kinachokufaa kulingana na mapato yako.",
        "flow_id": "1623606141936116",
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


# --- LOAN CALCULATOR LOGIC ---
def calculate_max_loan(repayment_capacity: float, duration_months: int, annual_rate_percent: float) -> float:
    """Hesabu kiasi cha juu cha mkopo kulingana na uwezo wa kulipa, muda, na riba."""
    if annual_rate_percent == 0:
        return repayment_capacity * duration_months
    periodic_rate = (annual_rate_percent / 100) / 12
    try:
        numerator = 1 - math.pow(1 + periodic_rate, -duration_months)
        principal = repayment_capacity * (numerator / periodic_rate)
        return principal
    except Exception:
        return 0.0


async def process_loan_calculator_flow(from_number: str, form_data: dict):
    """
    Process the Loan Calculator Flow submission.
    Expects: form_data = { "kipato_mwezi": ..., "muda_miezi": ..., "riba_mwaka": ... }
    """
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
            f"Kiasi cha juu cha mkopo kinachokadiriwa ni:\n"
            f"💰 *Tsh {max_loan:,.0f}*"
        )

    except Exception as e:
        logger.error(f"❌ Error processing loan calculator: {e}")
        message = "❌ Samahani, kuna hitilafu katika kuchakata data. Tafadhali jaribu tena."

    send_meta_whatsapp_message(to=from_number, body=message)
    logger.info(f"📩 Loan Calculator result sent to {from_number}")
    return PlainTextResponse("OK")


# --- NAKOPESHEKA FLOW LOGIC ---
async def process_nakopesheka_flow(from_number: str, form_data: dict):
    """
    Process Nakopesheka Flow submission.
    Simply confirm user's name and request PDF/photo documents.
    """
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


# --- WHATSAPP MENU HANDLER ---
async def whatsapp_menu(data: dict):
    """
    Handle incoming WhatsApp messages and route to proper menu option.
    """
    try:
        from_number_full = str(data.get("From") or "")
        if from_number_full and not from_number_full.startswith("+"):
            from_number_full = "+" + from_number_full

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # --- MAIN MENU TRIGGERS ---
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

        # --- HANDLE MENU SELECTIONS ---
        if incoming_msg in main_menu:
            selection = incoming_msg
            item = main_menu[selection]

            # --- FLOW OPTIONS (Nakopesheka & Loan Calculator) ---
            if selection in ["3", "4"]:
                
                # *** START OF THE FIX ***
                
                # Determine the correct starting screen ID based on the selection
                if selection == "3":
                    # Nakopesheka flow uses the LOAN_APPLICATION screen
                    start_screen_id = NAKOPESHEKA_START_SCREEN
                elif selection == "4":
                    # Loan Calculator flow uses a specific input screen (e.g., CALCULATOR_INPUT)
                    start_screen_id = CALCULATOR_START_SCREEN
                else:
                    # Should be unreachable given the outer 'if' condition
                    return PlainTextResponse("Invalid flow selection logic.", status_code=400)
                
                flow_payload = {
                    "screen": start_screen_id, # <-- Using the actual flow screen ID
                    "data": {}  
                }
                # *** END OF THE FIX ***
                
                send_meta_whatsapp_flow(
                    to=from_number_full,
                    flow_id=item["flow_id"],
                    flow_cta=item["flow_cta"],
                    flow_body_text=item.get("flow_body_text", "Tuma taarifa zako."),
                    flow_header_text=item.get("title", "Huduma ya Mikopo"),
                    flow_footer_text="Taarifa yako ni siri.",
                    flow_action_payload=flow_payload
                )
                return PlainTextResponse("OK")

            # --- PLAIN MESSAGE OPTIONS (1,2,5,6) ---
            message = f"*{item['title']}*\n{item['description']}"
            send_meta_whatsapp_message(to=from_number_full, body=message)
            return PlainTextResponse("OK")

        # --- UNKNOWN COMMAND ---
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