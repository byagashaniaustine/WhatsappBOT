import logging
import math
from fastapi.responses import PlainTextResponse
from services.meta import send_meta_whatsapp_message

logger = logging.getLogger("whatsapp_app")
logger.setLevel(logging.INFO)

# ---------------------------------
# MAIN MENU
# ---------------------------------
main_menu = {
    "1": {
        "title": "Fahamu kuhusu Alama za Mikopo (Credit Score)",
        "description": "Alama ya mikopo ni kipimo kinachoonyesha jinsi unavyoaminika kifedha. Kwa lugha rahisi, ni kama ripoti ya tabia yako ya kifedha — inaonyesha kama wewe ni mtu wa kuaminika au la, katika kukopa na kulipa fedha. Alama hii hutengenezwa na taasisi maalum kama Credit Reference Bureau (CRB) kwa kutumia taarifa zako za kifedha kutoka benki, taasisi za mikopo, au hata huduma za mkopo mtandaoni kama Tala, Timiza, au Fuliza.\n\nIli kupata alama nzuri ya mikopo, ni muhimu ulipie mikopo yako kwa wakati, usiwe na madeni mengi yanayozidi uwezo wako, na uendelee kutumia huduma za kifedha kwa nidhamu. Kadri unavyodumisha historia nzuri ya ulipaji, ndivyo alama yako inavyoongezeka.\n\nFaida ya kuwa na alama nzuri ni kwamba benki na taasisi za kifedha zitakuona kama mteja wa kuaminika. Hii hukurahisishia kupata mikopo mikubwa zaidi, kwa masharti nafuu na riba ndogo. Lakini kama alama yako ni mbaya, unaweza kukataliwa mkopo au kupewa kwa masharti magumu zaidi.\n\nKwa ufupi, alama ya mikopo ni kama jina lako la kifedha. Unapoitunza vizuri, unajitengenezea heshima na fursa zaidi za kifedha katika siku za usoni."
    },
    "2": {
        "title": "Kiwango cha Mkopo (Credit Bandwidth)",
        "description": "Kiwango cha mkopo ni kiasi cha juu cha fedha ambacho taasisi ya kifedha inaweza kukukopesha kulingana na hali yako ya kifedha. Kwa maneno rahisi, ni kipimo kinachoonyesha uwezo wako wa kukopa bila kuathiri uwezo wako wa kurejesha. Benki au taasisi za mikopo hutumia taarifa kama kipato chako cha kila mwezi, gharama zako za maisha, na madeni uliyonayo ili kuamua kiwango hicho.\n\nKwa mfano, kama kipato chako ni kikubwa na una historia nzuri ya ulipaji wa mikopo, taasisi inaweza kukuamini zaidi na kukuruhusu kukopa kiasi kikubwa. Lakini kama kipato chako ni kidogo au una madeni mengi, kiwango chako cha mkopo hupunguzwa ili kuepuka hatari ya kushindwa kulipa.\n\nKuelewa kiwango chako cha mkopo ni muhimu kwa sababu kinakusaidia kupanga fedha zako vizuri. Unajua mpaka gani unaweza kukopa bila kujitumbukiza kwenye matatizo ya kifedha. Kadri unavyoongeza kipato na kudumisha tabia nzuri ya ulipaji, ndivyo kiwango chako cha mkopo kinavyoongezeka kwa muda."
    },
    "3": {
        "title": "Nakopesheka!! (Uwezo wa Kukopa)",
        "description": (
            "💳 *Ili ujue kama nakopesheka tambua Uwezo wa Kukopa (Affordability)*\n\n"
            "Affordability ni kipimo kinachoonyesha uwezo wako wa kulipa mkopo bila "
            "kuumiza bajeti yako ya kila siku. Tunapima kipato chako, matumizi yako, "
            "historia ya ulipaji na uaminifu wa kifedha.\n\n"

            "📊 *Manka Affordability Score* inaonyesha kiwango cha mkopo unachoweza kuchukua:\n"
            "• *Score ya Juu* — Kiwango kinachoonesha kiasi chako cha juu unachoweza kukopa.\n"
            "• *Score ya Kati (Moderate)* — Kiwango kinachoonesha kiasi chako cha kati unachoweza kukopa sio mdogo sana wala sio mkubwa sana.\n"
            "• *Score ya Chini* — Hiki ndicho kiwango cha chini unachoweza kuchukua mkopo ambacho ni salama kuanzia.\n\n"

            "⚠️ *Ushauri:* Tunashauri uanze na kiwango cha chini ili ujenge historia nzuri ya ulipaji. "
            "Kadri unavyolipa kwa wakati, score inaongezeka na unaweza kukopa zaidi.\n\n"

            "📄 Sasa tuma faili la PDF za nyaraka zako ( salary slip au bank statement) zisizopungua miezi mitatu "
            "ili tukadirie score yako na kujua kiwango chako halisi cha mkopo."
        )
    },

    "4": {
        "title": "Kikokotoo cha Mkopo (Loan Calculator)",
        "description": "Tumia kikokotoo kujua kiasi utakacholipa kila mwezi kulingana na mkopo, muda, na riba."
    },
    "5": {
        "title": "Aina za Mikopo kulingana na Riba",
        "description": "Mikopo inaweza kuwa na riba ya kudumu au inayobadilika. Riba ya kudumu inamaanisha malipo yako ya kila mwezi hayabadiliki. Riba inayobadilika inaweza kupanda au kushuka kulingana na hali ya soko."
    },
    "6": {
        "title": "Huduma za Mikopo za Manka",
        "description": "Manka inakuletea aina mbalimbali za mikopo zinazokusaidia kukamilisha mahitaji yako ya kila siku na miradi midogo. Huduma hizi ni rahisi, haraka, na karibu nawe."
    }
}

