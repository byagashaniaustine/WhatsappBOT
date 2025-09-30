from fastapi import FastAPI, Request
import api.whatsappBOT as whatsappBOT
import api.whatsappfile as whatsappfile

app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    """
    Handles incoming WhatsApp messages via Twilio webhook.
    Routes file messages to whatsappfile module and other messages to whatsappBOT module.
    """
    data = await request.form()
    num_media = int(data.get("NumMedia", 0))

    if num_media > 0:
        # File message → forward to whatsappfile handler
        return await whatsappfile.whatsapp_file(data)

    # Normal text message → forward to bot menu
    return await whatsappBOT.whatsapp_menu(data)
