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
        "title": "Fahamu Alama za Mikopo (Credit Scoring)",
        "description": "Alama ya mikopo ni kipimo kinachoonyesha jinsi unavyoaminika kifedha. Kwa lugha rahisi, ni kama ripoti ya tabia yako ya kifedha — inaonyesha kama wewe ni mtu wa kuaminika au la, katika kukopa na kulipa fedha. Alama hii hutengenezwa na taasisi maalum kama Credit Reference Bureau (CRB) kwa kutumia taarifa zako za kifedha kutoka benki, taasisi za mikopo, au hata huduma za mkopo mtandaoni kama Tala, Timiza, au Fuliza.\n\nIli kupata alama nzuri ya mikopo, ni muhimu ulipie mikopo yako kwa wakati, usiwe na madeni mengi yanayozidi uwezo wako, na uendelee kutumia huduma za kifedha kwa nidhamu. Kadri unavyodumisha historia nzuri ya ulipaji, ndivyo alama yako inavyoongezeka.\n\nFaida ya kuwa na alama nzuri ni kwamba benki na taasisi za kifedha zitakuona kama mteja wa kuaminika. Hii hukurahisishia kupata mikopo mikubwa zaidi, kwa masharti nafuu na riba ndogo. Lakini kama alama yako ni mbaya, unaweza kukataliwa mkopo au kupewa kwa masharti magumu zaidi.\n\nKwa ufupi, alama ya mikopo ni kama jina lako la kifedha. Unapoitunza vizuri, unajitengenezea heshima na fursa zaidi za kifedha katika siku za usoni."
    },
    "2": {
        "title": "Kiwango cha Mkopo (Credit Bandwidth)",
        "description": "Kiwango cha mkopo ni kiasi cha juu cha fedha ambacho taasisi ya kifedha inaweza kukukopesha kulingana na hali yako ya kifedha. Kwa maneno rahisi, ni kipimo kinachoonyesha uwezo wako wa kukopa bila kuathiri uwezo wako wa kurejesha. Benki au taasisi za mikopo hutumia taarifa kama kipato chako cha kila mwezi, gharama zako za maisha, na madeni uliyonayo ili kuamua kiwango hicho.\n\nKwa mfano, kama kipato chako ni kikubwa na una historia nzuri ya ulipaji wa mikopo, taasisi inaweza kukuamini zaidi na kukuruhusu kukopa kiasi kikubwa. Lakini kama kipato chako ni kidogo au una madeni mengi, kiwango chako cha mkopo hupunguzwa ili kuepuka hatari ya kushindwa kulipa.\n\nKuelewa kiwango chako cha mkopo ni muhimu kwa sababu kinakusaidia kupanga fedha zako vizuri. Unajua mpaka gani unaweza kukopa bila kujitumbukiza kwenye matatizo ya kifedha. Kadri unavyoongeza kipato na kudumisha tabia nzuri ya ulipaji, ndivyo kiwango chako cha mkopo kinavyoongezeka kwa muda."
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
        "title": "Aina za Mikopo kulingana na Riba (Types of Loans by Interest Rate)",
        "description": "Mikopo inaweza kugawanywa katika makundi mawili makuu kulingana na jinsi riba yake inavyobadilika au kubaki vilevile. Hii inaitwa riba ya kudumu (fixed interest) na riba inayobadilika (variable interest).\n\n1️⃣ **Mkopo wenye Riba ya Kudumu (Fixed Interest Loan)**\nHapa kiwango cha riba hakibadiliki katika kipindi chote cha mkopo. Hii inamaanisha utakuwa unalipa kiasi kilekile cha malipo kila mwezi hadi mkopo wako umalizike. Ni aina ya mkopo ambayo inasaidia kupanga bajeti kwa urahisi, kwa sababu unajua kiasi utakacholipa kila mwezi bila mshangao. Hata kama riba sokoni itaongezeka, yako inabaki pale pale.\n\nMfano: Ukipewa mkopo wa milioni 5 kwa riba ya 10% kwa miaka 2, utalipa kiasi kilekile cha malipo kila mwezi hadi mwisho.\n\n2️⃣ **Mkopo wenye Riba Inayobadilika (Variable Interest Loan)**\nHapa kiwango cha riba hubadilika kulingana na mabadiliko ya soko au sera za benki kuu. Inaweza kupanda au kushuka kadri uchumi unavyobadilika. Wakati mwingine hii inaweza kuwa na faida kama riba itashuka, lakini pia inaweza kuongeza mzigo wa malipo kama riba itapanda.\n\nMfano: Ukipewa mkopo wa milioni 5 kwa riba ya 12% na baada ya miezi 6 riba ya soko ikipanda hadi 15%, malipo yako ya kila mwezi nayo yataongezeka.\n\nKwa ufupi, mikopo yenye riba ya kudumu ni salama na rahisi kupanga bajeti, wakati mikopo yenye riba inayobadilika inaweza kuwa na faida au hasara kulingana na hali ya soko. Ni muhimu kuelewa aina hizi kabla ya kukopa, ili ujue hatari na manufaa yake."
    },
    "6":{
        "title": "Huduma za Mikopo za Manka",
        "description": "Manka inakuletea aina mbalimbali za mikopo zinazokusaidia kukamilisha mahitaji yako ya kila siku na miradi midogo. Huduma hizi ni rahisi, haraka, na karibu nawe.\n\n1️⃣ **Simu za Mikopo** – Mikopo hii inakusaidia kununua simu mpya au kulipa simu unazotumia, bila kushughulikia gharama kubwa mara moja.\n\n2️⃣ **Gari za Mikopo** – Kwa mtu anayetaka kununua gari la kibinafsi au la biashara, Manka inakupa mkopo unaoweza kulipwa kwa awamu, ukipunguza mzigo wa kifedha.\n\n3️⃣ **Mikopo ya Kilimo (Agriculture Utilities and Equipments)** – Mikopo hii inasaidia wakulima kununua mashine, zana, na vifaa vya kilimo kama ploughs, pampu za maji, na mbegu ili kuongeza tija na uzalishaji.\n\n4️⃣ **Vifaa vya Tiba (Medical Equipments and Medical Tools)** – Kwa watoa huduma za afya au hospitali ndogo, Manka inatoa mikopo ya kununua vifaa vya matibabu kama mashine za vipimo, viti vya upasuaji, na vifaa vingine muhimu.\n\nKwa kifupi, **Huduma za Mikopo za Manka** ni njia rahisi ya kupata pesa kwa ajili ya mahitaji yako muhimu, miradi ya biashara, au uwekezaji mdogo, bila kushughulikia gharama kubwa mara moja."
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