# ---------------------------------
# USER STATES
# ---------------------------------
user_states = {}  # {phone_number: {"mode": "LOAN_CALC", "step": int, "data": {}}}

# ---------------------------------
# HELPER FUNCTIONS
# ---------------------------------
def calculate_monthly_payment(principal: float, months: int, annual_rate_percent: float) -> float:
    r = annual_rate_percent / 100 / 12
    if r == 0:
        return principal / months
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)

# ---------------------------------
# MAIN MENU HANDLER
# ---------------------------------
async def whatsapp_menu(data: dict):
    try:
        from_number = str(data.get("From") or "")
        if not from_number.startswith("+"):
            from_number = "+" + from_number

        incoming_msg = str(data.get("Body") or "").strip().lower()

        # --- LOAN CALCULATOR MODE ---
        if user_states.get(from_number, {}).get("mode") == "LOAN_CALC":
            state = user_states[from_number]
            step = state["step"]
            collected = state["data"]

            try:
                if step == 1:
                    collected["principal"] = float(incoming_msg)
                    user_states[from_number]["step"] = 2
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza muda wa mkopo kwa miezi:")
                elif step == 2:
                    collected["months"] = int(incoming_msg)
                    user_states[from_number]["step"] = 3
                    send_meta_whatsapp_message(from_number, "Tafadhali ingiza riba ya mwaka (%):")
                elif step == 3:
                    collected["rate"] = float(incoming_msg)

                    P = collected["principal"]
                    n = collected["months"]
                    r = collected["rate"]

                    monthly_payment = calculate_monthly_payment(P, n, r)

                    message = (
                        f"💰 *Matokeo ya Kikokotoo cha Mkopo*\n\n"
                        f"Kiasi cha mkopo: Tsh {P:,.0f}\n"
                        f"Muda: {n} miezi\n"
                        f"Riba ya mwaka: {r}%\n\n"
                        f"Kiasi cha kulipa kila mwezi: Tsh {monthly_payment:,.0f}"
                    )

                    send_meta_whatsapp_message(from_number, message)
                    user_states.pop(from_number)  # reset state

            except ValueError:
                send_meta_whatsapp_message(from_number, "❌ Tafadhali ingiza namba sahihi.")
            return PlainTextResponse("OK")

        # --- MAIN MENU TRIGGERS ---
        if incoming_msg in ["hi", "hello", "start", "menu", "anza", "habari", "mambo"]:
            menu_list = "\n".join([f"*{key}* - {value['title']}" for key, value in main_menu.items()])
            reply = f"👋 *Karibu kwenye Huduma za Mikopo za Manka!*\n\nChagua huduma kwa kutuma namba:\n\n{menu_list}"
            send_meta_whatsapp_message(from_number, reply)
            return PlainTextResponse("OK")

        # --- USER SELECTION ---
        if incoming_msg in main_menu:
            if incoming_msg == "4":  # start loan calculator mode
                user_states[from_number] = {"mode": "LOAN_CALC", "step": 1, "data": {}}
                send_meta_whatsapp_message(from_number, "Karibu kwenye Kikokotoo cha Mkopo!\nTafadhali ingiza kiasi unachotaka kukopa (Tsh):")
                return PlainTextResponse("OK")
            else:
                item = main_menu[incoming_msg]
                send_meta_whatsapp_message(from_number, f"*{item['title']}*\n\n{item['description']}")
                return PlainTextResponse("OK")

        # --- UNKNOWN INPUT ---
        send_meta_whatsapp_message(from_number, "⚠️ Samahani, sielewi chaguo lako. Tuma *menu* kuanza tena.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"❌ Error in whatsapp_menu: {e}")
        send_meta_whatsapp_message(from_number, "❌ Hitilafu imetokea. Tafadhali jaribu tena au tuma 'menu'.")
        return PlainTextResponse("Internal Server Error", status_code=500)
