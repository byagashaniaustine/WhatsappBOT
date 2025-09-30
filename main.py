from fastapi import FastAPI, Request
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import whatsapp_file

app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    num_media = int(data.get("NumMedia", 0))

    if num_media > 0:
        # File message → forward to whatsappfile handler
        return await whatsappfile.whatsapp_file(data)

    # Normal text message → forward to bot menu
    return await whatsappBOT.whatsapp_menu(data)
