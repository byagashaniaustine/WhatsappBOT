import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# -------------------------
# UPDATED MAIN MENU (NO FLOWS)
# -------------------------
main_menu = {
    "1": {
        "title": "Fahamu kuhusu Alama za Mikopo (Credit Score)",
        "description": "Alama ya mikopo ni kipimo kinachoonyesha jinsi unavyoaminika kifedha..."
    },
    "2": {
        "title": "Kiwango cha Mkopo (Credit Bandwidth)",
        "description": "Kiwango cha mkopo ni kiasi cha juu cha fedha ambacho taasisi ya kifedha inaweza kukukopesha..."
    },
    "3": {
        "title": "Nakopesheka!! (Uwezo wa Kukopa)",
        "description": (
            "💳 *Uwezo wa Kukopa (Affordability)*\n\n"
            "Affordability ni kipimo kinachoonyesha uwezo wako wa kulipa mkopo bila "
            "kuumiza bajeti yako ya kila siku. Tunapima kipato chako, matumizi yako, "
            "historia ya ulipaji na uaminifu wa kifedha.\n\n"

            "📊 *Manka Affordability Score* inaonyesha kiwango cha mkopo unachoweza kuchukua:\n"
            "• 🔼 *Score ya Juu* — Inaonyesha uwezo mkubwa. Hapa unaweza kukopeshwa kiasi kikubwa.\n"
            "• 🟡 *Score ya Kati (Moderate)* — Una uwezo wa wastani. Hapa unaweza kuchukua mkopo wa kawaida, sio mdogo sana wala sio mkubwa sana.\n"
            "• 🔽 *Score ya Chini* — Hiki ndicho kiwango cha chini cha mkopo ambacho ni salama kuanzia.\n\n"

            "➡️ Kwa lugha nyepesi:\n"
            "• Score ya juu = unaweza kubeba mzigo mkubwa wa mkopo bila kuteseka.\n"
            "• Score ya kati = unaweza kubeba mkopo wa kiwango cha kati bila shida.\n"
            "• Score ya chini = ni salama kuanza na mkopo mdogo ili usipate presha ya malipo.\n\n"

            "⚠️ *Ushauri:* Tunashauri uanze na kiwango cha chini ili ujenge historia nzuri ya ulipaji. "
            "Kadri unavyolipa kwa wakati, score inaongezeka na unaweza kukopa zaidi.\n\n"

            "📄 Sasa tuma PDF au picha za nyaraka zako (NIDA, salary slip, mkataba, au bank statement) "
            "ili tukadirie score yako na kujua kiwango chako halisi cha mkopo."
        )
    },
    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": (
            "Tuma taarifa kwa format hii:\n\n"
            "*kalk 300000, 12, 10*\n\n"
            "Ambapo:\n"
            "• 300000 = uwezo wako wa kulipa kwa mwezi (PMT)\n"
            "• 12 = muda wa mkopo (miezi)\n"
            "• 10 = riba ya mwaka (%)"
        )
    },
    "5": {
        "title": "Aina za Mikopo kulingana na Riba",
        "description": "Mikopo hugawanywa katika riba ya kudumu na riba inayobadilika..."
    },
    "6": {
        "title": "Huduma za Mikopo za Manka",
        "description": "Manka inakuletea aina mbalimbali za mikopo kama mikopo ya simu, gari..."
    }
}

# -------------------------
# BASIC LOAN CALCULATOR
# -------------------------
def calculate_max_loan(repayment_capacity: float, duration_months: int, annual_rate_percent: float) -> float:
    if annual_rate_percent == 0:
        return repayment_capacity * duration_months

    periodic_rate = (annual_rate_percent / 100) / 12
    try:
        numerator = 1 - math.pow(1 + periodic_rate, -duration_months)
        return repayment_capacity * (numerator / periodic_rate)
    except Exception:
        return 0.0

# -------------------------
# MAIN WHATSAPP HANDLER
# -------------------------
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming = str(data.get("Body") or "").strip().lower()

        # --- TRIGGER WORDS (MENU) ---
        if incoming in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_text = "\n".join([f"*{k}* - {v['title']}" for k, v in main_menu.items()])
            reply = f"👋 *Karibu kwenye Huduma za Mikopo za Manka!*\n\nChagua huduma:\n\n{menu_text}"
            send_meta_whatsapp_message(to=from_number, body=reply)
            return PlainTextResponse("OK")

        # --- OPTION SELECTION (1–6) ---
        if incoming in main_menu:
            selected = main_menu[incoming]
            reply = f"*{selected['title']}*\n\n{selected['description']}"
            send_meta_whatsapp_message(to=from_number, body=reply)
            return PlainTextResponse("OK")

        # --- MANUAL CALCULATOR TRIGGER ---
        if incoming.startswith("kalk"):
            try:
                _, raw = incoming.split(" ", 1)
                pmt, months, rate = [x.strip() for x in raw.split(",")]

                pmt = float(pmt)
                months = int(months)
                rate = float(rate)

                max_loan = calculate_max_loan(pmt, months, rate)

                msg = (
                    "📊 *Matokeo ya Kikokotoo*\n\n"
                    f"➡️ PMT: *Tsh {pmt:,.0f}*\n"
                    f"➡️ Miezi: *{months}*\n"
                    f"➡️ Riba: *{rate}%*\n\n"
                    f"💰 *Kiasi cha juu cha mkopo unaweza kupata:* *Tsh {max_loan:,.0f}*"
                )
                send_meta_whatsapp_message(to=from_number, body=msg)
                return PlainTextResponse("OK")

            except Exception:
                send_meta_whatsapp_message(to=from_number, body="⚠️ Format si sahihi. Tumia mfano: *kalk 300000, 12, 10*")
                return PlainTextResponse("OK")

        # --- UNKNOWN INPUT ---
        send_meta_whatsapp_message(to=from_number, body="⚠️ Sijakuelewa. Tuma *menu* kuanza tena.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.error(f"Error: {e}")
        send_meta_whatsapp_message(to=from_number, body="❌ Hitilafu imetokea. Jaribu tena.")
        return PlainTextResponse("Internal Error", status_code=500)
