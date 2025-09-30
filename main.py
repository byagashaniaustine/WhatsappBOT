from fastapi import FastAPI, Request
from api.whatsappBOT import whatsappBOT
from api.whatsappfile import whatsappfile

app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    incoming_msg = data.get("Body", "").strip().lower()

    # If file message → forward to whatsappFile
    if data.get("NumMedia") and int(data.get("NumMedia")) > 0:
        return await whatsappfile.whatsapp_file(data)

    # Otherwise → normal bot menu
    return await whatsappBOT.whatsapp_menu(data)
